# OJGuard AgentTeams 真实运行证据

## 结论

- Team：`ojguard-incident-team`，状态 `Active 6/6`；
- Team Leader：`ojguard-incident-manager`；Worker：6 个；
- 模型：DeepSeek `deepseek-chat`；
- 任务：`OJGUARD-LIVE-FINAL-20260803`；
- 事故：`INC-33E802A300`；
- 编排模式：`live_dynamic_routing`，`posthoc_review=false`；
- 初始状态：`TRIAGING`；最终状态：`RESOLVED`；
- 20 条有界模型响应：11 次 `ROUTE_DECISION`、8 次 `WORKER_RESULT`、1 次最终报告；
- 六个专业 Worker 全部留下独立响应；Root Cause Analyst 和 Rejudge Executor 因阶段职责各执行两次；
- 脱敏原始证据：`output/evidence/agentteams/agentteams-demo-result.json`。

启动时事故只有 22 条原始信号，`hypothesis_count=0`、`experiment_count=0`、`impact_count=0`、`plan_count=0`。因此本次证据不是对已完成事故的事后复核。

## 动态闭环轨迹

| 前状态 | Team Leader 路由 | Worker / 人工角色 | 工具或门禁 | 后状态 |
|---|---|---|---|---|
| `TRIAGING` | `triage` | Signal Aggregator | `incident.triage_signals` | `INVESTIGATING` |
| `INVESTIGATING` | `hypothesize` | Root Cause Analyst | `judge.replay_submission(mode=hypotheses)` | `INVESTIGATING` |
| `INVESTIGATING` | `experiment` | Root Cause Analyst | `judge.replay_submission(mode=experiment)` | `IMPACT_ASSESSING` |
| `IMPACT_ASSESSING` | `impact` | Impact Analyst | `impact.calculate_scope` | `REMEDIATION_PLANNING` |
| `REMEDIATION_PLANNING` | `plan` | Remediation Planner | `rejudge.create_plan` | `APPROVAL_PENDING` |
| `APPROVAL_PENDING` | `request_technical_approval` | 人工技术角色 | 技术审批 | `APPROVAL_PENDING` |
| `APPROVAL_PENDING` | `control_canary` | Rejudge Executor | `rejudge.execute_batch(control_canary)` | `EXECUTING` |
| `EXECUTING` | `request_business_approval` | 人工业务角色 | 业务审批 | `EXECUTING` |
| `EXECUTING` | `bulk` | Rejudge Executor | `rejudge.execute_batch(bulk)` | `REJUDGING` |
| `REJUDGING` | `verify` | Verification Auditor | `verification.verify_incident` | `VERIFYING` |
| `VERIFYING` | `request_close_approval` | 人工业务角色 | 关闭审批 | `RESOLVED` |

每轮路由后，宿主调度器重新读取 SQLite 中的 IncidentContext 并核对预期状态。Agent 自然语言不直接改变业务状态；非法路由、工具失败、证据冲突或状态不符都会停止或转人工。

## 关键证据

### 竞争假设与补充实验

第一次 Root Cause Analyst 调用只持久化两条 `PROPOSED` 假设，明确返回 `experiment_executed=false`：

- `runtime_image`：Java 运行镜像或启动参数导致性能回归；
- `judge_node`：部分评测节点退化导致 Java 提交集中超时。

Team Leader 读取冲突后才发出第二个 `experiment` 路由。二维对照实验 `EXP-6CC58C053B` 通过：正常环境 3/3 `OK`，退化环境 3/3 `TLE`；失败率从 8.3% 升至 41.4%，五个节点失败率接近，因此确认 `runtime_image`、否定 `judge_node`。

### 影响、计划与执行

- 冻结影响：703 名候选人、742 条提交、703 项预计成绩变化、72 项预计晋级变化；
- 计划：控制 20、灰度 38、全量 500 + 184，共四个批次；
- 控制与灰度：全部完成、失败 0、跳过 0；
- 全量重评：两个批次全部完成、失败 0、跳过 0；
- 独立验证 `VERIFY-E19B0A5963`：覆盖率 100%，重复 0、遗漏 0、越界 0。

### 审批与权限边界

- MCP 不提供批准接口，Agent 不能自批技术、业务或关闭门禁；
- 技术审批发生在控制/灰度前，业务审批发生在全量重评前，关闭审批发生在独立验证后；
- AgentTeams Pod 不挂载 Docker、Podman 或 containerd Socket；
- Java 实验由宿主侧受控 Runner 生成证据，Worker 只读取带 SHA-256 的结构化结果；
- 单人参赛者以不同角色上下文完成门禁验证，这不代表真实多人签批；
- 演练只作用于模拟事故和临时成绩，不连接真实 OJ 或正式成绩库。

## 可复核文件

- `output/evidence/agentteams/agentteams-demo-result.json`：11 次路由、8 次 Worker 结果、状态轨迹和最终消息；
- `output/evidence/java-runtime-comparison.json`：正常/退化 Java 运行时对照实验；
- `agentteams/ojguard-team.yaml`：Team/Worker 身份、边界和协作配置；
- `scripts/run_agentteams_demo.ps1`：动态路由、状态验证、预算上限、失败停止与安全续跑；
- `scripts/agentteams_runtime_control.py`：只负责事故启动、状态读取和人工门禁记录；
- `scripts/export_agentteams_evidence.ps1`：脱敏证据验证与导出。

## 补充确定性策略与恢复证据

真实记录用于证明 AgentTeams、DeepSeek、TeamLeader 和六个 Worker 确实参与协作；为了不额外消耗预算，多个合法候选、不充分实验补选和灰度失败恢复使用独立的确定性证据验证：`output/evidence/agentteams/deterministic-recovery-evidence.json`。

该文件明确标记 `evidence_class=deterministic_policy_and_recovery_test`、`model_calls=0`、`paid_api_cost=0`，验证：

- 节点退化场景同时产生 3 个合法实验候选；
- 首选跨镜像实验得到 `INCONCLUSIVE` 并保持 `INVESTIGATING`；
- 改选跨节点实验后才进入 `IMPACT_ASSESSING`；
- 灰度失败进入 `PAUSED`，不得执行全量；
- 恢复计划为 revision 2，引用原计划并撤销旧技术审批；
- 新 `canary_retry` 通过后完成全量，最终覆盖率 100%，重复、遗漏、越界均为 0。

两类证据相互补充且不混淆：前者证明真实多 Agent 调用，后者证明新增路由选择与失败恢复语义可重复、可断言。
