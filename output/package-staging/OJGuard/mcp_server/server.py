from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from backend.app.config import get_settings
from mcp_server.tools import OJGuardTools

settings = get_settings()
tools = OJGuardTools(Path.cwd())
mcp = FastMCP(
    "OJGuard",
    instructions=(
        "Evidence-driven online-judge incident response tools. Use persisted identifiers only. "
        "All execution and state changes are constrained by deterministic gates and approvals."
    ),
    host=settings.mcp_host,
    port=settings.mcp_port,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            f"127.0.0.1:{settings.mcp_port}",
            f"localhost:{settings.mcp_port}",
            f"host.docker.internal:{settings.mcp_port}",
        ],
    ),
)


@mcp.tool(name="incident.list_signals", title="List incident signals", structured_output=True)
def incident_list_signals(incident_id: str) -> dict[str, Any]:
    return tools.incident_list_signals(incident_id)


@mcp.tool(
    name="submission.aggregate_verdicts",
    title="Aggregate submission verdicts",
    structured_output=True,
)
def submission_aggregate_verdicts(incident_id: str) -> dict[str, Any]:
    return tools.submission_aggregate_verdicts(incident_id)


@mcp.tool(
    name="deployment.list_changes", title="List deployment changes", structured_output=True
)
def deployment_list_changes(incident_id: str) -> dict[str, Any]:
    return tools.deployment_list_changes(incident_id)


@mcp.tool(
    name="judge.replay_submission", title="Replay controlled submission", structured_output=True
)
def judge_replay_submission(incident_id: str, repetitions: int = 3) -> dict[str, Any]:
    return tools.judge_replay_submission(incident_id, repetitions)


@mcp.tool(name="problem.audit_package", title="Audit problem package", structured_output=True)
def problem_audit_package(package_id: str) -> dict[str, Any]:
    return tools.problem_audit_package(package_id)


@mcp.tool(name="impact.calculate_scope", title="Calculate incident impact", structured_output=True)
def impact_calculate_scope(incident_id: str) -> dict[str, Any]:
    return tools.impact_calculate_scope(incident_id)


@mcp.tool(name="rejudge.create_plan", title="Get controlled rejudge plan", structured_output=True)
def rejudge_create_plan(incident_id: str) -> dict[str, Any]:
    return tools.rejudge_create_plan(incident_id)


@mcp.tool(name="rejudge.execute_batch", title="Execute approved rejudge phase", structured_output=True)
def rejudge_execute_batch(incident_id: str, phase: str) -> dict[str, Any]:
    return tools.rejudge_execute_batch(incident_id, phase)


@mcp.tool(name="rejudge.pause_batch", title="Pause rejudge batch", structured_output=True)
def rejudge_pause_batch(incident_id: str, batch_id: str) -> dict[str, Any]:
    return tools.rejudge_pause_batch(incident_id, batch_id)


@mcp.tool(name="score.calculate_changes", title="List calculated score changes", structured_output=True)
def score_calculate_changes(incident_id: str) -> dict[str, Any]:
    return tools.score_calculate_changes(incident_id)


@mcp.tool(
    name="verification.verify_incident", title="Verify incident resolution", structured_output=True
)
def verification_verify_incident(incident_id: str) -> dict[str, Any]:
    return tools.verification_verify_incident(incident_id)


@mcp.tool(
    name="report.generate_incident_report",
    title="Generate incident report",
    structured_output=True,
)
def report_generate_incident_report(incident_id: str) -> dict[str, Any]:
    return tools.report_generate_incident_report(incident_id)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
