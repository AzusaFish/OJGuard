# OJGuard AgentTeams 集成

OJGuard 固定使用 AgentTeams `v1.2.0`（`agentscope-ai/AgentTeams`，commit `793db242257a569d911b1aa59c1cd554af78511f`）。业务 Team 为 `ojguard-incident-team`：Incident Manager 是独立 TeamLeader，协同 Signal、Root Cause、Impact、Remediation、Rejudge、Verification 六个专业 Worker。

## 部署边界：方案 B

本项目使用官方 Kubernetes/Helm 形态，Controller 通过 RBAC 管理 Pod；AgentTeams Pod 不挂载 Docker、Podman 或 containerd Socket。只有宿主侧受控 OJGuard Runner 可以创建临时执行容器，Worker 只能调用白名单 MCP 工具。

OJGuard MCP 监听 `127.0.0.1:8020`，Worker 经 `host.docker.internal:8020/mcp` 访问。DeepSeek 配置只保存在本地 `.env`，不得提交。

## 安装与应用 Team

在仓库根目录执行：

```powershell
.\scripts\setup_agentteams_k8s.ps1
.\scripts\start_ojguard_mcp.ps1
.\scripts\apply_agentteams_team.ps1
.\scripts\start_agentteams_ui.ps1
```

安装脚本把固定版本的 kind、Helm 和 AgentTeams Chart 保存到忽略的 `.runtime/`。安装期 LLM 探测关闭，Team 心跳关闭，避免消耗比赛 API 预算。

检查安全边界：

```powershell
.\scripts\verify_agentteams_security.ps1
```

检查业务 Team：

```powershell
kubectl --kubeconfig .runtime/agentteams-kubeconfig -n agentteams-system get workers
kubectl --kubeconfig .runtime/agentteams-kubeconfig -n agentteams-system get team ojguard-incident-team
```

## 受控协作演示

先在 OJGuard 工作台完成一条事故闭环并取得 `incident_id`，再执行一次有预算上限的 AgentTeams 复核：

```powershell
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-DEMO-LOCAL -IncidentId INC-XXXXXXXXXX
```

脚本要求六个 Worker 各回复一次、每人只调用一个指定工具，随后 TeamLeader 汇总一次。脱敏 Matrix 事件写入 `.runtime/agentteams-demo-result.json`。该过程会调用 DeepSeek，只有在最终验收或录制演示时运行。

## 状态归属

- Matrix 历史、Team/Worker 生命周期和共享 MinIO 工作区由 AgentTeams 管理；
- IncidentContext、信号、假设、实验、影响集合、审批、批次、成绩变化和验证记录由 OJGuard SQLite 管理；
- MCP 没有批准操作，Agent 不能代替人类批准全量重评、模拟成绩写回、通知或事故关闭；
- 单人参赛演示中的技术/业务审批通过角色上下文切换记录，报告会明确披露其并非真实多人签批。

Element Web 在端口转发运行时位于 `http://127.0.0.1:18080`。仅在确需登录时执行 `.\scripts\show_agentteams_login.ps1` 查看本地管理员账号。
