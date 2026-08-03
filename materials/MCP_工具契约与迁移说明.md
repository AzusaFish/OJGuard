# OJGuard MCP 工具契约与迁移说明

## 1. 接入契约

| 项目 | 当前实现 |
|---|---|
| 协议 | MCP Streamable HTTP，路径 `/mcp`，无状态 JSON 响应 |
| 实现 | Python FastMCP；工具参数由类型签名生成 Schema，返回结构化对象 |
| 绑定范围 | 默认仅绑定 `127.0.0.1:8020`；AgentTeams 通过 `host.docker.internal` 访问 |
| 传输保护 | 启用 DNS Rebinding Protection，并限制 `127.0.0.1`、`localhost` 和 `host.docker.internal` Host |
| 身份与权限 | Demo 不提供公网身份认证；访问边界由本机网络、受限工具面、Agent 身份契约、状态机和人工审批共同组成 |
| 数据标识 | 工具只接受持久化 `incident_id`、`package_id`、`batch_id` 等标识，不接受任意路径、Shell 或 Docker 参数 |
| 错误处理 | 非法标识、缺失对象、状态不符和审批缺失转换为安全的 `MCPToolError`，不向 Agent 暴露宿主执行能力 |
| 重试 | 查询工具可安全重试；实验由输入哈希约束；批量重评必须复用原 `batch_id` 和幂等键，已完成项目不得重复执行 |
| 审计 | 事故状态、审批、批次、结果和 Evidence ID 持久化；AgentTeams 消息和最终结果导出为脱敏 JSON |
| 降级 | MCP 不可用时停止相关 Agent 任务并保留 IncidentContext，禁止模型伪造工具结果或绕过门禁 |

当前网络边界适用于本机比赛 Demo，不宣称满足公网生产认证。若部署到企业网络，应在 MCP 前增加 API Gateway 或 Service Mesh，使用 mTLS/OAuth2/短期服务令牌，并将 Agent 身份映射到服务端工具白名单；状态机和人工审批仍是最终业务授权依据。

## 2. 十二个受控工具

| MCP 工具 | 类型 | 主要调用方 | 输入 | 结构化输出/失败边界 |
|---|---|---|---|---|
| `incident.triage_signals` | 写入状态 | Signal Aggregator | `incident_id` | 读取有来源的信号并将 `TRIAGING` 推进到 `INVESTIGATING`；未知事故或非法阶段失败 |
| `submission.aggregate_verdicts` | 读取 | Signal Aggregator | `incident_id` | 基线、观测失败率与分组指标 |
| `deployment.list_changes` | 读取 | Signal Aggregator | `incident_id` | 时间窗口内变更记录 |
| `judge.replay_submission` | 分阶段分析/受控执行 | Root Cause Analyst | `incident_id`、`repetitions`、`mode`、`experiment_kind` | `hypotheses` 持久化竞争假设并返回多个候选；`candidates` 返回未执行候选；`experiment` 只执行 Manager 指定实验。不充分时写入 `INCONCLUSIVE` 并保持调查态；重复次数限制为 1–5 |
| `problem.audit_package` | 受控读取 | Root Cause Analyst | `package_id` | 只读清单与角色识别；拒绝未上传包和不安全标识 |
| `impact.calculate_scope` | 计算 | Impact Analyst | `incident_id` | 精确范围、数量、集合哈希；根因或策略条件不足时失败 |
| `rejudge.create_plan` | 计划 | Remediation Planner | `incident_id`、`mode` | `initial` 创建控制/灰度/全量批次；`recovery` 只允许在灰度失败后的 `PAUSED` 状态创建新版本计划和恢复灰度，并撤销旧审批；不执行批次 |
| `rejudge.execute_batch` | 状态变更 | Rejudge Executor | `incident_id`、`phase`、测试专用 `inject_canary_failure` | 批次计数和临时结果；审批、灰度或范围门禁失败即拒绝。注入失败仅用于确定性验收，失败后立即 `PAUSED`，不得进入全量 |
| `rejudge.pause_batch` | 状态变更 | Rejudge Executor | `incident_id`、`batch_id` | 暂停后的批次状态；已完成批次不可暂停 |
| `score.calculate_changes` | 计算 | Impact Analyst / Rejudge Executor | `incident_id` | 模拟成绩和排名变化；不写正式成绩 |
| `verification.verify_incident` | 独立核验 | Verification Auditor | `incident_id` | 覆盖、重复、遗漏、越界和关闭建议 |
| `report.generate_incident_report` | 报告 | Incident Manager / Auditor | `incident_id` | 稳定 JSON/HTML 报告及证据引用 |

## 3. 失败、审批和审计规则

- 读取和分析工具不得产生正式业务写入。
- 控制和灰度重评需要技术审批；全量重评需要业务审批。
- 任何灰度失败、影响集合漂移、运行器不可用或证据缺失都会阻止后续阶段。
- 灰度失败必须保留失败原因，将旧批次标记为被新 `canary_retry` 取代，创建 `revision+1` 的计划并撤销技术审批；只有新的持久化审批通过后才可恢复。
- Agent 不得以自然语言表示“已经批准”来替代持久化审批状态。
- 模型输出不是确认结论；确认结论必须引用确定性工具结果或可重放证据。
- 正式成绩写回不在本项目实现范围内，Demo 只产生临时结果和变化预览。

## 4. 替换与迁移成本

| 替换目标 | 保持不变的契约 | 需要适配 | 预计成本 |
|---|---|---|---|
| FastMCP → 其他 MCP Server | 工具名、参数 Schema、结构化返回、错误语义、幂等键 | 传输配置、注册方式、鉴权中间件 | 低到中 |
| SQLite → PostgreSQL/PolarDB | Incident、Approval、Batch、Evidence 领域模型 | Repository、事务和索引 | 中 |
| 本地 Runner → CI/CD 或企业沙箱 | Workload ID、资源限制、RunResult、Evidence ID | 调度、制品传输、身份和配额 | 中到高 |
| AgentTeams 内置调用 → 企业 Agent 平台 | MCP 工具契约、Skill 输入输出、IncidentContext | 角色配置、消息总线、Trace 关联字段 | 中 |
| 本机网络 → 公网/企业网络 | 工具 Schema、状态机、审批门禁 | mTLS/OAuth2、网关策略、密钥轮换和审计接入 | 中 |

项目不以“工具数量”作为价值证明。可替换性来自稳定领域模型、受控输入、显式错误、审批门禁、幂等语义和证据引用。

## 5. 核验证据

- MCP 注册：`mcp_server/server.py`。
- 工具实现：`mcp_server/tools.py`。
- 状态与审批门禁：`backend/app/services/incident_state_machine.py`。
- 重评幂等与范围验证：`backend/app/services/trusted_rejudge.py`。
- 工具契约测试：`tests/test_mcp_tools.py`。
