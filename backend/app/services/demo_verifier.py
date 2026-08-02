from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel

from backend.app.domain import (
    AgentEvent,
    ConfidenceClass,
    Evidence,
    Finding,
    RunStage,
    Severity,
    TaskContext,
)
from backend.app.domain.release import ReleaseGateResult
from backend.app.runner import ExecutionStatus, ResourceLimits
from backend.app.runner.models import CompileResult, ExecutionResult
from backend.app.services.baseline_audit import BaselineAuditReport, BaselineAuditor
from backend.app.services.evidence import EvidenceStore
from backend.app.services.release_gate import ReleaseGate
from backend.app.services.repository import SQLiteRepository
from backend.app.services.state_machine import transition
from backend.app.services.trace import TraceWriter


class Runner(Protocol):
    def compile_cpp(
        self, *, source_relative_path: str, limits: ResourceLimits | None = None
    ) -> tuple[CompileResult, Path]: ...

    def execute(
        self, *, session: Path, input_payload: bytes, limits: ResourceLimits | None = None
    ) -> ExecutionResult: ...

    def probe_checker(
        self,
        *,
        session: Path,
        answer_payload: bytes,
        contestant_output: bytes,
        limits: ResourceLimits | None = None,
    ) -> ExecutionResult: ...


class DemoAuditResult(BaseModel):
    context: TaskContext
    baseline: BaselineAuditReport
    findings: list[Finding]
    evidence: list[Evidence]
    release_gate: ReleaseGateResult


class DemoVerifier:
    """Reproduce the four intentionally seeded defects in the bundled demonstration."""

    TOOL_VERSION = "ojguard-demo-verifier/0.1.0"

    def __init__(
        self,
        *,
        runner: Runner,
        repository: SQLiteRepository,
        evidence_store: EvidenceStore,
        trace_writer: TraceWriter,
    ) -> None:
        self.runner = runner
        self.repository = repository
        self.evidence_store = evidence_store
        self.trace_writer = trace_writer

    def audit(
        self,
        package_root: Path,
        *,
        package_id: str = "maximum_segment_score",
        run_id: str | None = None,
    ) -> DemoAuditResult:
        suffix = uuid4().hex[:10].upper()
        run_id = run_id or f"RUN-DEMO-{suffix}"
        context = TaskContext(task_id=f"TASK-DEMO-{suffix}", package_id=package_id, run_id=run_id)
        self.repository.save_run(context)
        self._event(context, "judge-manager", "run.created", "Demo audit run created")

        context = self._advance(context, RunStage.BASELINE_VALIDATING)
        baseline = BaselineAuditor().audit(
            package_root.resolve(), package_id=package_id, run_id=run_id
        )
        context.active_hypothesis_ids = [item.id for item in baseline.hypotheses]
        self.repository.save_run(context)
        self._event(
            context,
            "specification-auditor",
            "baseline.completed",
            f"Generated {len(baseline.hypotheses)} deterministic hypotheses",
        )

        context = self._advance(context, RunStage.ANALYZING)
        context = self._advance(context, RunStage.TESTING)
        evidence = self._run_probes(package_id=package_id, run_id=run_id)
        for item in evidence:
            self.repository.save_evidence(item)
        context.evidence_ids = [item.id for item in evidence]
        self.repository.save_run(context)
        self._event(
            context,
            "adversarial-test-engineer",
            "probes.completed",
            "Reproduced overflow, missing coverage, Validator mismatch, and Checker bypass",
            [item.id for item in evidence],
        )

        findings = self._build_findings(package_id=package_id, run_id=run_id, evidence=evidence)
        for finding in findings:
            self.repository.save_finding(finding)
        context.confirmed_finding_ids = [item.id for item in findings]
        self.repository.save_run(context)

        context = self._advance(context, RunStage.EVIDENCE_REVIEW)
        gate = ReleaseGate().evaluate(
            findings=findings,
            evidence=evidence,
            required_checks_passed=True,
        )
        context = self._advance(context, RunStage.BLOCKED)
        self._event(
            context,
            "judge-manager",
            "release_gate.blocked",
            f"Release gate decision: {gate.decision.value}",
            gate.blocking_finding_ids,
        )
        return DemoAuditResult(
            context=context,
            baseline=baseline,
            findings=findings,
            evidence=evidence,
            release_gate=gate,
        )

    def _run_probes(self, *, package_id: str, run_id: str) -> list[Evidence]:
        overflow_input = f"3000\n{' '.join(['1000000'] * 3000)}\n".encode()
        counterexample = b"3\n5 -100 6\n"

        oracle_overflow = self._compile_and_run(
            "maximum_segment_score/solutions/oracle.cpp", overflow_input
        )
        reference_overflow = self._compile_and_run(
            "maximum_segment_score/solutions/reference.cpp", overflow_input
        )
        if oracle_overflow.stdout.strip() == reference_overflow.stdout.strip():
            raise RuntimeError("overflow hypothesis was not reproduced")
        overflow = self._write_probe(
            evidence_id=f"E-OVERFLOW-{run_id}",
            package_id=package_id,
            run_id=run_id,
            relative_path="probes/integer-overflow.json",
            evidence_type="differential_execution",
            producer="solution-analyst",
            payload={
                "input": overflow_input.decode(),
                "oracle": oracle_overflow.model_dump(mode="json"),
                "reference": reference_overflow.model_dump(mode="json"),
                "assertion": "oracle.stdout != reference.stdout",
            },
            inputs=["solutions/oracle.cpp", "solutions/reference.cpp", "generated:overflow"],
            outputs=[oracle_overflow.stdout.strip(), reference_overflow.stdout.strip()],
        )

        oracle_negative = self._compile_and_run(
            "maximum_segment_score/solutions/oracle.cpp", counterexample
        )
        wrong_negative = self._compile_and_run(
            "maximum_segment_score/solutions/wrong_positive_sum.cpp", counterexample
        )
        if oracle_negative.stdout.strip() == wrong_negative.stdout.strip():
            raise RuntimeError("coverage hypothesis was not reproduced")
        coverage = self._write_probe(
            evidence_id=f"E-COVERAGE-{run_id}",
            package_id=package_id,
            run_id=run_id,
            relative_path="probes/missing-negative-case.json",
            evidence_type="wrong_solution_counterexample",
            producer="adversarial-test-engineer",
            payload={
                "input": counterexample.decode(),
                "oracle": oracle_negative.model_dump(mode="json"),
                "wrong_solution": wrong_negative.model_dump(mode="json"),
                "assertion": "oracle.stdout != wrong_solution.stdout",
            },
            inputs=["solutions/oracle.cpp", "solutions/wrong_positive_sum.cpp"],
            outputs=[oracle_negative.stdout.strip(), wrong_negative.stdout.strip()],
        )

        validator = self._compile("maximum_segment_score/validators/validator.cpp")
        validator_result = self.runner.execute(
            session=validator[1], input_payload=b"1\n1000000000\n"
        )
        if validator_result.exit_code != 1:
            raise RuntimeError("Validator mismatch hypothesis was not reproduced")
        spec = self._write_probe(
            evidence_id=f"E-SPEC-{run_id}",
            package_id=package_id,
            run_id=run_id,
            relative_path="probes/validator-boundary.json",
            evidence_type="contract_boundary_execution",
            producer="specification-auditor",
            payload={
                "input": "1\n1000000000\n",
                "manifest_allows": True,
                "validator": validator_result.model_dump(mode="json"),
                "assertion": "manifest allows input and Validator rejects it",
            },
            inputs=["problem.yaml", "validators/validator.cpp"],
            outputs=[f"exit_code={validator_result.exit_code}"],
        )

        checker = self._compile("maximum_segment_score/checker/checker.cpp")
        checker_result = self.runner.probe_checker(
            session=checker[1],
            answer_payload=b"15\n",
            contestant_output=b"15\nTHIS_OUTPUT_MUST_BE_REJECTED\n",
        )
        if checker_result.status is not ExecutionStatus.OK or checker_result.exit_code != 0:
            raise RuntimeError("Checker bypass hypothesis was not reproduced")
        checker_evidence = self._write_probe(
            evidence_id=f"E-CHECKER-{run_id}",
            package_id=package_id,
            run_id=run_id,
            relative_path="probes/checker-trailing-output.json",
            evidence_type="checker_adversarial_execution",
            producer="checker-auditor",
            payload={
                "answer": "15\n",
                "contestant_output": "15\nTHIS_OUTPUT_MUST_BE_REJECTED\n",
                "checker": checker_result.model_dump(mode="json"),
                "assertion": "malformed trailing output is accepted",
            },
            inputs=["checker/checker.cpp", "generated:trailing-token"],
            outputs=[f"exit_code={checker_result.exit_code}"],
        )
        return [spec, overflow, coverage, checker_evidence]

    def _compile(self, source: str) -> tuple[CompileResult, Path]:
        result, session = self.runner.compile_cpp(source_relative_path=source)
        if result.status is not ExecutionStatus.OK:
            raise RuntimeError(f"compile failed for {source}: {result.compiler_stderr}")
        return result, session

    def _compile_and_run(self, source: str, payload: bytes) -> ExecutionResult:
        _, session = self._compile(source)
        result = self.runner.execute(
            session=session,
            input_payload=payload,
            limits=ResourceLimits(time_limit_ms=2_000),
        )
        if result.status is not ExecutionStatus.OK:
            raise RuntimeError(f"execution failed for {source}: {result.model_dump()}")
        return result

    def _write_probe(
        self,
        *,
        evidence_id: str,
        package_id: str,
        run_id: str,
        relative_path: str,
        evidence_type: str,
        producer: str,
        payload: dict[str, Any],
        inputs: list[str],
        outputs: list[str],
    ) -> Evidence:
        return self.evidence_store.write_json(
            evidence_id=evidence_id,
            package_id=package_id,
            run_id=run_id,
            evidence_type=evidence_type,
            producer=producer,
            relative_path=relative_path,
            payload=payload,
            tool_version=self.TOOL_VERSION,
            inputs=inputs,
            outputs=outputs,
        )

    @staticmethod
    def _build_findings(
        *, package_id: str, run_id: str, evidence: list[Evidence]
    ) -> list[Finding]:
        evidence_ids = {item.type: item.id for item in evidence}
        rows = [
            (
                "SPEC",
                "specification-auditor",
                "statement_validator_mismatch",
                Severity.HIGH,
                ConfidenceClass.CONFIRMED,
                "Validator rejects a boundary value explicitly allowed by the manifest.",
                "H-SPEC-001",
                evidence_ids["contract_boundary_execution"],
            ),
            (
                "OVERFLOW",
                "solution-analyst",
                "integer_overflow",
                Severity.CRITICAL,
                ConfidenceClass.CONFIRMED,
                "Reference solution diverges from the 64-bit oracle on an in-range extreme case.",
                "H-OVERFLOW-001",
                evidence_ids["differential_execution"],
            ),
            (
                "COVERAGE",
                "adversarial-test-engineer",
                "missing_negative_cases",
                Severity.HIGH,
                ConfidenceClass.CONFIRMED,
                "A negative-value counterexample kills the bundled wrong solution but is absent from tests.",
                "H-COVERAGE-001",
                evidence_ids["wrong_solution_counterexample"],
            ),
            (
                "CHECKER",
                "checker-auditor",
                "checker_trailing_output",
                Severity.CRITICAL,
                ConfidenceClass.CONFIRMED,
                "Checker accepts contestant output containing an invalid trailing token.",
                "H-CHECKER-001",
                evidence_ids["checker_adversarial_execution"],
            ),
        ]
        return [
            Finding(
                id=f"F-{label}-{run_id}",
                package_id=package_id,
                run_id=run_id,
                source_agent=agent,
                category=category,
                severity=severity,
                confidence_class=confidence,
                description=description,
                hypothesis_id=hypothesis,
                evidence_ids=[evidence_id],
                replay_action="replay_demo_probe",
            )
            for label, agent, category, severity, confidence, description, hypothesis, evidence_id in rows
        ]

    def _advance(self, context: TaskContext, stage: RunStage) -> TaskContext:
        updated = transition(context, stage)
        self.repository.save_run(updated)
        self._event(
            updated,
            "judge-manager",
            "run.stage_changed",
            f"Run entered {stage.value}",
        )
        return updated

    def _event(
        self,
        context: TaskContext,
        agent: str,
        event_type: str,
        summary: str,
        artifact_ids: list[str] | None = None,
    ) -> None:
        event = AgentEvent(
            id=f"EVT-{uuid4().hex.upper()}",
            task_id=context.task_id,
            run_id=context.run_id,
            agent=agent,
            event_type=event_type,
            summary=summary,
            artifact_ids=artifact_ids or [],
        )
        self.repository.append_event(event)
        self.trace_writer.append(context.package_id, event)
