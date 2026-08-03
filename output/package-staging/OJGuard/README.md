# OJGuard

> 在线测评事故响应与可信重评

OJGuard 面向企业招聘考试、在线教育、开发者认证和算法竞赛平台。当运行镜像、评测节点或 Checker 引发批量误判时，系统把分散信号归并为同一事故，通过竞争假设和对照实验确认根因，冻结受影响提交，再经人工审批执行控制组、灰度和分批全量重评，最后核验成绩、排名、晋级变化和重评完整性。

核心原则：**Agent 负责理解、协作和规划；确定性程序负责实验、计算、重评和验证；高风险动作由人审批。**

## 已实现能力

- 通用 Incident 领域模型、十阶段状态机、SQLite 持久化和可审计审批记录；
- Java 运行时回归、评测节点退化、Checker 缺陷三类确定性场景；
- 真实 Java 17 正常/退化镜像对照实验，相同代码和时限下复现 OK/TLE 差异；
- 影响集合计算、幂等批次、控制组/灰度/全量重评、暂停门禁与独立闭环验证；
- 同一调查状态下生成多个合法实验候选，由 Incident Manager 选择；不充分实验保持 `INVESTIGATING`，可继续改选补充实验；
- 灰度失败进入 `PAUSED`，自动隔离失败批次并生成新版本恢复计划，撤销旧审批，重新审批后执行 `canary_retry`；
- `AgentRun` 与顺序化 `AgentRunEvent` 持久化，提供快照、增量事件查询和 SSE 事件流接口；
- 成绩、排名和晋级变化重算，以及 JSON/HTML 事故报告；
- AgentTeams Team Leader + 6 个专业 Worker、9 个可复用 Skill、12 个 MCP 工具；
- Vue 3 + TypeScript 业务界面：事故总览、事故列表、事故工作台、审批与重评；
- Kubernetes Worker 后端配置；Worker 不直接操作宿主 Docker，执行动作只通过白名单 MCP 工具完成；
- Apache-2.0 许可证、第三方依赖声明和自动化测试。

## 快速体验

环境要求：Python 3.12+、Node.js 22+。只有运行 Java 镜像对照实验时需要 Docker Desktop。

首次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix frontend install
```

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

另开一个终端启动前端：

```powershell
npm --prefix frontend run dev
```

浏览器打开 `http://127.0.0.1:5173`，然后：

1. 进入“事故列表”，选择“Java 运行时回归”并创建演练；
2. 按页面“下一步”依次完成技术审批、控制与灰度、业务审批、全量重评、验证和关闭；
3. 在“重评与成绩”查看四个批次和成绩变化；
4. 在“闭环验证”确认覆盖率、重复、遗漏和越界检查；
5. 点击“查看事故报告”导出可审计 HTML 报告。

单人参赛演示会在技术审批与业务审批两种角色上下文之间切换，并记录同一操作者；这用于验证职责分离和门禁，不表示真实多人签批。

## 可复现证据

生成三类场景的完整闭环 JSON/HTML：

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_incident_evidence
```

构建并运行 Java 正常/退化镜像对照实验：

```powershell
.\scripts\build_java_runners.ps1
.\.venv\Scripts\python.exe -m scripts.run_java_regression_experiment
```

当前固定种子 `20260802` 的证据结果：

| 场景 | 受影响选手 | 受影响提交 | 重评覆盖率 | 结论 |
|---|---:|---:|---:|---|
| Java 运行时回归 | 703 | 742 | 100% | RESOLVED |
| 评测节点退化 | 118 | 119 | 100% | RESOLVED |
| Checker 缺陷 | 71 | 73 | 100% | RESOLVED |

证据位于 `output/evidence/`。Java 对照实验在相同 80ms 时限下，正常镜像 3/3 为 OK，退化镜像 3/3 为 TLE。

零成本复现“多候选动态路由 + 灰度失败恢复”证据：

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_orchestration_recovery_evidence
```

输出位于 `output/evidence/agentteams/deterministic-recovery-evidence.json`，明确标记为确定性策略与恢复测试，`model_calls=0`、`paid_api_cost=0`，不冒充真实大模型协作记录。

## 自动化验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check backend mcp_server scripts tests
npm --prefix frontend run build
```

当前 63 项测试覆盖事故状态门禁、多候选路由合同、事件幂等与顺序、灰度失败恢复、场景生成、影响计算、幂等重评、越界/重复检查、MCP 工具、Skill 合约、AgentTeams 配置和 Java Runner。

## AgentTeams 与 DeepSeek

常规开发、测试、场景生成和前端演练均不调用大模型。只有显式执行 AgentTeams 协作演练时才会读取本地 `.env` 中的 DeepSeek 配置：

```powershell
Copy-Item .env.example .env
# 在 .env 中填写 DEEPSEEK_API_KEY，且不要提交该文件
```

部署和演练入口见 `agentteams/README.md`。演练脚本默认创建一个没有预计算根因、影响面或处置计划的 `TRIAGING` 事故；后端给出带 Worker、实验、证据、预期状态和失败出口的合法路由合同，Team Leader 从中选择，而不是由宿主预先指定唯一动作。正常主链最多接受 20 条模型响应；显式失败恢复演练需要更高上限，默认只运行零成本确定性证据。确定性工具结果才是业务真相，密钥不会写入报告、前端、日志或仓库。

## 目录

```text
backend/       FastAPI、事故模型、状态机、重评、验证和报告
frontend/      Vue 3 业务界面
runner/        C++/Java 隔离执行镜像
mcp_server/    12 个 OJGuard MCP 工具
agents/        Team Leader 与 6 个 Worker 身份卡
agentteams/    AgentTeams/Kubernetes 配置和演练说明
skills/        9 个可复用 Skill
demo/          Java 对照实验与题包样例
scripts/       启动、证据生成、Runner 和 AgentTeams 脚本
tests/         自动化测试
output/        运行证据与提交材料
```

## 边界

- 演示数据均为固定种子生成的脱敏模拟数据，不连接真实 OJ、招聘系统或成绩库；
- “成绩写回”只作用于模拟临时结果，不覆盖真实成绩；
- 队列拥塞和配置漂移提供 Playbook/接口契约，但不宣称已有完整执行器；
- 知识检索仅保留后端扩展契约，不作为当前已实现功能；
- DeepSeek 是外部商业服务，不属于 Apache-2.0 开源范围。

完整方案见 [OJGuard_项目方案.md](OJGuard_项目方案.md)，第三方边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

赛题技术材料：

- [Agent Identity 清单](materials/Agent_Identity_清单.md)
- [MCP 工具契约与迁移说明](materials/MCP_工具契约与迁移说明.md)
- [上下文与可观测性说明](materials/上下文与可观测性说明.md)
