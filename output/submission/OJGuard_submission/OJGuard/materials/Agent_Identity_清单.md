# OJGuard Agent Identity 清单

## 1. 团队结构

OJGuard 使用 AgentTeams v1.2.0 组织一个独立 Team Leader 和六个专业 Worker。AgentTeams Platform Manager 只管理 Team/Worker 生命周期，不承担 OJGuard 事故处置职责；业务任务统一交给 OJGuard Incident Manager。

| Agent | AgentTeams 角色 | 核心职责 | 能力边界 | 主要 Skill | 主要 MCP 工具 | 主要协作关系 |
|---|---|---|---|---|---|---|
| Incident Manager | Team Leader | 逐状态读取共享上下文，在多个合法实验/处置合同中动态选择、冲突裁决、失败恢复、人工转交和报告汇总 | 不得调用专业 Worker 工具，不得自造路由合同，不得替人审批重评、成绩写回、通知或关闭事故 | `normalize-judge-signals`、`correlate-incident-events`、`generate-incident-audit-report` | `incident.triage_signals`、`report.generate_incident_report` | 每轮只发出一个含 action、worker、experiment、failure、evidence 的 `ROUTE_DECISION`；不充分实验后可改选剩余实验，灰度失败后只能进入恢复计划或人工出口 |
| Signal Aggregator | Worker | 归一化监控、提交、部署和投诉信号，构建时间线并推进调查状态 | 不得把相关性直接写成根因，不得执行处置 | `normalize-judge-signals`、`correlate-incident-events` | `incident.triage_signals`、`submission.aggregate_verdicts`、`deployment.list_changes` | 从 `TRIAGING` 写入可追溯信号并推进到 `INVESTIGATING`，供 Root Cause Analyst 使用 |
| Root Cause Analyst | Worker | 维护竞争假设，公布可选实验并执行 Manager 选择的控制实验 | 未通过实验不得确认根因；不得自行决定后续 Agent；不得直接操作 Docker 或宿主机 | `correlate-incident-events`、`reproduce-judge-failure`、`audit-problem-package` | `judge.replay_submission`、`problem.audit_package` | `hypotheses` 生成竞争假设，`candidates` 返回剩余实验，`experiment` 只执行指定 `experiment_kind`；不充分结果写回 `INCONCLUSIVE` |
| Impact Analyst | Worker | 计算受影响提交、候选人、题目、语言、成绩和晋级范围 | 不得越过策略扩大范围、导出个人数据或修改成绩 | `calculate-impact-scope` | `impact.calculate_scope`、`score.calculate_changes` | 将冻结集合交给 Remediation Planner、Rejudge Executor 和 Verification Auditor |
| Remediation Planner | Worker | 生成回滚、隔离、灰度、全量重评及灰度失败后的版本化恢复方案 | 只生成计划，不得自批或执行；恢复计划不得改变冻结影响集合 | `generate-remediation-plan` | `rejudge.create_plan` | 初始计划使用 `mode=initial`；失败恢复使用 `mode=recovery`，记录 `revision` 与 `supersedes_plan_id` 并撤销旧技术审批 |
| Rejudge Executor | Worker | 执行已批准的控制、灰度和全量批次 | 不得变更范围、自批、覆盖正式成绩或绕过灰度 | `execute-controlled-rejudge` | `rejudge.execute_batch`、`rejudge.pause_batch` | 消费批准后的计划，将批次记录和临时结果交给 Verification Auditor |
| Verification & Audit Worker | Worker | 独立核验覆盖、重复、越界、成绩、审批和证据 | 不得编辑证据、审批或自行关闭事故 | `verify-score-consistency`、`generate-incident-audit-report` | `verification.verify_incident`、`report.generate_incident_report` | 独立重算并向 Incident Manager 返回关闭、警告、回滚或人工复核建议 |

机器可读身份卡位于 `agents/identities/*.yaml`，每张卡包含 Name、Role、Capabilities、Inputs、Outputs、Dependencies、Decision Boundary、允许 Skill/Tool、人工介入条件、失败升级路径和 Trace 规则。

## 2. 端到端任务闭环

1. **任务输入**：系统接收告警、提交异常、部署变更、投诉、题包事件或人工创建的事故。
2. **任务拆解**：Incident Manager 按 Playbook 和依赖关系拆成信号、根因、影响、处置、执行、核验六类任务。
3. **上下文传递**：Agent 共享结构化 `IncidentContext`、不可变 Evidence ID 和集合哈希，不以复制整段聊天记录代替业务状态。
4. **协同执行**：Worker 只调用声明的 Skill 和受控 MCP 工具；确定性程序负责查询、实验、集合计算、批次和核验，大模型负责解释、编排和报告。
5. **结果验证**：确认根因需要可重复控制实验；全量重评前必须通过控制组、灰度和人工审批；关闭前由独立 Auditor 重算。
6. **状态跟踪**：状态机覆盖 `DETECTED` 至 `RESOLVED`；灰度失败进入 `PAUSED`，旧批次标为 `ROLLED_BACK`，新计划重新审批后通过 `canary_retry` 恢复；不可恢复时进入 `FAILED` 或 `HUMAN_REVIEW_REQUIRED`。
7. **证据沉淀**：系统保存 AgentTeams 消息事件、MCP 结果、批次记录、JSON/HTML 报告、截图和 SHA-256 摘要。
8. **审批与回滚**：L2 以上动作要求人工确认；失败时暂停后续批次、保留原始快照和幂等状态，必要时进入人工复核或回滚。
9. **经验复用**：稳定流程沉淀为版本化 Skill、Playbook、Schema、固定种子场景和事故报告，可复用于不同 OJ 与事故类型。

## 3. 实机证据

- Team 定义：`agentteams/ojguard-team.yaml`。
- 身份契约测试：`tests/test_agentteams_manifest.py`。
- 脱敏实机记录：`output/evidence/agentteams/agentteams-demo-result.json`。
- 零成本多候选/失败恢复证据：`output/evidence/agentteams/deterministic-recovery-evidence.json`。
- 实机结果：Team 为 `Active`，六个 Worker 全部返回，Team Leader 完成最终汇总，任务标记 `completed=true`。

实机记录证明 AgentTeams 与六个 Worker 的真实调用；确定性恢复证据证明多个合法实验候选、补充实验、灰度暂停、计划版本、审批撤销与恢复灰度。二者证据类别分开标注，不把零模型测试写成真实 LLM 运行。

单人参赛情况下，技术审批与业务审批由参赛者切换角色上下文完成并留痕。该设计用于展示职责分离和审批门禁，不代表真实多人签批。
