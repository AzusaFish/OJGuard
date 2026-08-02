from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

from backend.app.runner.models import (
    CompileResult,
    ExecutionResult,
    JavaRuntimeProfile,
    ResourceLimits,
)


class DockerUnavailableError(RuntimeError):
    """Raised when the trusted runner cannot reach Docker Desktop."""


class RunnerSecurityError(ValueError):
    """Raised when a requested path escapes the configured runner roots."""


class DockerRunner:
    """Trusted control-plane adapter for the locked-down execution image.

    Agents never construct these commands. They submit artifact identifiers to
    the application service, which resolves them under `packages_root`.
    """

    def __init__(
        self,
        *,
        packages_root: Path,
        sessions_root: Path,
        image: str = "ojguard-runner:0.1.0",
        java_normal_image: str = "ojguard-java-runtime:normal-17",
        java_degraded_image: str = "ojguard-java-runtime:degraded-17",
        docker_binary: str = "docker",
    ) -> None:
        self.packages_root = packages_root.resolve()
        self.sessions_root = sessions_root.resolve()
        self.image = image
        self.java_normal_image = java_normal_image
        self.java_degraded_image = java_degraded_image
        self.docker_binary = docker_binary

    @staticmethod
    def _ensure_inside(root: Path, candidate: Path) -> Path:
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise RunnerSecurityError(f"path escapes configured root: {candidate}")
        return resolved

    def resolve_source(self, relative_path: str) -> Path:
        return self._ensure_inside(self.packages_root, self.packages_root / relative_path)

    def _new_session(self) -> Path:
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        session = self.sessions_root / f"session-{uuid.uuid4().hex}"
        session.mkdir()
        return session.resolve()

    def _base_command(self, limits: ResourceLimits) -> list[str]:
        return [
            self.docker_binary,
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            str(limits.cpus),
            "--memory",
            f"{limits.memory_limit_mb}m",
            "--memory-swap",
            f"{limits.memory_limit_mb}m",
            "--pids-limit",
            str(limits.pids_limit),
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
        ]

    @staticmethod
    def _load_result(result_path: Path) -> dict[str, object]:
        if not result_path.is_file():
            raise DockerUnavailableError("runner container did not produce result.json")
        return json.loads(result_path.read_text(encoding="utf-8"))

    def compile_cpp(
        self,
        *,
        source_relative_path: str,
        limits: ResourceLimits | None = None,
    ) -> tuple[CompileResult, Path]:
        limits = limits or ResourceLimits()
        source = self.resolve_source(source_relative_path)
        if not source.is_file() or source.suffix.lower() not in {".cc", ".cpp", ".cxx"}:
            raise RunnerSecurityError("source must be an existing C++ file under packages_root")
        session = self._new_session()
        command = self._base_command(limits)
        command.extend(
            [
                "--mount",
                f"type=bind,src={source.parent},dst=/workspace,readonly",
                "--mount",
                f"type=bind,src={session},dst=/session",
                self.image,
                "compile",
                f"/workspace/{source.name}",
                "/session/program",
                "/session/result.json",
            ]
        )
        self._invoke(command, timeout_seconds=90)
        return CompileResult.model_validate(self._load_result(session / "result.json")), session

    def execute(
        self,
        *,
        session: Path,
        input_payload: bytes,
        limits: ResourceLimits | None = None,
    ) -> ExecutionResult:
        limits = limits or ResourceLimits()
        session = self._ensure_inside(self.sessions_root, session)
        binary = session / "program"
        if not binary.is_file():
            raise RunnerSecurityError("compiled program is missing")
        input_path = session / "input.txt"
        input_path.write_bytes(input_payload)
        result_path = session / "run-result.json"
        command = self._base_command(limits)
        command.extend(
            [
                "--mount",
                f"type=bind,src={session},dst=/session",
                self.image,
                "run",
                "/session/program",
                "/session/input.txt",
                str(limits.time_limit_ms),
                str(limits.output_limit_bytes),
                "/session/run-result.json",
            ]
        )
        self._invoke(command, timeout_seconds=max(15, limits.time_limit_ms / 1000 + 10))
        return ExecutionResult.model_validate(self._load_result(result_path))

    def compile_java(
        self,
        *,
        source_relative_path: str,
        limits: ResourceLimits | None = None,
    ) -> tuple[CompileResult, Path]:
        limits = limits or ResourceLimits()
        source = self.resolve_source(source_relative_path)
        if not source.is_file() or source.suffix.lower() != ".java":
            raise RunnerSecurityError("source must be an existing Java file under packages_root")
        session = self._new_session()
        command = self._base_command(limits)
        command.extend(
            [
                "--mount",
                f"type=bind,src={source.parent},dst=/workspace,readonly",
                "--mount",
                f"type=bind,src={session},dst=/session",
                self.java_normal_image,
                "compile-java",
                f"/workspace/{source.name}",
                "/session/classes",
                "/session/result.json",
            ]
        )
        self._invoke(command, timeout_seconds=90)
        return CompileResult.model_validate(self._load_result(session / "result.json")), session

    def execute_java(
        self,
        *,
        session: Path,
        main_class: str,
        input_payload: bytes,
        profile: JavaRuntimeProfile,
        limits: ResourceLimits | None = None,
    ) -> ExecutionResult:
        limits = limits or ResourceLimits()
        session = self._ensure_inside(self.sessions_root, session)
        classes = session / "classes"
        if not classes.is_dir():
            raise RunnerSecurityError("compiled Java classes are missing")
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", main_class) is None:
            raise RunnerSecurityError("invalid Java main class")
        input_path = session / "java-input.txt"
        input_path.write_bytes(input_payload)
        result_path = session / f"java-{profile.value}-result.json"
        image = (
            self.java_normal_image
            if profile == JavaRuntimeProfile.NORMAL
            else self.java_degraded_image
        )
        command = self._base_command(limits)
        command.extend(
            [
                "--mount",
                f"type=bind,src={session},dst=/session",
                image,
                "run-java",
                "/session/classes",
                main_class,
                "/session/java-input.txt",
                str(limits.time_limit_ms),
                str(limits.output_limit_bytes),
                f"/session/{result_path.name}",
            ]
        )
        self._invoke(command, timeout_seconds=max(15, limits.time_limit_ms / 1000 + 10))
        return ExecutionResult.model_validate(self._load_result(result_path))

    def probe_checker(
        self,
        *,
        session: Path,
        answer_payload: bytes,
        contestant_output: bytes,
        limits: ResourceLimits | None = None,
    ) -> ExecutionResult:
        limits = limits or ResourceLimits()
        session = self._ensure_inside(self.sessions_root, session)
        binary = session / "program"
        if not binary.is_file():
            raise RunnerSecurityError("compiled Checker is missing")
        (session / "answer.txt").write_bytes(answer_payload)
        (session / "contestant-output.txt").write_bytes(contestant_output)
        result_path = session / "checker-result.json"
        command = self._base_command(limits)
        command.extend(
            [
                "--mount",
                f"type=bind,src={session},dst=/session",
                self.image,
                "checker",
                "/session/program",
                "/session/answer.txt",
                "/session/contestant-output.txt",
                str(limits.time_limit_ms),
                str(limits.output_limit_bytes),
                "/session/checker-result.json",
            ]
        )
        self._invoke(command, timeout_seconds=max(15, limits.time_limit_ms / 1000 + 10))
        return ExecutionResult.model_validate(self._load_result(result_path))

    @staticmethod
    def _invoke(command: list[str], *, timeout_seconds: float) -> None:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DockerUnavailableError("Docker runner is unavailable or timed out") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise DockerUnavailableError(f"Docker runner failed: {stderr[:500]}")
