from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from backend.app.config import get_settings
from mcp_server.tools import OJGuardTools


settings = get_settings()
tools = OJGuardTools(Path.cwd())
mcp = FastMCP(
    "OJGuard",
    instructions=(
        "Evidence-driven programming-problem audit tools. Use package and run identifiers only; "
        "all untrusted code execution is delegated to the locked-down Docker Runner."
    ),
    host=settings.mcp_host,
    port=settings.mcp_port,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


@mcp.tool(title="Inspect problem package", structured_output=True)
def inspect_package(package_id: str) -> dict[str, Any]:
    """Structurally inspect an uploaded immutable package; this never executes package code."""
    return tools.inspect_package(package_id)


@mcp.tool(title="Run deterministic baseline audit", structured_output=True)
def baseline_audit(package_id: str, run_id: str) -> dict[str, Any]:
    """Extract rule-based audit hypotheses from a previously uploaded package."""
    return tools.baseline_audit(package_id, run_id)


@mcp.tool(title="Run sandboxed C++ probe", structured_output=True)
def run_cpp_probe(
    package_id: str,
    run_id: str,
    source_path: str,
    input_data: str,
    time_limit_ms: int = 1000,
    memory_limit_mb: int = 256,
) -> dict[str, Any]:
    """Compile and run a C++ source artifact under fixed Docker security and resource limits."""
    return tools.run_cpp_probe(
        package_id,
        run_id,
        source_path,
        input_data,
        time_limit_ms,
        memory_limit_mb,
    )


@mcp.tool(title="Audit bundled OJGuard demo", structured_output=True)
def audit_bundled_demo() -> dict[str, Any]:
    """Reproduce all four known Demo defects and persist a complete release-gate report."""
    return tools.audit_bundled_demo()


@mcp.tool(title="Get run evidence bundle", structured_output=True)
def get_run_bundle(run_id: str) -> dict[str, Any]:
    """Retrieve the current run state and all persisted audit records."""
    return tools.get_run_bundle(run_id)


@mcp.tool(title="Verify run evidence integrity", structured_output=True)
def verify_run_evidence(run_id: str) -> dict[str, Any]:
    """Verify SHA-256 integrity for every evidence artifact belonging to a run."""
    return tools.verify_run_evidence(run_id)


@mcp.tool(title="Propose bundled Demo patch", structured_output=True)
def propose_demo_patch(run_id: str) -> dict[str, Any]:
    """Generate a candidate Diff without changing any source file; human approval remains external."""
    return tools.propose_demo_patch(run_id)


@mcp.tool(title="Run bundled Demo regression", structured_output=True)
def run_demo_regression(patch_id: str) -> dict[str, Any]:
    """Revalidate an already human-approved working copy; this cannot grant release approval."""
    return tools.run_demo_regression(patch_id)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
