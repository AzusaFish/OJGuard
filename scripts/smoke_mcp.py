import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def smoke() -> None:
    async with streamable_http_client("http://127.0.0.1:8020/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            names = sorted(tool.name for tool in result.tools)
            expected = {
                "audit_bundled_demo",
                "baseline_audit",
                "get_run_bundle",
                "inspect_package",
                "propose_demo_patch",
                "run_cpp_probe",
                "run_demo_regression",
                "verify_run_evidence",
            }
            if set(names) != expected:
                raise RuntimeError(f"unexpected MCP tools: {names}")
            print(f"mcp_tools={','.join(names)}")
            print("mcp_smoke=PASS")


if __name__ == "__main__":
    asyncio.run(smoke())
