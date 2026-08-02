from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.app.domain import IncidentStage, IncidentType, RejudgeBatchState
from backend.app.runner import DockerRunner
from backend.app.services.incident_reporting import build_incident_report
from backend.app.services.incident_state_machine import transition_incident
from backend.app.services.incident_workflow import (
    IncidentWorkflowError,
    IncidentWorkflowService,
)
from backend.app.services.java_regression_experiment import JavaRegressionExperiment
from backend.app.services.repository import SQLiteRepository
from backend.app.services.scenario_analysis import ScenarioAnalyzer
from backend.app.services.scenario_data import ScenarioDataGenerator

SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class MCPToolError(ValueError):
    """Safe, user-facing error raised by an OJGuard MCP tool."""


class OJGuardTools:
    """Approval-gated incident tools; no tool accepts shell commands or arbitrary paths."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.data_root = self.workspace_root / "data"
        self.packages_root = self.data_root / "packages"
        self.repository = SQLiteRepository(self.data_root / "ojguard.sqlite3")
        self.workflow = IncidentWorkflowService(self.repository)
        self.generator = ScenarioDataGenerator()
        self.analyzer = ScenarioAnalyzer()

    @staticmethod
    def _validate_id(value: str, label: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise MCPToolError(f"{label} contains unsupported characters")
        return value

    def _incident(self, incident_id: str):
        self._validate_id(incident_id, "incident_id")
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise MCPToolError("incident not found")
        return incident

    def _dataset(self, incident_id: str):
        incident = self._incident(incident_id)
        try:
            return incident, self.generator.generate(incident.profile.incident_type)
        except ValueError as exc:
            raise MCPToolError("incident type has no executable adapter") from exc

    def incident_list_signals(self, incident_id: str) -> dict[str, Any]:
        incident = self._incident(incident_id)
        signals = self.repository.list_incident_signals(incident_id)
        return {
            "incident_id": incident_id,
            "stage": incident.stage.value,
            "signals": [item.model_dump(mode="json") for item in signals],
        }

    def submission_aggregate_verdicts(self, incident_id: str) -> dict[str, Any]:
        _, dataset = self._dataset(incident_id)
        return self.analyzer.metrics(dataset).model_dump(mode="json")

    def deployment_list_changes(self, incident_id: str) -> dict[str, Any]:
        _, dataset = self._dataset(incident_id)
        return {
            "incident_id": incident_id,
            "changes": [item.model_dump(mode="json") for item in dataset.deployments],
        }

    def judge_replay_submission(
        self, incident_id: str, repetitions: int = 3
    ) -> dict[str, Any]:
        incident, _ = self._dataset(incident_id)
        if not 1 <= repetitions <= 5:
            raise MCPToolError("repetitions must be between 1 and 5")
        if incident.profile.incident_type == IncidentType.RUNTIME_REGRESSION:
            evidence_path = (
                self.workspace_root / "output" / "evidence" / "java-runtime-comparison.json"
            )
            if evidence_path.is_file():
                evidence_bytes = evidence_path.read_bytes()
                result = json.loads(evidence_bytes.decode("utf-8"))
                result.update(
                    {
                        "incident_id": incident_id,
                        "replay_mode": "recorded_real_runner_evidence",
                        "evidence_sha256": sha256(evidence_bytes).hexdigest(),
                        "requested_repetitions": repetitions,
                    }
                )
                return result
            runner = DockerRunner(
                packages_root=self.workspace_root / "demo" / "incidents",
                sessions_root=self.workspace_root / ".runtime" / "java-sessions",
            )
            result = JavaRegressionExperiment(runner).run(repetitions=repetitions)
            return result.model_dump(mode="json")

        experiments = self.repository.list_incident_experiments(incident_id)
        if not experiments:
            raise MCPToolError("incident has no comparison experiment")
        return experiments[-1].model_dump(mode="json")

    def problem_audit_package(self, package_id: str) -> dict[str, Any]:
        package_id = self._validate_id(package_id, "package_id")
        root = (self.packages_root / package_id / "original").resolve()
        if self.packages_root.resolve() not in root.parents or not root.is_dir():
            raise MCPToolError("package does not exist or has not been uploaded")
        manifest_path = root.parent / "manifest.json"
        if not manifest_path.is_file():
            raise MCPToolError("package manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        roles = {"statement": [], "validator": [], "checker": [], "solution": []}
        missing: list[str] = []
        for relative in manifest.get("files", []):
            target = (root / relative).resolve()
            if root not in target.parents or not target.is_file():
                missing.append(relative)
                continue
            lowered = relative.casefold()
            for role in roles:
                if role in lowered or role == "statement" and lowered.endswith((".md", ".pdf")):
                    roles[role].append(relative)
        return {
            "status": "SUCCESS" if not missing else "FAILED",
            "package_id": package_id,
            "manifest": manifest,
            "roles": roles,
            "missing_files": missing,
            "execution_performed": False,
        }

    def impact_calculate_scope(self, incident_id: str) -> dict[str, Any]:
        self._incident(incident_id)
        impacts = self.repository.list_impact_assessments(incident_id)
        if not impacts:
            raise MCPToolError("incident impact has not been calculated")
        impact = impacts[-1]
        return impact.model_dump(
            mode="json",
            exclude={"candidate_ids", "submission_ids"},
        ) | {
            "candidate_id_sample": impact.candidate_ids[:10],
            "submission_id_sample": impact.submission_ids[:10],
        }

    def rejudge_create_plan(self, incident_id: str) -> dict[str, Any]:
        self._incident(incident_id)
        plans = self.repository.list_remediation_plans(incident_id)
        if not plans:
            raise MCPToolError("incident remediation plan does not exist")
        return {
            "plan": plans[-1].model_dump(mode="json"),
            "batches": [
                item.model_dump(mode="json", exclude={"submission_ids"})
                for item in self.repository.list_rejudge_batches(incident_id)
            ],
        }

    def rejudge_execute_batch(self, incident_id: str, phase: str) -> dict[str, Any]:
        self._incident(incident_id)
        try:
            if phase == "control_canary":
                incident = self.workflow.execute_control_and_canary(incident_id)
            elif phase == "bulk":
                incident = self.workflow.execute_bulk(incident_id)
            else:
                raise MCPToolError("phase must be control_canary or bulk")
        except (IncidentWorkflowError, ValueError) as exc:
            raise MCPToolError(str(exc)) from exc
        return {
            "incident": incident.model_dump(mode="json"),
            "batches": [
                item.model_dump(mode="json")
                for item in self.repository.list_rejudge_batches(incident_id)
            ],
        }

    def rejudge_pause_batch(self, incident_id: str, batch_id: str) -> dict[str, Any]:
        incident = self._incident(incident_id)
        self._validate_id(batch_id, "batch_id")
        batches = self.repository.list_rejudge_batches(incident_id)
        batch = next((item for item in batches if item.id == batch_id), None)
        if batch is None:
            raise MCPToolError("batch not found in incident")
        if batch.state == RejudgeBatchState.COMPLETED:
            raise MCPToolError("completed batch cannot be paused")
        updated = batch.model_copy(deep=True)
        updated.state = RejudgeBatchState.PAUSED
        updated.updated_at = datetime.now(UTC)
        self.repository.save_rejudge_batch(updated)
        if incident.stage in {IncidentStage.EXECUTING, IncidentStage.REJUDGING}:
            incident = transition_incident(incident, IncidentStage.PAUSED)
            self.repository.save_incident(incident)
        return updated.model_dump(mode="json")

    def score_calculate_changes(self, incident_id: str) -> dict[str, Any]:
        self._incident(incident_id)
        changes = self.repository.list_score_changes(incident_id)
        return {
            "incident_id": incident_id,
            "count": len(changes),
            "sample_changes": [item.model_dump(mode="json") for item in changes[:20]],
        }

    def verification_verify_incident(self, incident_id: str) -> dict[str, Any]:
        self._incident(incident_id)
        existing = self.repository.list_incident_verifications(incident_id)
        if existing:
            return existing[-1].model_dump(mode="json")
        try:
            self.workflow.verify(incident_id)
        except (IncidentWorkflowError, ValueError) as exc:
            raise MCPToolError(str(exc)) from exc
        return self.repository.list_incident_verifications(incident_id)[-1].model_dump(
            mode="json"
        )

    def report_generate_incident_report(self, incident_id: str) -> dict[str, Any]:
        incident = self._incident(incident_id)
        return build_incident_report(self.repository, incident).model_dump(mode="json")
