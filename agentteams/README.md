# OJGuard AgentTeams integration

OJGuard pins AgentTeams `v1.2.0` (`agentscope-ai/AgentTeams`, commit
`793db242257a569d911b1aa59c1cd554af78511f`). The deployment is a real
AgentTeams Team: `ojguard-judge-manager` is the Team Leader and delegates work
to four specialist Workers through Matrix rooms.

## Prerequisites

- Docker Desktop with at least 4 CPU cores and 8 GiB available to Linux containers.
- AgentTeams v1.2.0 installed locally in OpenAI-compatible mode.
- OJGuard MCP running on `127.0.0.1:8020`; Worker containers reach it through
  `host.docker.internal:8020/mcp`.
- DeepSeek configuration remains in local `.env` and must never be committed.

## Apply the team

Use the v1.2.0 official `agentteams-apply` helper after AgentTeams is healthy:

```powershell
docker cp agentteams/ojguard-team.yaml agentteams-manager:/tmp/ojguard-team.yaml
docker exec agentteams-manager agt apply -f /tmp/ojguard-team.yaml
docker exec agentteams-manager agt get workers
docker exec agentteams-manager agt get team ojguard-audit-team
```

The YAML intentionally exposes no approval tool. Agents may inspect, execute
controlled probes, produce evidence, and propose a candidate Diff. Applying a
working-copy patch and confirming release remain human-only OJGuard API/UI actions.

## Expected topology

- Leader Room: AgentTeams Manager, human admin, OJGuard Judge Manager.
- Team Room: OJGuard Judge Manager and the four specialist Workers.
- Shared MinIO workspace and Matrix history are owned by AgentTeams.
- Structured run state, Findings, Evidence, approvals, and product trace are
  owned by OJGuard SQLite/artifact storage.

For local development, start MCP with `python -m mcp_server.server`. The RAG
port `8010` remains reserved and disabled; AgentTeams integration does not
depend on RAG.
