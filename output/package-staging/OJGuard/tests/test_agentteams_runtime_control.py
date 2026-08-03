import tempfile
import unittest
from pathlib import Path

from backend.app.domain import IncidentType, RejudgeBatchState
from mcp_server.tools import OJGuardTools
from scripts.agentteams_runtime_control import approve, bootstrap, status


class AgentTeamsRuntimeControlTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_live_orchestration_starts_clean_and_reaches_resolved(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            initial = bootstrap(root, IncidentType.NODE_DEGRADATION)
            incident_id = initial["incident_id"]

            self.assertEqual(initial["stage"], "TRIAGING")
            self.assertFalse(initial["precomputed_root_cause"])
            self.assertFalse(initial["precomputed_impact"])
            self.assertFalse(initial["precomputed_plan"])
            self.assertEqual(initial["hypothesis_count"], 0)
            self.assertEqual(initial["impact_count"], 0)
            self.assertEqual(initial["plan_count"], 0)

            tools = OJGuardTools(root)
            self.assertEqual(
                tools.incident_triage_signals(incident_id)["stage"],
                "INVESTIGATING",
            )
            hypotheses = tools.judge_replay_submission(incident_id, mode="hypotheses")
            self.assertEqual(hypotheses["stage"], "INVESTIGATING")
            self.assertFalse(hypotheses["experiment_executed"])
            self.assertEqual(
                tools.judge_replay_submission(incident_id, mode="experiment")["stage"],
                "IMPACT_ASSESSING",
            )
            self.assertEqual(
                tools.impact_calculate_scope(incident_id)["stage"],
                "REMEDIATION_PLANNING",
            )
            self.assertEqual(
                tools.rejudge_create_plan(incident_id)["stage"],
                "APPROVAL_PENDING",
            )

            technical = approve(root, incident_id, "technical", "demo-operator")
            self.assertEqual(technical["approval_state"]["execute_plan"], "APPROVED")
            self.assertEqual(technical["approval_state"]["run_canary_rejudge"], "APPROVED")
            control = tools.rejudge_execute_batch(incident_id, "control_canary")
            self.assertEqual(control["incident"]["stage"], "EXECUTING")

            business = approve(root, incident_id, "business", "demo-operator")
            self.assertEqual(business["approval_state"]["run_bulk_rejudge"], "APPROVED")
            bulk = tools.rejudge_execute_batch(incident_id, "bulk")
            self.assertEqual(bulk["incident"]["stage"], "REJUDGING")
            tools.verification_verify_incident(incident_id)

            closed = approve(root, incident_id, "close", "demo-operator")
            self.assertEqual(closed["stage"], "RESOLVED")
            final = status(tools.repository, incident_id)
            self.assertEqual(final["hypothesis_count"], 2)
            self.assertEqual(final["experiment_count"], 1)
            self.assertEqual(final["verification_count"], 1)
            self.assertTrue(final["rejudge_complete"])

    def test_inconclusive_route_then_canary_failure_recovers_with_new_plan(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            initial = bootstrap(
                root,
                IncidentType.NODE_DEGRADATION,
                task_id="TASK-RECOVERY",
            )
            incident_id = initial["incident_id"]
            tools = OJGuardTools(root)

            tools.incident_triage_signals(incident_id)
            proposed = tools.judge_replay_submission(incident_id, mode="hypotheses")
            self.assertEqual(len(proposed["experiment_candidates"]), 3)

            inconclusive = tools.judge_replay_submission(
                incident_id,
                mode="experiment",
                experiment_kind="cross_image_replay",
            )
            self.assertEqual(inconclusive["stage"], "INVESTIGATING")
            self.assertEqual(inconclusive["state"], "INCONCLUSIVE")
            remaining = tools.judge_replay_submission(incident_id, mode="candidates")
            self.assertNotIn(
                "cross_image_replay",
                {item["kind"] for item in remaining["experiment_candidates"]},
            )

            discriminating = tools.judge_replay_submission(
                incident_id,
                mode="experiment",
                experiment_kind="cross_node_replay",
            )
            self.assertEqual(discriminating["stage"], "IMPACT_ASSESSING")
            tools.impact_calculate_scope(incident_id)
            initial_plan = tools.rejudge_create_plan(incident_id)
            self.assertEqual(initial_plan["plan"]["revision"], 1)

            approve(root, incident_id, "technical", "demo-operator")
            failed = tools.rejudge_execute_batch(
                incident_id,
                "control_canary",
                inject_canary_failure=True,
            )
            self.assertEqual(failed["incident"]["stage"], "PAUSED")
            self.assertIn(
                "FAILED",
                {item["state"] for item in failed["batches"] if item["kind"] == "canary"},
            )

            recovery = tools.rejudge_create_plan(incident_id, mode="recovery")
            self.assertEqual(recovery["stage"], "APPROVAL_PENDING")
            self.assertEqual(recovery["plan"]["revision"], 2)
            self.assertEqual(recovery["plan"]["supersedes_plan_id"], initial_plan["plan"]["id"])
            self.assertEqual(
                recovery["batches"][-1]["kind"],
                "canary_retry",
            )

            approve(root, incident_id, "technical", "demo-operator")
            retried = tools.rejudge_execute_batch(incident_id, "control_canary")
            self.assertEqual(retried["incident"]["stage"], "EXECUTING")
            states = {(item["kind"], item["state"]) for item in retried["batches"]}
            self.assertIn(("canary", RejudgeBatchState.ROLLED_BACK.value), states)
            self.assertIn(("canary_retry", RejudgeBatchState.COMPLETED.value), states)

            approve(root, incident_id, "business", "demo-operator")
            tools.rejudge_execute_batch(incident_id, "bulk")
            verification = tools.verification_verify_incident(incident_id)
            self.assertEqual(verification["coverage_rate"], 1)
            self.assertEqual(verification["duplicate_rejudge_count"], 0)
            self.assertEqual(verification["missing_rejudge_count"], 0)
            self.assertEqual(verification["cross_scope_regression_count"], 0)
            closed = approve(root, incident_id, "close", "demo-operator")
            self.assertEqual(closed["stage"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
