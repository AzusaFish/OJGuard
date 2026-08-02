import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def smoke() -> None:
    async with streamable_http_client("http://127.0.0.1:8020/mcp") as (
        read_stream,
        write_stream,
        _,
    ), ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        result = await session.list_tools()
        names = sorted(tool.name for tool in result.tools)
        expected = {
            "deployment.list_changes",
            "impact.calculate_scope",
            "incident.list_signals",
            "judge.replay_submission",
            "problem.audit_package",
            "rejudge.create_plan",
            "rejudge.execute_batch",
            "rejudge.pause_batch",
            "report.generate_incident_report",
            "score.calculate_changes",
            "submission.aggregate_verdicts",
            "verification.verify_incident",
        }
        if set(names) != expected:
            raise RuntimeError(f"unexpected MCP tools: {names}")
        print(f"mcp_tools={','.join(names)}")
        print("mcp_smoke=PASS")


if __name__ == "__main__":
    asyncio.run(smoke())
