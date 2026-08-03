from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from backend.app.runner import (
    DockerRunner,
    ExecutionResult,
    ExecutionStatus,
    JavaRuntimeProfile,
    ResourceLimits,
)


class JavaRuntimeComparison(BaseModel):
    """Reproducible control experiment for the Java runtime incident."""

    source: str
    iterations: int = Field(ge=1)
    time_limit_ms: int = Field(ge=50)
    normal_runs: list[ExecutionResult]
    degraded_runs: list[ExecutionResult]
    normal_pass_rate: float = Field(ge=0, le=1)
    degraded_timeout_rate: float = Field(ge=0, le=1)
    conclusion: str
    passed: bool


class JavaRegressionExperiment:
    def __init__(self, runner: DockerRunner) -> None:
        self.runner = runner

    def run(
        self,
        *,
        source_relative_path: str = "runtime_regression/ControlWorkload.java",
        iterations: int = 12_000_000,
        time_limit_ms: int = 80,
        repetitions: int = 3,
    ) -> JavaRuntimeComparison:
        if repetitions < 1:
            raise ValueError("repetitions must be positive")

        compile_result, session = self.runner.compile_java(
            source_relative_path=source_relative_path
        )
        if compile_result.status != ExecutionStatus.OK:
            raise RuntimeError(f"control workload failed to compile: {compile_result.compiler_stderr}")

        limits = ResourceLimits(time_limit_ms=time_limit_ms, memory_limit_mb=192, cpus=1)
        payload = f"{iterations}\n".encode()
        normal_runs = [
            self.runner.execute_java(
                session=session,
                main_class=Path(source_relative_path).stem,
                input_payload=payload,
                profile=JavaRuntimeProfile.NORMAL,
                limits=limits,
            )
            for _ in range(repetitions)
        ]
        degraded_runs = [
            self.runner.execute_java(
                session=session,
                main_class=Path(source_relative_path).stem,
                input_payload=payload,
                profile=JavaRuntimeProfile.DEGRADED,
                limits=limits,
            )
            for _ in range(repetitions)
        ]

        normal_pass_rate = sum(run.status == ExecutionStatus.OK for run in normal_runs) / repetitions
        degraded_timeout_rate = (
            sum(run.status == ExecutionStatus.TIME_LIMIT_EXCEEDED for run in degraded_runs)
            / repetitions
        )
        passed = normal_pass_rate == 1 and degraded_timeout_rate == 1
        conclusion = (
            "同一源码和资源限制下，正常运行时全部通过、退化运行时全部超时，"
            "运行时回归假设获得可复现的隔离对照证据。"
            if passed
            else "对照结果未达到稳定判定门槛，需要调整工作负载或转人工复核。"
        )
        return JavaRuntimeComparison(
            source=source_relative_path,
            iterations=iterations,
            time_limit_ms=time_limit_ms,
            normal_runs=normal_runs,
            degraded_runs=degraded_runs,
            normal_pass_rate=normal_pass_rate,
            degraded_timeout_rate=degraded_timeout_rate,
            conclusion=conclusion,
            passed=passed,
        )
