from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from backend.app.domain import IncidentType, RouteDecision
from backend.app.services.agent_routing import AgentRoutingPolicy
from mcp_server.tools import OJGuardTools
from scripts.agentteams_runtime_control import approve


def _validated_choice(options, experiment_kind: str):
    option = next(item for item in options if item.experiment_kind == experiment_kind)
    decision = RouteDecision(
        action=option.action,
        worker=option.worker,
        reason=f"Deterministic test selects {experiment_kind}.",
        evidence_refs=option.evidence_refs,
        experiment_kind=option.experiment_kind,
        expected_result=option.expected_result,
        failure_action=option.failure_action,
    )
    AgentRoutingPolicy.validate_decision(decision, options)
    return option, decision


def generate_evidence(state_root: Path, output_path: Path) -> dict:
    tools = OJGuardTools(state_root)
    incident = tools.workflow.start_triage_demo(IncidentType.NODE_DEGRADATION)
    incident_id = incident.incident_id
    route_policy = AgentRoutingPolicy(tools.repository)

    tools.incident_triage_signals(incident_id)
    hypotheses = tools.judge_replay_submission(incident_id, mode="hypotheses")
    incident = tools.repository.get_incident(incident_id)
    if incident is None:
        raise RuntimeError("incident was not persisted")
    initial_options = route_policy.legal_options(incident)
    first_option, first_decision = _validated_choice(initial_options, "cross_image_replay")
    inconclusive = tools.judge_replay_submission(
        incident_id,
        mode="experiment",
        experiment_kind=first_option.experiment_kind,
    )

    incident = tools.repository.get_incident(incident_id)
    if incident is None:
        raise RuntimeError("incident disappeared after experiment")
    remaining_options = route_policy.legal_options(incident)
    second_option, second_decision = _validated_choice(remaining_options, "cross_node_replay")
    confirmed = tools.judge_replay_submission(
        incident_id,
        mode="experiment",
        experiment_kind=second_option.experiment_kind,
    )

    impact_payload = tools.impact_calculate_scope(incident_id)
    initial_plan_payload = tools.rejudge_create_plan(incident_id)
    initial_plan = initial_plan_payload["plan"]
    approve(state_root, incident_id, "technical", "deterministic-demo-operator")
    failed = tools.rejudge_execute_batch(
        incident_id,
        "control_canary",
        inject_canary_failure=True,
    )
    paused_incident = tools.repository.get_incident(incident_id)
    if paused_incident is None:
        raise RuntimeError("paused incident was not persisted")
    recovery_options = route_policy.legal_options(paused_incident)
    if [item.action for item in recovery_options] != ["recovery_plan"]:
        raise RuntimeError("PAUSED did not expose exactly one bounded recovery route")

    recovery_payload = tools.rejudge_create_plan(incident_id, mode="recovery")
    recovery_plan = recovery_payload["plan"]
    recovery_pending = tools.repository.get_incident(incident_id)
    if recovery_pending is None:
        raise RuntimeError("recovery plan incident was not persisted")
    revoked_before_reapproval = {
        key: value.value
        for key, value in recovery_pending.approval_state.items()
        if key in {"execute_plan", "run_canary_rejudge"}
    }
    approval_after_recovery = approve(
        state_root,
        incident_id,
        "technical",
        "deterministic-demo-operator",
    )
    retried = tools.rejudge_execute_batch(incident_id, "control_canary")
    approve(state_root, incident_id, "business", "deterministic-demo-operator")
    tools.rejudge_execute_batch(incident_id, "bulk")
    verification = tools.verification_verify_incident(incident_id)
    final = approve(state_root, incident_id, "close", "deterministic-demo-operator")

    impact = tools.repository.list_impact_assessments(incident_id)[-1]
    scope_hash = sha256("\n".join(sorted(impact.submission_ids)).encode("utf-8")).hexdigest()
    experiments = tools.repository.list_incident_experiments(incident_id)
    batches = tools.repository.list_rejudge_batches(incident_id)
    payload = {
        "evidence_class": "deterministic_policy_and_recovery_test",
        "model_calls": 0,
        "paid_api_cost": 0,
        "incident_id": incident_id,
        "scenario": "node_degradation",
        "initial_experiment_candidate_count": len(hypotheses["experiment_candidates"]),
        "route_decisions": [
            first_decision.model_dump(mode="json"),
            second_decision.model_dump(mode="json"),
        ],
        "experiment_results": [
            {
                "kind": experiments[0].kind,
                "state": experiments[0].state.value,
                "stage_after": inconclusive["stage"],
            },
            {
                "kind": experiments[1].kind,
                "state": experiments[1].state.value,
                "stage_after": confirmed["stage"],
            },
        ],
        "impact": {
            "assessment_id": impact.id,
            "submission_count": impact.affected_submission_count,
            "candidate_count": impact.affected_candidate_count,
            "scope_sha256": scope_hash,
            "reported_stage": impact_payload["stage"],
        },
        "canary_failure": {
            "stage_after": failed["incident"]["stage"],
            "rolled_back_failed_batches": [
                item.id for item in batches if item.state.value == "ROLLED_BACK"
            ],
            "recovery_route": recovery_options[0].model_dump(mode="json"),
        },
        "plan_versions": [
            {
                "id": initial_plan["id"],
                "revision": initial_plan["revision"],
                "supersedes_plan_id": initial_plan["supersedes_plan_id"],
            },
            {
                "id": recovery_plan["id"],
                "revision": recovery_plan["revision"],
                "supersedes_plan_id": recovery_plan["supersedes_plan_id"],
            },
        ],
        "fresh_technical_approval": {
            "revoked_before_reapproval": revoked_before_reapproval,
            "after_reapproval": {
                "execute_plan": approval_after_recovery["approval_state"]["execute_plan"],
                "run_canary_rejudge": approval_after_recovery["approval_state"][
                    "run_canary_rejudge"
                ],
            },
        },
        "batch_results": [
            item.model_dump(mode="json", exclude={"submission_ids"}) for item in batches
        ],
        "recovery_canary_passed": retried["incident"]["canary_rejudge_passed"],
        "verification": verification,
        "final_stage": final["stage"],
        "assertions": {
            "multiple_legal_experiments": len(initial_options) >= 2,
            "first_experiment_inconclusive": experiments[0].state.value == "INCONCLUSIVE",
            "manager_can_choose_second_experiment": experiments[1].state.value == "PASSED",
            "canary_failure_pauses": failed["incident"]["stage"] == "PAUSED",
            "recovery_plan_is_new_revision": recovery_plan["revision"] == 2,
            "fresh_approval_required": initial_plan["id"] == recovery_plan["supersedes_plan_id"]
            and revoked_before_reapproval
            == {
                "execute_plan": "REVOKED",
                "run_canary_rejudge": "REVOKED",
            },
            "recovery_canary_passes": retried["incident"]["canary_rejudge_passed"],
            "verification_has_full_coverage": verification["coverage_rate"] == 1,
            "no_duplicate_rejudge": verification["duplicate_rejudge_count"] == 0,
            "no_missing_rejudge": verification["missing_rejudge_count"] == 0,
            "no_cross_scope_rejudge": verification["cross_scope_regression_count"] == 0,
            "resolved": final["stage"] == "RESOLVED",
        },
    }
    if not all(payload["assertions"].values()):
        raise RuntimeError("one or more deterministic recovery assertions failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate zero-cost deterministic evidence for dynamic routing and recovery."
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path(".runtime") / "deterministic-recovery",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output") / "evidence" / "agentteams" / "deterministic-recovery-evidence.json",
    )
    args = parser.parse_args()
    payload = generate_evidence(args.state_root, args.output)
    print(json.dumps(payload["assertions"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
