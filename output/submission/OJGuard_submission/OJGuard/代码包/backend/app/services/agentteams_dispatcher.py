from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import Settings
from backend.app.domain import AgentRun


@dataclass(frozen=True)
class AgentTeamsRuntimeReadiness:
    ready: bool
    real_calls_enabled: bool
    api_key_configured: bool
    kubeconfig_present: bool
    launcher_present: bool
    python_present: bool
    gateway_reachable: bool
    message: str


@dataclass(frozen=True)
class AgentTeamsLaunchResult:
    pid: int
    stdout_path: Path
    stderr_path: Path


class AgentTeamsDispatcherError(RuntimeError):
    """Raised when a live AgentTeams run cannot be launched safely."""


class AgentTeamsDispatcher:
    def __init__(self, settings: Settings, repository_root: Path | None = None) -> None:
        self.settings = settings
        self.repository_root = repository_root or Path(__file__).resolve().parents[3]
        self.runtime_root = self.repository_root / ".runtime"
        self.kubeconfig = self.runtime_root / "agentteams-kubeconfig"
        self.launcher = self.repository_root / "scripts" / "run_agentteams_demo.ps1"
        self.python = self.repository_root / ".venv" / "Scripts" / "python.exe"

    @staticmethod
    def _gateway_reachable() -> bool:
        try:
            with socket.create_connection(("127.0.0.1", 18080), timeout=0.25):
                return True
        except OSError:
            return False

    def readiness(self) -> AgentTeamsRuntimeReadiness:
        api_key_configured = bool(
            self.settings.deepseek_api_key
            and self.settings.deepseek_api_key.get_secret_value().strip()
        )
        kubeconfig_present = self.kubeconfig.is_file()
        launcher_present = self.launcher.is_file()
        python_present = self.python.is_file()
        gateway_reachable = self._gateway_reachable()
        real_calls_enabled = self.settings.llm_real_calls_enabled
        ready = all(
            (
                real_calls_enabled,
                api_key_configured,
                kubeconfig_present,
                launcher_present,
                python_present,
                gateway_reachable,
            )
        )
        missing: list[str] = []
        if not real_calls_enabled:
            missing.append("尚未允许真实模型调用")
        if not api_key_configured:
            missing.append("未配置 DeepSeek 密钥")
        if not kubeconfig_present:
            missing.append("AgentTeams 集群尚未安装")
        if not gateway_reachable:
            missing.append("AgentTeams 网关尚未启动")
        if not python_present:
            missing.append("项目 Python 环境不存在")
        if not launcher_present:
            missing.append("AgentTeams 启动脚本不存在")
        return AgentTeamsRuntimeReadiness(
            ready=ready,
            real_calls_enabled=real_calls_enabled,
            api_key_configured=api_key_configured,
            kubeconfig_present=kubeconfig_present,
            launcher_present=launcher_present,
            python_present=python_present,
            gateway_reachable=gateway_reachable,
            message="AgentTeams 可以启动" if ready else "；".join(missing),
        )

    def launch(
        self,
        run: AgentRun,
        *,
        approval_actor: str,
        timeout_minutes: int,
        resume: bool = False,
    ) -> AgentTeamsLaunchResult:
        readiness = self.readiness()
        if not readiness.ready:
            raise AgentTeamsDispatcherError(readiness.message)
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            raise AgentTeamsDispatcherError("找不到 PowerShell，无法启动 AgentTeams")

        log_root = self.runtime_root / "agentteams-launch"
        log_root.mkdir(parents=True, exist_ok=True)
        stdout_path = log_root / f"{run.run_id}.stdout.log"
        stderr_path = log_root / f"{run.run_id}.stderr.log"
        command = [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.launcher),
            "-TaskId",
            run.task_id,
            "-IncidentId",
            run.incident_id,
            "-MaxLlmResponses",
            str(run.max_model_responses),
            "-TimeoutMinutes",
            str(timeout_minutes),
            "-ApprovalActor",
            approval_actor,
        ]
        if resume:
            command.append("-Resume")
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
                process = subprocess.Popen(
                    command,
                    cwd=self.repository_root,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    creationflags=creationflags,
                    shell=False,
                )
        except OSError as exc:
            raise AgentTeamsDispatcherError(f"AgentTeams 进程启动失败：{exc}") from exc
        return AgentTeamsLaunchResult(
            pid=process.pid,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
