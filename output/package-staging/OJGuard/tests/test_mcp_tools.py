import asyncio
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from backend.app.domain import (
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentType,
)
from backend.app.services.package_ingest import PackageIngestor
from mcp_server.tools import MCPToolError, OJGuardTools


class MCPToolsTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    @staticmethod
    def package_payload() -> bytes:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("statement.md", "# Demo")
            archive.writestr("problem.yaml", "name: Demo")
            archive.writestr("checker/checker.cpp", "int main() { return 0; }")
        return buffer.getvalue()

    def test_inspect_package_identifies_roles_without_execution(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            PackageIngestor(root / "data" / "packages").ingest_zip(
                package_id="demo", filename="demo.zip", payload=self.package_payload()
            )
            tools = OJGuardTools(root)
            result = tools.problem_audit_package("demo")
            self.assertEqual(result["status"], "SUCCESS")
            self.assertFalse(result["execution_performed"])
            self.assertEqual(result["roles"]["checker"], ["checker/checker.cpp"])

    def test_rejects_unsafe_identifier(self) -> None:
        with self.temporary_directory() as directory:
            tools = OJGuardTools(Path(directory))
            with self.assertRaises(MCPToolError):
                tools.problem_audit_package("../escape")

    def test_incident_tools_reject_unknown_incident(self) -> None:
        with self.temporary_directory() as directory:
            tools = OJGuardTools(Path(directory))
            with self.assertRaises(MCPToolError):
                tools.incident_list_signals("INC-UNKNOWN")

    def test_runtime_replay_reuses_hashed_real_runner_evidence(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            evidence_path = root / "output" / "evidence" / "java-runtime-comparison.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(
                '{"passed":true,"normal_pass_rate":1.0,"degraded_timeout_rate":1.0}',
                encoding="utf-8",
            )
            tools = OJGuardTools(root)
            incident = tools.workflow.prepare_demo(IncidentType.RUNTIME_REGRESSION)

            result = tools.judge_replay_submission(incident.incident_id)

            self.assertTrue(result["passed"])
            self.assertEqual(result["replay_mode"], "recorded_real_runner_evidence")
            self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_twelve_incident_tools_follow_approval_gates(self) -> None:
        with self.temporary_directory() as directory:
            tools = OJGuardTools(Path(directory))
            incident = tools.workflow.prepare_demo(IncidentType.NODE_DEGRADATION)
            incident_id = incident.incident_id

            self.assertTrue(tools.incident_list_signals(incident_id)["signals"])
            self.assertGreater(
                tools.submission_aggregate_verdicts(incident_id)["failure_rate_delta"], 0
            )
            self.assertTrue(tools.deployment_list_changes(incident_id)["changes"])
            self.assertEqual(tools.judge_replay_submission(incident_id)["state"], "PASSED")
            impact = tools.impact_calculate_scope(incident_id)
            self.assertGreater(impact["affected_submission_count"], 0)
            self.assertNotIn("submission_ids", impact)
            self.assertTrue(tools.rejudge_create_plan(incident_id)["batches"])

            with self.assertRaises(MCPToolError):
                tools.rejudge_execute_batch(incident_id, "control_canary")

            for action in (
                IncidentApprovalAction.APPROVE_REMEDIATION,
                IncidentApprovalAction.RUN_CANARY_REJUDGE,
            ):
                tools.workflow.record_approval(
                    incident_id,
                    action=action,
                    role_context="technical_approver",
                    actor="demo-operator",
                    decision=IncidentApprovalDecision.APPROVED,
                )
            control = tools.rejudge_execute_batch(incident_id, "control_canary")
            self.assertTrue(control["incident"]["canary_rejudge_passed"])

            with self.assertRaises(MCPToolError):
                tools.rejudge_execute_batch(incident_id, "bulk")
            tools.workflow.record_approval(
                incident_id,
                action=IncidentApprovalAction.RUN_BULK_REJUDGE,
                role_context="business_approver",
                actor="demo-operator",
                decision=IncidentApprovalDecision.APPROVED,
            )
            bulk = tools.rejudge_execute_batch(incident_id, "bulk")
            self.assertTrue(bulk["incident"]["rejudge_complete"])
            self.assertGreater(tools.score_calculate_changes(incident_id)["count"], 0)
            self.assertEqual(
                tools.verification_verify_incident(incident_id)["coverage_rate"], 1
            )
            self.assertEqual(
                tools.report_generate_incident_report(incident_id)["incident_id"],
                incident_id,
            )

    def test_server_exposes_exactly_twelve_bounded_incident_tools(self) -> None:
        from mcp_server.server import mcp

        names = {tool.name for tool in asyncio.run(mcp.list_tools())}
        self.assertEqual(
            names,
            {
                "incident.list_signals",
                "submission.aggregate_verdicts",
                "deployment.list_changes",
                "judge.replay_submission",
                "problem.audit_package",
                "impact.calculate_scope",
                "rejudge.create_plan",
                "rejudge.execute_batch",
                "rejudge.pause_batch",
                "score.calculate_changes",
                "verification.verify_incident",
                "report.generate_incident_report",
            },
        )


if __name__ == "__main__":
    unittest.main()
