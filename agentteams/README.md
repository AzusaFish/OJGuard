# OJGuard AgentTeams integration

OJGuard pins AgentTeams `v1.2.0` (`agentscope-ai/AgentTeams`, commit
`793db242257a569d911b1aa59c1cd554af78511f`). The deployment is a real
AgentTeams Team: `ojguard-judge-manager` is the Team Leader and delegates work
to four specialist Workers through Matrix rooms.
The v1.2.0 Kubernetes deployment uses the chart's stable OpenClaw runtime; the
CoPaw image currently has a K8s workspace/MinIO sync incompatibility.

## Deployment decision: B (no host Docker Socket)

OJGuard does **not** use AgentTeams' single-container embedded installer. In
v1.2.0 that installer mounts the host Docker Socket into the controller so it
can create Manager and Worker containers. OJGuard instead uses the official
Kubernetes-native Helm chart `agentteams-1.2.0` (verified SHA-256
`f530879c26cc4e3ef8aea3e33551937604a9a803a09a358135f07a5de2de00f7`).
The controller reconciles Kubernetes Pods through its ServiceAccount/RBAC;
Manager and Workers receive no Docker, Podman, or containerd socket.

## Prerequisites

- Docker Desktop with at least 4 CPU cores and 8 GiB available to Linux containers.
- Docker Desktop running. The setup script creates a dedicated local `kind`
  cluster; Docker Desktop Kubernetes does not need to be enabled.
- OJGuard MCP running on `127.0.0.1:8020`; Worker containers reach it through
  `host.docker.internal:8020/mcp`.
- DeepSeek configuration remains in local `.env` and must never be committed.

## Install and apply the team

Run in PowerShell from the repository root:

```powershell
.\scripts\setup_agentteams_k8s.ps1
.\scripts\start_ojguard_mcp.ps1
.\scripts\apply_agentteams_team.ps1
.\scripts\start_agentteams_ui.ps1
```

The first script downloads pinned `kind v0.31.0`, Helm `v3.20.2`, and the
official chart into ignored `.runtime/` storage. It reads the DeepSeek key from
`.env`, never prints it, and disables the chart's install-time LLM preflight to
avoid spending the competition budget on a connectivity probe. Team heartbeats
are disabled and the platform Manager heartbeat is set to 24 hours.

To re-check the security boundary and current state:

```powershell
.\scripts\verify_agentteams_security.ps1
```

Run a fresh bounded demonstration, or consolidate an already verified run:

```powershell
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-DEMO-LOCAL
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-DEMO-REVIEW -ExistingRunId RUN-DEMO-XXXXXXXXXX
```

The script waits for four distinct Worker replies, visibly mentions the Leader
for final consolidation, and stores a sanitized transcript in ignored
`.runtime/agentteams-demo-result.json`.

Element Web is then available at `http://127.0.0.1:18080` while the local
port-forward is running.

Display the locally generated admin login only when you need to sign in:

```powershell
.\scripts\show_agentteams_login.ps1
```

### Kubernetes-native apply

The helper script applies the CRs directly to the dedicated namespace. The
equivalent inspection commands are:

```powershell
kubectl --kubeconfig .runtime/agentteams-kubeconfig -n agentteams-system get workers
kubectl --kubeconfig .runtime/agentteams-kubeconfig -n agentteams-system get team ojguard-audit-team
```

The YAML intentionally exposes no approval tool. Agents may inspect, execute
controlled probes, produce evidence, and propose a candidate Diff. Applying a
working-copy patch and confirming release remain human-only OJGuard API/UI actions.

## Expected topology

- Leader DM Room: human admin and OJGuard Judge Manager.
- Platform Manager has a separate admin DM for infrastructure coordination.
- Team Room: OJGuard Judge Manager and the four specialist Workers.
- Shared MinIO workspace and Matrix history are owned by AgentTeams.
- Structured run state, Findings, Evidence, approvals, and product trace are
  owned by OJGuard SQLite/artifact storage.

For local development, start MCP with `scripts/start_ojguard_mcp.ps1`. It binds
only `127.0.0.1:8020`; Docker Desktop maps its private
`host.docker.internal` gateway to that loopback listener. The RAG
port `8010` remains reserved and disabled; AgentTeams integration does not
depend on RAG.
