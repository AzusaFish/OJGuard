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

## 前端主流程与受控协作

Vue 事故列表通过 `POST /api/v1/agent-runs` 创建干净的 `TRIAGING` 事故与 `AgentRun`；事故工作台检查运行环境后，通过 `/agent-runs/{run_id}/launch` 启动本脚本。前端不会调用 `prepare_demo()`，也不会直接执行实验、影响计算、重评或验证。

也可以直接启动一次有预算上限的在线协作：

```powershell
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-LIVE-LOCAL -IncidentType runtime_regression
```

脚本先创建一个仅包含原始信号的 `TRIAGING` 事故，明确保证根因、影响面和处置计划均未预计算。随后进入动态闭环：

1. 后端根据当前 `IncidentContext` 生成合法路由合同；根因阶段同时给出 2～3 个实验候选，包含 Worker、工具参数、证据范围、预期状态和失败出口；
2. TeamLeader 读取候选并选择一个结构化 `ROUTE_DECISION`，选择结果必须通过宿主策略校验，不能引用合同外证据或更换 Worker；
3. 被选中的 Worker 调用一个白名单 MCP 工具，将结果与状态变化写回共享上下文；
4. 调度器重新读取状态并验证预期转换；实验不充分时仍停留在 `INVESTIGATING` 并返回剩余候选，而不是强行确认根因；
5. 灰度失败时进入 `PAUSED`，Remediation Planner 生成新版本计划并撤销旧技术审批；重新审批后只执行恢复灰度；
6. 技术审批、业务审批和关闭审批由宿主侧人类角色上下文记录，Agent 无审批工具；脚本默认暂停等待前端批准或拒绝；
7. 六个专业 Worker 全部留下过程证据，最终 TeamLeader 才生成事故报告。

完整主链为：`TRIAGING → INVESTIGATING → IMPACT_ASSESSING → REMEDIATION_PLANNING → APPROVAL_PENDING → EXECUTING → REJUDGING → VERIFYING → RESOLVED`。根因阶段会持久化竞争假设与“节点 × 运行时镜像”对照实验；重评、影响计算和一致性验证仍由确定性后端执行。

脱敏的路由决策、状态轨迹、Worker 响应和最终报告写入 `.runtime/agentteams-demo-result.json`；同一过程还写入 SQLite 的 `AgentRun` / `AgentRunEvent`，可通过 `/api/v1/agent-runs/{run_id}`、`/events` 和 `/stream` 查询或订阅。默认成功主链最多接受 20 条 LLM 响应；安装探测与心跳不调用模型。真实协作会消耗 DeepSeek 预算，只在最终验收时运行一次。

`-AutoApprove` 仅用于隔离的脚本回归，不得用于正式前端主流程或评审证据。失败运行可以通过前端“恢复 AgentTeams”或脚本 `-Resume` 从持久化 `IncidentContext` 和事件序列继续。

不调用 DeepSeek 即可验证多候选选择和失败恢复：

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_orchestration_recovery_evidence
```

结果写入 `output/evidence/agentteams/deterministic-recovery-evidence.json`。若明确需要录制真实失败恢复链，必须同时传入 `-InjectCanaryFailure -MaxLlmResponses 30`；这会显著增加付费调用，运行前应先确认预算。

如需复用一个尚未处理的事故，可传入其 ID，但脚本会拒绝任何不是 `TRIAGING` 的事故：

```powershell
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-LIVE-LOCAL -IncidentId INC-XXXXXXXXXX
```

## 状态归属

- Matrix 历史、Team/Worker 生命周期和共享 MinIO 工作区由 AgentTeams 管理；
- IncidentContext、信号、假设、实验、影响集合、审批、批次、成绩变化和验证记录由 OJGuard SQLite 管理；
- AgentRun 保存一次协作执行的状态与模型响应预算，AgentRunEvent 以递增序号保存路由、Worker、工具、状态转换、人工门禁、暂停、恢复、报告和错误；重复事件 ID 不会重复计数；
- MCP 没有批准操作，Agent 不能代替人类批准全量重评、模拟成绩写回、通知或事故关闭；
- 单人参赛演示中的技术/业务审批通过角色上下文切换记录，报告会明确披露其并非真实多人签批。

Element Web 在端口转发运行时位于 `http://127.0.0.1:18080`。仅在确需登录时执行 `.\scripts\show_agentteams_login.ps1` 查看本地管理员账号。
