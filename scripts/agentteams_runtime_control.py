from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.domain import (
    AgentRun,
    AgentRunEvent,
    AgentRunEventType,
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentStage,
    IncidentType,
)
from backend.app.services.agent_routing import AgentRoutingPolicy
from backend.app.services.incident_workflow import (
    APPROVAL_STATE_KEY,
    IncidentWorkflowService,
)
from backend.app.services.repository import SQLiteRepository


def _runtime(workspace_root: Path) -> tuple[SQLiteRepository, IncidentWorkflowService]:
    root = workspace_root.resolve()
    repository = SQLiteRepository(root / "data" / "ojguard.sqlite3")
    return repository, IncidentWorkflowService(repository)


def ensure_run(
    repository: SQLiteRepository,
    incident_id: str,
    task_id: str,
    max_model_responses: int = 20,
) -> AgentRun:
    existing = repository.get_agent_run_by_task(task_id)
    if existing is not None:
        if existing.incident_id != incident_id:
            raise ValueError("task_id already belongs to another incident")
        return existing
    run = AgentRun(
        run_id=f"ARUN-{uuid4().hex[:12].upper()}",
        task_id=task_id,
        incident_id=incident_id,
        max_model_responses=max_model_responses,
    )
    repository.save_agent_run(run)
    repository.append_agent_run_event(
        AgentRunEvent(
            id=f"AEVT-{uuid4().hex[:12].upper()}",
            run_id=run.run_id,
            incident_id=incident_id,
            event_type=AgentRunEventType.RUN_CREATED,
            agent="ojguard-runtime-control",
            action="bootstrap",
            summary="Clean TRIAGING incident created for live AgentTeams orchestration.",
            after_stage=IncidentStage.TRIAGING,
        )
    )
    stored = repository.get_agent_run(run.run_id)
    if stored is None:
        raise ValueError("agent run was not persisted")
    return stored


def bootstrap(
    workspace_root: Path,
    incident_type: IncidentType,
    task_id: str | None = None,
    max_model_responses: int = 20,
) -> dict[str, Any]:
    repository, workflow = _runtime(workspace_root)
    incident = workflow.start_triage_demo(incident_type)
    run = ensure_run(
        repository,
        incident.incident_id,
        task_id or f"OJGUARD-{uuid4().hex[:12].upper()}",
        max_model_responses,
    )
    return status(repository, incident.incident_id, run.run_id) | {
        "event": "AGENTTEAMS_INCIDENT_BOOTSTRAPPED",
        "precomputed_root_cause": False,
        "precomputed_impact": False,
        "precomputed_plan": False,
    }


def status(
    repository: SQLiteRepository,
    incident_id: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    incident = repository.get_incident(incident_id)
    if incident is None:
        raise ValueError("incident not found")
    run = (
        repository.get_agent_run(run_id)
        if run_id
        else repository.get_latest_agent_run_for_incident(incident_id)
    )
    options = AgentRoutingPolicy(repository).legal_options(incident)
    return {
        "incident_id": incident_id,
        "stage": incident.stage.value,
        "signal_count": len(repository.list_incident_signals(incident_id)),
        "hypothesis_count": len(repository.list_root_cause_hypotheses(incident_id)),
        "experiment_count": len(repository.list_incident_experiments(incident_id)),
        "impact_count": len(repository.list_impact_assessments(incident_id)),
        "plan_count": len(repository.list_remediation_plans(incident_id)),
        "batch_count": len(repository.list_rejudge_batches(incident_id)),
        "verification_count": len(
            repository.list_incident_verifications(incident_id)
        ),
        "approval_state": {
            key: value.value for key, value in incident.approval_state.items()
        },
        "control_experiment_passed": incident.control_experiment_passed,
        "canary_rejudge_passed": incident.canary_rejudge_passed,
        "rejudge_complete": incident.rejudge_complete,
        "open_questions": incident.open_questions,
        "legal_route_options": [item.model_dump(mode="json") for item in options],
        "agent_run": run.model_dump(mode="json") if run else None,
    }


def record_event(
    workspace_root: Path,
    *,
    run_id: str,
    event_id: str,
    event_type: AgentRunEventType,
    agent: str,
    summary: str,
    action: str | None = None,
    worker: str | None = None,
    tool: str | None = None,
    evidence_refs: list[str] | None = None,
    before_stage: IncidentStage | None = None,
    after_stage: IncidentStage | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repository, _ = _runtime(workspace_root)
    run = repository.get_agent_run(run_id)
    if run is None:
        raise ValueError("agent run not found")
    stored = repository.append_agent_run_event(
        AgentRunEvent(
            id=event_id,
            run_id=run_id,
            incident_id=run.incident_id,
            event_type=event_type,
            agent=agent,
            action=action,
            worker=worker,
            tool=tool,
            summary=summary,
            evidence_refs=evidence_refs or [],
            before_stage=before_stage,
            after_stage=after_stage,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
    )
    updated_run = repository.get_agent_run(run_id)
    return {
        "event": stored.model_dump(mode="json"),
        "run": updated_run.model_dump(mode="json") if updated_run else None,
    }


def _approve_once(
    repository: SQLiteRepository,
    workflow: IncidentWorkflowService,
    incident_id: str,
    action: IncidentApprovalAction,
    role_context: str,
    actor: str,
) -> None:
    incident = repository.get_incident(incident_id)
    if incident is None:
        raise ValueError("incident not found")
    state_key = APPROVAL_STATE_KEY[action]
    if incident.approval_state.get(state_key) == IncidentApprovalDecision.APPROVED:
        return
    workflow.record_approval(
        incident_id,
        action=action,
        role_context=role_context,
        actor=actor,
        decision=IncidentApprovalDecision.APPROVED,
        reason="Single-operator competition demo role context; not model approval.",
    )


def approve(
    workspace_root: Path,
    incident_id: str,
    gate: str,
    actor: str,
) -> dict[str, Any]:
    repository, workflow = _runtime(workspace_root)
    if gate == "technical":
        for action in (
            IncidentApprovalAction.APPROVE_REMEDIATION,
            IncidentApprovalAction.RUN_CANARY_REJUDGE,
        ):
            _approve_once(
                repository,
                workflow,
                incident_id,
                action,
                "technical_approver",
                actor,
            )
    elif gate == "business":
        _approve_once(
            repository,
            workflow,
            incident_id,
            IncidentApprovalAction.RUN_BULK_REJUDGE,
            "business_approver",
            actor,
        )
    elif gate == "close":
        _approve_once(
            repository,
            workflow,
            incident_id,
            IncidentApprovalAction.CLOSE_INCIDENT,
            "business_approver",
            actor,
        )
        incident = repository.get_incident(incident_id)
        if incident is not None and incident.stage == IncidentStage.VERIFYING:
            workflow.close(incident_id)
    else:
        raise ValueError("gate must be technical, business, or close")
    return status(repository, incident_id) | {
        "event": "HUMAN_GATE_RECORDED",
        "gate": gate,
        "actor": actor,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bounded host-side controls for the live AgentTeams incident demo."
    )
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument(
        "--incident-type",
        type=IncidentType,
        default=IncidentType.RUNTIME_REGRESSION,
        choices=list(IncidentType),
    )
    bootstrap_parser.add_argument("--task-id")
    bootstrap_parser.add_argument("--max-model-responses", type=int, default=20)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--incident-id", required=True)
    status_parser.add_argument("--run-id")

    ensure_parser = subparsers.add_parser("ensure-run")
    ensure_parser.add_argument("--incident-id", required=True)
    ensure_parser.add_argument("--task-id", required=True)
    ensure_parser.add_argument("--max-model-responses", type=int, default=20)

    event_parser = subparsers.add_parser("event")
    event_parser.add_argument("--run-id", required=True)
    event_parser.add_argument("--event-id", required=True)
    event_parser.add_argument(
        "--event-type", required=True, choices=[item.value for item in AgentRunEventType]
    )
    event_parser.add_argument("--agent", required=True)
    event_parser.add_argument("--summary", required=True)
    event_parser.add_argument("--action")
    event_parser.add_argument("--worker")
    event_parser.add_argument("--tool")
    event_parser.add_argument("--evidence-refs", default="")
    event_parser.add_argument("--before-stage", choices=[item.value for item in IncidentStage])
    event_parser.add_argument("--after-stage", choices=[item.value for item in IncidentStage])
    event_parser.add_argument("--metadata-json", default="{}")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--incident-id", required=True)
    approve_parser.add_argument(
        "--gate", required=True, choices=("technical", "business", "close")
    )
    approve_parser.add_argument("--actor", default="demo-operator")

    args = parser.parse_args()
    if args.command == "bootstrap":
        payload = bootstrap(
            args.workspace_root,
            args.incident_type,
            args.task_id,
            args.max_model_responses,
        )
    elif args.command == "status":
        repository, _ = _runtime(args.workspace_root)
        payload = status(repository, args.incident_id, args.run_id)
    elif args.command == "ensure-run":
        repository, _ = _runtime(args.workspace_root)
        run = ensure_run(
            repository,
            args.incident_id,
            args.task_id,
            args.max_model_responses,
        )
        payload = status(repository, args.incident_id, run.run_id)
    elif args.command == "event":
        payload = record_event(
            args.workspace_root,
            run_id=args.run_id,
            event_id=args.event_id,
            event_type=AgentRunEventType(args.event_type),
            agent=args.agent,
            summary=args.summary,
            action=args.action,
            worker=args.worker,
            tool=args.tool,
            evidence_refs=[item for item in args.evidence_refs.split(",") if item],
            before_stage=(IncidentStage(args.before_stage) if args.before_stage else None),
            after_stage=(IncidentStage(args.after_stage) if args.after_stage else None),
            metadata=json.loads(args.metadata_json),
        )
    else:
        payload = approve(args.workspace_root, args.incident_id, args.gate, args.actor)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
