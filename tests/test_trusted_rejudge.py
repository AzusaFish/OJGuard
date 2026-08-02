from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.app.domain import (
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentStage,
    IncidentType,
    RejudgeBatchState,
)
from backend.app.services.incident_workflow import (
    IncidentWorkflowError,
    IncidentWorkflowService,
)
from backend.app.services.repository import SQLiteRepository
from backend.app.services.scenario_data import ScenarioDataGenerator
from backend.app.services.trusted_rejudge import (
    assess_impact,
    complete_batch,
    infer_affected_submission_ids,
    plan_rejudge_batches,
    verify_rejudge,
)


class TrustedRejudgeTests(unittest.TestCase):
    def test_inferred_scope_matches_labelled_truth_for_all_executable_scenarios(self) -> None:
        generator = ScenarioDataGenerator()
        for incident_type in (
            IncidentType.RUNTIME_REGRESSION,
            IncidentType.NODE_DEGRADATION,
            IncidentType.CHECKER_DEFECT,
        ):
            with self.subTest(incident_type=incident_type):
                dataset = generator.generate(incident_type)
                self.assertEqual(
                    set(infer_affected_submission_ids(dataset)),
                    set(dataset.truth.affected_submission_ids),
                )

    def test_impact_batches_and_verification_are_exact_and_idempotent(self) -> None:
        dataset = ScenarioDataGenerator().checker_defect()
        impact = assess_impact("INC-TEST", dataset, "problem-version-and-submission")
        self.assertEqual(impact.affected_submission_count, len(dataset.truth.affected_submission_ids))
        self.assertEqual(impact.affected_candidate_count, len(dataset.truth.affected_candidate_ids))

        batches = plan_rejudge_batches("INC-TEST", "PLAN-TEST", impact.submission_ids)
        self.assertEqual(batches[0].kind, "control")
        self.assertEqual(batches[0].planned_count, min(20, len(impact.submission_ids)))
        completed_once = [complete_batch(item) for item in batches]
        completed_twice = [complete_batch(item) for item in completed_once]
        self.assertEqual(completed_once, completed_twice)
        self.assertTrue(all(item.state == RejudgeBatchState.COMPLETED for item in completed_twice))

        score_changes = []
        verification = verify_rejudge("INC-TEST", impact, completed_twice, score_changes)
        self.assertEqual(verification.coverage_rate, 1)
        self.assertEqual(verification.duplicate_rejudge_count, 0)
        self.assertEqual(verification.missing_rejudge_count, 0)
        self.assertFalse(verification.checks["score_changes_recalculated"])


class IncidentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(".test-tmp") / f"workflow-{uuid4().hex}"
        self.repository = SQLiteRepository(self.root / "ojguard.db")
        self.workflow = IncidentWorkflowService(self.repository)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_dual_gate_rejudge_and_close_workflow(self) -> None:
        incident = self.workflow.prepare_demo(IncidentType.CHECKER_DEFECT)
        self.assertEqual(incident.stage, IncidentStage.APPROVAL_PENDING)

        with self.assertRaises(IncidentWorkflowError):
            self.workflow.record_approval(
                incident.incident_id,
                action=IncidentApprovalAction.APPROVE_REMEDIATION,
                role_context="business_approver",
                actor="demo-operator",
                decision=IncidentApprovalDecision.APPROVED,
            )

        for action in (
            IncidentApprovalAction.APPROVE_REMEDIATION,
            IncidentApprovalAction.RUN_CANARY_REJUDGE,
        ):
            self.workflow.record_approval(
                incident.incident_id,
                action=action,
                role_context="technical_approver",
                actor="demo-operator",
                decision=IncidentApprovalDecision.APPROVED,
            )
        executing = self.workflow.execute_control_and_canary(incident.incident_id)
        self.assertEqual(executing.stage, IncidentStage.EXECUTING)
        self.assertTrue(executing.canary_rejudge_passed)

        self.workflow.record_approval(
            incident.incident_id,
            action=IncidentApprovalAction.RUN_BULK_REJUDGE,
            role_context="business_approver",
            actor="demo-operator",
            decision=IncidentApprovalDecision.APPROVED,
        )
        rejudging = self.workflow.execute_bulk(incident.incident_id)
        first_score_ids = rejudging.score_change_ids
        rejudging_again = self.workflow.execute_bulk(incident.incident_id)
        self.assertEqual(first_score_ids, rejudging_again.score_change_ids)
        self.assertTrue(rejudging_again.rejudge_complete)

        verifying = self.workflow.verify(incident.incident_id)
        self.assertEqual(verifying.stage, IncidentStage.VERIFYING)
        verification = self.repository.list_incident_verifications(incident.incident_id)[-1]
        self.assertEqual(verification.coverage_rate, 1)
        self.assertTrue(all(verification.checks.values()))

        self.workflow.record_approval(
            incident.incident_id,
            action=IncidentApprovalAction.CLOSE_INCIDENT,
            role_context="business_approver",
            actor="demo-operator",
            decision=IncidentApprovalDecision.APPROVED,
        )
        closed = self.workflow.close(incident.incident_id)
        self.assertEqual(closed.stage, IncidentStage.RESOLVED)


if __name__ == "__main__":
    unittest.main()
