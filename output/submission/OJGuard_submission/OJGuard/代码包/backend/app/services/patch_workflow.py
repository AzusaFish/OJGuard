from __future__ import annotations

import difflib
import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from backend.app.domain import (
    ApprovalAction,
    ApprovalRecord,
    ApprovalState,
    PatchCandidate,
    PatchFileChange,
    PatchRisk,
    PatchStatus,
    RunStage,
)
from backend.app.runner import DockerRunner, ExecutionStatus, ResourceLimits
from backend.app.services.repository import SQLiteRepository
from backend.app.services.state_machine import transition


class PatchWorkflowError(ValueError):
    """Raised when approval, integrity, or patch workflow preconditions fail."""


class RegressionCheck(BaseModel):
    name: str
    passed: bool
    details: dict[str, str | int | bool | None]


class RegressionResult(BaseModel):
    run_id: str
    patch_id: str
    passed: bool
    checks: list[RegressionCheck]


class PatchWorkflow:
    """Enforce candidate-only generation, first approval, regression, and final approval."""

    def __init__(self, *, repository: SQLiteRepository, workspaces_root: Path) -> None:
        self.repository = repository
        self.workspaces_root = workspaces_root.resolve()
        self.workspaces_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_file(root: Path, relative_path: str, *, must_exist: bool = True) -> Path:
        target = (root / relative_path).resolve()
        if root not in target.parents or (must_exist and not target.is_file()):
            raise PatchWorkflowError(f"unsafe or missing patch target: {relative_path}")
        return target

    def propose_demo_patch(self, *, run_id: str, original_root: Path) -> PatchCandidate:
        context = self.repository.get_run(run_id)
        if context is None or context.stage is not RunStage.BLOCKED:
            raise PatchWorkflowError("run must exist and be BLOCKED before proposing a patch")
        if self.repository.list_patches(run_id):
            raise PatchWorkflowError("a patch candidate already exists for this run")
        original_root = original_root.resolve()
        changes: list[PatchFileChange] = []

        replacements = {
            "solutions/reference.cpp": [
                ("int best = std::numeric_limits<int>::lowest();", "long long best = std::numeric_limits<long long>::lowest();"),
                ("int current = 0;", "long long current = 0;"),
                ("int value;\n        std::cin >> value;", "long long value;\n        std::cin >> value;"),
            ],
            "validators/validator.cpp": [
                ("std::llabs(value) > 1000000LL", "std::llabs(value) > 1000000000LL")
            ],
            "checker/checker.cpp": [
                (
                    "// Intentional defect: trailing contestant output is not rejected.\n    return expected == actual ? 0 : 1;",
                    "std::string trailing;\n    if (output_file >> trailing) return 1;\n    return expected == actual ? 0 : 1;",
                )
            ],
        }
        for relative, pairs in replacements.items():
            source = self._safe_file(original_root, relative)
            before = source.read_text(encoding="utf-8")
            after = before
            for old, new in pairs:
                if old not in after:
                    raise PatchWorkflowError(f"expected patch context not found in {relative}")
                after = after.replace(old, new, 1)
            changes.append(self._change(relative, before, after))

        changes.extend(
            [
                self._change("tests/002.in", None, "3\n5 -100 6\n"),
                self._change("tests/002.ans", None, "6\n"),
            ]
        )
        patch_id = f"PATCH-{uuid4().hex[:12].upper()}"
        patch = PatchCandidate(
            id=patch_id,
            package_id=context.package_id,
            run_id=run_id,
            title="Fix four deterministic Demo defects",
            rationale=(
                "Use 64-bit accumulators, align Validator bounds, reject Checker trailing output, "
                "and preserve the discovered negative counterexample as a regression test."
            ),
            risk=PatchRisk.MEDIUM,
            finding_ids=context.confirmed_finding_ids,
            regression_scope=[
                "original tests",
                "overflow differential",
                "negative wrong-solution kill",
                "Validator boundary",
                "Checker trailing-output attack",
            ],
            changes=changes,
        )
        self.repository.save_patch(patch)
        updated = transition(context, RunStage.PATCH_PENDING_APPROVAL)
        updated.approval_state = ApprovalState.PENDING
        self.repository.save_run(updated)
        return patch

    def approve_and_apply(
        self,
        *,
        patch_id: str,
        original_root: Path,
        actor: str,
        reason: str | None = None,
    ) -> PatchCandidate:
        patch = self.repository.get_patch(patch_id)
        if patch is None or patch.status is not PatchStatus.CANDIDATE:
            raise PatchWorkflowError("patch candidate is missing or no longer approvable")
        context = self.repository.get_run(patch.run_id)
        if context is None or context.stage is not RunStage.PATCH_PENDING_APPROVAL:
            raise PatchWorkflowError("run is not waiting for first approval")
        original_root = original_root.resolve()
        working_root = (self.workspaces_root / patch.run_id).resolve()
        if self.workspaces_root not in working_root.parents or working_root.exists():
            raise PatchWorkflowError("working copy already exists or path is unsafe")

        for change in patch.changes:
            if change.before_sha256 is None:
                continue
            current = self._safe_file(original_root, change.relative_path).read_text(encoding="utf-8")
            if self._sha(current) != change.before_sha256:
                raise PatchWorkflowError(f"original changed after proposal: {change.relative_path}")

        shutil.copytree(original_root, working_root)
        for change in patch.changes:
            target = self._safe_file(working_root, change.relative_path, must_exist=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.after_content, encoding="utf-8", newline="")
            if self._sha(target.read_text(encoding="utf-8")) != change.after_sha256:
                raise PatchWorkflowError(f"post-write hash mismatch: {change.relative_path}")

        patch.status = PatchStatus.APPLIED
        patch.working_copy_path = working_root.relative_to(self.workspaces_root).as_posix()
        patch.updated_at = datetime.now(UTC)
        self.repository.save_patch(patch)
        approval = ApprovalRecord(
            id=f"APPROVAL-{uuid4().hex.upper()}",
            run_id=patch.run_id,
            action=ApprovalAction.APPLY_PATCH_TO_WORKING_COPY,
            state=ApprovalState.APPROVED,
            actor=actor,
            target_id=patch.id,
            reason=reason,
            before_sha256=self._aggregate_before_hash(patch),
            after_sha256=self._aggregate_after_hash(patch),
        )
        self.repository.save_approval(approval)
        updated = transition(context, RunStage.REVALIDATING)
        updated.approval_state = ApprovalState.APPROVED
        self.repository.save_run(updated)
        return patch

    def reject_patch(self, *, patch_id: str, actor: str, reason: str) -> PatchCandidate:
        patch = self.repository.get_patch(patch_id)
        if patch is None or patch.status is not PatchStatus.CANDIDATE:
            raise PatchWorkflowError("patch candidate is missing or no longer rejectable")
        context = self.repository.get_run(patch.run_id)
        if context is None or context.stage is not RunStage.PATCH_PENDING_APPROVAL:
            raise PatchWorkflowError("run is not waiting for first approval")
        patch.status = PatchStatus.REJECTED
        patch.updated_at = datetime.now(UTC)
        self.repository.save_patch(patch)
        self.repository.save_approval(
            ApprovalRecord(
                id=f"APPROVAL-{uuid4().hex.upper()}",
                run_id=patch.run_id,
                action=ApprovalAction.APPLY_PATCH_TO_WORKING_COPY,
                state=ApprovalState.REJECTED,
                actor=actor,
                target_id=patch.id,
                reason=reason,
            )
        )
        updated = transition(context, RunStage.BLOCKED)
        updated.approval_state = ApprovalState.REJECTED
        self.repository.save_run(updated)
        return patch

    def run_demo_regression(self, *, patch_id: str) -> RegressionResult:
        patch = self.repository.get_patch(patch_id)
        if patch is None or patch.status is not PatchStatus.APPLIED or not patch.working_copy_path:
            raise PatchWorkflowError("an applied patch is required before regression")
        context = self.repository.get_run(patch.run_id)
        if context is None or context.stage is not RunStage.REVALIDATING:
            raise PatchWorkflowError("run is not in revalidation")
        runner = DockerRunner(
            packages_root=self.workspaces_root,
            sessions_root=self.workspaces_root.parent / "runner-sessions",
        )
        prefix = patch.working_copy_path
        overflow = f"3000\n{' '.join(['1000000'] * 3000)}\n".encode()
        negative = b"3\n5 -100 6\n"
        oracle_overflow = self._run(runner, f"{prefix}/solutions/oracle.cpp", overflow)
        reference_overflow = self._run(runner, f"{prefix}/solutions/reference.cpp", overflow)
        oracle_negative = self._run(runner, f"{prefix}/solutions/oracle.cpp", negative)
        wrong_negative = self._run(
            runner, f"{prefix}/solutions/wrong_positive_sum.cpp", negative
        )
        validator_compile, validator_session = runner.compile_cpp(
            source_relative_path=f"{prefix}/validators/validator.cpp"
        )
        validator = runner.execute(
            session=validator_session, input_payload=b"1\n1000000000\n"
        )
        checker_compile, checker_session = runner.compile_cpp(
            source_relative_path=f"{prefix}/checker/checker.cpp"
        )
        checker = runner.probe_checker(
            session=checker_session,
            answer_payload=b"15\n",
            contestant_output=b"15\nTHIS_OUTPUT_MUST_BE_REJECTED\n",
        )
        test_input = self._safe_file(self.workspaces_root / prefix, "tests/002.in").read_bytes()
        test_answer = self._safe_file(self.workspaces_root / prefix, "tests/002.ans").read_text(
            encoding="utf-8"
        ).strip()
        reference_negative = self._run(
            runner, f"{prefix}/solutions/reference.cpp", test_input
        )
        checks = [
            RegressionCheck(
                name="overflow_fixed",
                passed=oracle_overflow == reference_overflow == "3000000000",
                details={"oracle": oracle_overflow, "reference": reference_overflow},
            ),
            RegressionCheck(
                name="wrong_solution_killed",
                passed=oracle_negative != wrong_negative,
                details={"oracle": oracle_negative, "wrong_solution": wrong_negative},
            ),
            RegressionCheck(
                name="validator_boundary_accepted",
                passed=validator_compile.status is ExecutionStatus.OK and validator.exit_code == 0,
                details={"exit_code": validator.exit_code},
            ),
            RegressionCheck(
                name="checker_trailing_output_rejected",
                passed=checker_compile.status is ExecutionStatus.OK and checker.exit_code != 0,
                details={"exit_code": checker.exit_code},
            ),
            RegressionCheck(
                name="counterexample_preserved",
                passed=reference_negative == test_answer == "6",
                details={"reference": reference_negative, "answer": test_answer},
            ),
        ]
        result = RegressionResult(
            run_id=patch.run_id,
            patch_id=patch.id,
            passed=all(item.passed for item in checks),
            checks=checks,
        )
        patch.status = (
            PatchStatus.REGRESSION_PASSED if result.passed else PatchStatus.REGRESSION_FAILED
        )
        patch.updated_at = datetime.now(UTC)
        self.repository.save_patch(patch)
        if not result.passed:
            updated = transition(context, RunStage.BLOCKED)
            self.repository.save_run(updated)
        return result

    def confirm_release(
        self, *, patch_id: str, actor: str, reason: str | None = None
    ) -> ApprovalRecord:
        patch = self.repository.get_patch(patch_id)
        if patch is None or patch.status is not PatchStatus.REGRESSION_PASSED:
            raise PatchWorkflowError("successful regression is required for final approval")
        context = self.repository.get_run(patch.run_id)
        if context is None or context.stage is not RunStage.REVALIDATING:
            raise PatchWorkflowError("run is not awaiting final confirmation")
        approval = ApprovalRecord(
            id=f"APPROVAL-{uuid4().hex.upper()}",
            run_id=patch.run_id,
            action=ApprovalAction.CONFIRM_RELEASE_CANDIDATE,
            state=ApprovalState.APPROVED,
            actor=actor,
            target_id=patch.id,
            reason=reason,
            after_sha256=self._aggregate_after_hash(patch),
        )
        patch.status = PatchStatus.RELEASE_CONFIRMED
        patch.updated_at = datetime.now(UTC)
        self.repository.save_patch(patch)
        self.repository.save_approval(approval)
        updated = transition(context, RunStage.READY_FOR_RELEASE)
        updated.approval_state = ApprovalState.APPROVED
        self.repository.save_run(updated)
        return approval

    @classmethod
    def _change(cls, relative_path: str, before: str | None, after: str) -> PatchFileChange:
        before_lines = [] if before is None else before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
        return PatchFileChange(
            relative_path=relative_path,
            before_sha256=cls._sha(before) if before is not None else None,
            after_sha256=cls._sha(after),
            unified_diff=diff,
            after_content=after,
        )

    @staticmethod
    def _run(runner: DockerRunner, source: str, payload: bytes) -> str:
        compile_result, session = runner.compile_cpp(source_relative_path=source)
        if compile_result.status is not ExecutionStatus.OK:
            raise PatchWorkflowError(f"regression compile failed: {source}")
        execution = runner.execute(
            session=session,
            input_payload=payload,
            limits=ResourceLimits(time_limit_ms=2_000),
        )
        if execution.status is not ExecutionStatus.OK:
            raise PatchWorkflowError(f"regression execution failed: {source}")
        return execution.stdout.strip()

    @staticmethod
    def _aggregate_before_hash(patch: PatchCandidate) -> str:
        payload = "\n".join(item.before_sha256 or "NEW" for item in patch.changes)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _aggregate_after_hash(patch: PatchCandidate) -> str:
        payload = "\n".join(item.after_sha256 for item in patch.changes)
        return hashlib.sha256(payload.encode()).hexdigest()
