from enum import StrEnum

from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    OK = "OK"
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"


class JavaRuntimeProfile(StrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"


class ResourceLimits(BaseModel):
    time_limit_ms: int = Field(default=1_000, ge=50, le=60_000)
    memory_limit_mb: int = Field(default=256, ge=32, le=2_048)
    pids_limit: int = Field(default=32, ge=1, le=256)
    output_limit_bytes: int = Field(default=1_048_576, ge=1_024, le=16_777_216)
    cpus: float = Field(default=1.0, ge=0.1, le=4.0)


class CompileResult(BaseModel):
    status: ExecutionStatus
    exit_code: int | None = None
    compiler_stdout: str = ""
    compiler_stderr: str = ""
    binary_relative_path: str | None = None
    duration_ms: int = 0


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    output_truncated: bool = False
