from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.runner import DockerRunner, ExecutionStatus, ResourceLimits
from backend.app.services.baseline_audit import BaselineAuditor
from backend.app.services.demo_verifier import DemoVerifier
from backend.app.services.evidence import EvidenceStore
from backend.app.services.patch_workflow import PatchWorkflow
from backend.app.services.repository import SQLiteRepository
from backend.app.services.trace import TraceWriter


SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class MCPToolError(ValueError):
    """Safe, user-facing error raised by an OJGuard MCP tool."""


class OJGuardTools:
    """Application boundary used by MCP and directly unit-testable without a transport."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.data_root = self.workspace_root / "data"
        self.packages_root = self.data_root / "packages"
        self.artifacts_root = self.workspace_root / "artifacts"
        self.repository = SQLiteRepository(self.data_root / "ojguard.sqlite3")
        self.evidence_store = EvidenceStore(self.artifacts_root)
        self.trace_writer = TraceWriter(self.artifacts_root)

    @staticmethod
    def _validate_id(value: str, label: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise MCPToolError(f"{label} contains unsupported characters")
        return value

    def _package_root(self, package_id: str) -> Path:
        package_id = self._validate_id(package_id, "package_id")
        root = (self.packages_root / package_id / "original").resolve()
        packages_root = self.packages_root.resolve()
        if packages_root not in root.parents or not root.is_dir():
            raise MCPToolError("package does not exist or has not been uploaded")
        return root

    def inspect_package(self, package_id: str) -> dict[str, Any]:
        """Inspect a previously uploaded package without executing its contents."""
        package_id = self._validate_id(package_id, "package_id")
        package_root = self._package_root(package_id)
        manifest_path = package_root.parent / "manifest.json"
        if not manifest_path.is_file():
            raise MCPToolError("package manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing: list[str] = []
        roles: dict[str, list[str]] = {
            "statement": [],
            "validator": [],
            "checker": [],
            "solution": [],
            "configuration": [],
        }
        for relative in manifest.get("files", []):
            target = (package_root / relative).resolve()
            if package_root not in target.parents or not target.is_file():
                missing.append(relative)
                continue
            lowered = relative.casefold()
            if "statement" in lowered or lowered.endswith((".pdf", ".md")):
                roles["statement"].append(relative)
            if "validator" in lowered:
                roles["validator"].append(relative)
            if "checker" in lowered:
                roles["checker"].append(relative)
            if "solution" in lowered:
                roles["solution"].append(relative)
            if lowered.endswith((".yaml", ".yml", ".json", ".ini")):
                roles["configuration"].append(relative)
        return {
            "status": "SUCCESS" if not missing else "FAILED",
            "package_id": package_id,
            "manifest": manifest,
            "roles": roles,
            "missing_files": missing,
            "execution_performed": False,
        }

    def baseline_audit(self, package_id: str, run_id: str) -> dict[str, Any]:
        """Generate deterministic hypotheses from a package manifest and source files."""
        self._validate_id(run_id, "run_id")
        report = BaselineAuditor().audit(
            self._package_root(package_id), package_id=package_id, run_id=run_id
        )
        return report.model_dump(mode="json")

    def run_cpp_probe(
        self,
        package_id: str,
        run_id: str,
        source_path: str,
        input_data: str,
        time_limit_ms: int = 1000,
        memory_limit_mb: int = 256,
    ) -> dict[str, Any]:
        """Compile and run one declared C++ artifact in the locked-down Docker Runner."""
        self._validate_id(package_id, "package_id")
        self._validate_id(run_id, "run_id")
        encoded = input_data.encode("utf-8")
        if len(encoded) > 1_048_576:
            raise MCPToolError("input_data exceeds the 1 MiB MCP probe limit")
        runner = DockerRunner(
            packages_root=self.packages_root,
            sessions_root=self.data_root / "runner-sessions",
        )
        resolved_source = f"{package_id}/original/{source_path}"
        compile_result, session = runner.compile_cpp(source_relative_path=resolved_source)
        response: dict[str, Any] = {
            "package_id": package_id,
            "run_id": run_id,
            "source_path": source_path,
            "compile": compile_result.model_dump(mode="json"),
            "execution": None,
        }
        if compile_result.status is ExecutionStatus.OK:
            execution = runner.execute(
                session=session,
                input_payload=encoded,
                limits=ResourceLimits(
                    time_limit_ms=time_limit_ms,
                    memory_limit_mb=memory_limit_mb,
                ),
            )
            response["execution"] = execution.model_dump(mode="json")
        return response

    def audit_bundled_demo(self) -> dict[str, Any]:
        """Run the complete four-defect demonstration and persist its evidence chain."""
        verifier = DemoVerifier(
            runner=DockerRunner(
                packages_root=self.workspace_root / "demo",
                sessions_root=self.data_root / "runner-sessions",
            ),
            repository=self.repository,
            evidence_store=self.evidence_store,
            trace_writer=self.trace_writer,
        )
        result = verifier.audit(self.workspace_root / "demo" / "maximum_segment_score")
        return result.model_dump(mode="json")

    def get_run_bundle(self, run_id: str) -> dict[str, Any]:
        """Return run state, findings, evidence, approvals, and trace events."""
        self._validate_id(run_id, "run_id")
        context = self.repository.get_run(run_id)
        if context is None:
            raise MCPToolError("run not found")
        return {
            "context": context.model_dump(mode="json"),
            "findings": [
                item.model_dump(mode="json") for item in self.repository.list_findings(run_id)
            ],
            "evidence": [
                item.model_dump(mode="json") for item in self.repository.list_evidence(run_id)
            ],
            "approvals": [
                item.model_dump(mode="json") for item in self.repository.list_approvals(run_id)
            ],
            "patches": [
                item.model_dump(mode="json") for item in self.repository.list_patches(run_id)
            ],
            "events": [
                item.model_dump(mode="json") for item in self.repository.list_events(run_id)
            ],
        }

    def verify_run_evidence(self, run_id: str) -> dict[str, Any]:
        """Re-hash every persisted evidence artifact and report integrity failures."""
        self._validate_id(run_id, "run_id")
        if self.repository.get_run(run_id) is None:
            raise MCPToolError("run not found")
        evidence = self.repository.list_evidence(run_id)
        checks = [{"evidence_id": item.id, "valid": self.evidence_store.verify(item)} for item in evidence]
        return {
            "run_id": run_id,
            "status": "SUCCESS" if checks and all(item["valid"] for item in checks) else "FAILED",
            "checks": checks,
        }

    def propose_demo_patch(self, run_id: str) -> dict[str, Any]:
        """Generate a candidate Diff only; this tool cannot approve or apply it."""
        self._validate_id(run_id, "run_id")
        workflow = PatchWorkflow(
            repository=self.repository,
            workspaces_root=self.data_root / "workspaces",
        )
        patch = workflow.propose_demo_patch(
            run_id=run_id,
            original_root=self.workspace_root / "demo" / "maximum_segment_score",
        )
        return patch.model_dump(mode="json")

    def run_demo_regression(self, patch_id: str) -> dict[str, Any]:
        """Run deterministic regression after a human has approved and applied a patch."""
        self._validate_id(patch_id, "patch_id")
        workflow = PatchWorkflow(
            repository=self.repository,
            workspaces_root=self.data_root / "workspaces",
        )
        return workflow.run_demo_regression(patch_id=patch_id).model_dump(mode="json")
