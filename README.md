# OJGuard

> 基于 AgentTeams 的编程题包多智能体质量验证与发布门禁

OJGuard 面向 OJ、编程教育、算法竞赛和技术招聘场景。系统把题面、Validator、
标准程序、测试数据与 Checker 的人工验题过程，转化为“风险假设 → 沙箱验证 →
证据固化 → 人工审批 → 回归 → 发布确认”的可审计闭环。

核心原则：**Agent 提出假设，确定性程序验证假设；没有证据的判断不能成为已确认缺陷。**

## 已实现

- FastAPI 业务 API、SQLite 状态机、ZIP 安全导入、预算门禁；
- Docker C++17 Runner，默认断网并限制 CPU、内存、进程、时间和输出；
- Finding、Evidence、SHA-256 校验、JSONL Trace、JSON/HTML 报告；
- 7 个可复用 Skill 和 8 个 MCP 工具，MCP 服务端口为 `8020`；
- 三级修复权限：候选 Diff、首次人工批准、工作副本回归、二次发布确认；
- 10 个原创基准题包及可重复计算的确定性基准报告；
- Vue 3 + TypeScript 完整控制台，含总览、上传、运行详情、证据、审批、基准、架构和设置；
- RAG 服务契约预留在 `8010`，默认明确返回 `RAG_DISABLED`；
- AgentTeams v1.2.0 平台 Manager、OJGuard Team Leader 与 4 个专业 Worker 的真实协作环境。

项目已按安全方案 B 部署官方 Kubernetes/Helm 形态：Controller 使用 `workerBackend=k8s`
管理独立 kind 集群，Manager、Worker 与被测容器均不挂载宿主 Docker Socket。只有宿主机
上的受控 OJGuard Runner 能通过白名单 MCP 动作创建临时执行容器；Agent 没有宿主 Shell、
补丁审批或发布确认接口。真实协作证据见
[`materials/evidence/AgentTeams_真实运行证据.md`](materials/evidence/AgentTeams_真实运行证据.md)。

## 目录

```text
backend/       FastAPI、领域模型、状态、证据、门禁与报告
frontend/      Vue 3 产品控制台
runner/        C++17 隔离执行镜像
mcp_server/    OJGuard MCP Server
agents/        五个 Agent Identity
agentteams/    AgentTeams Team/Worker 清单
skills/        七个 Agent Skill
demo/          主演示题包（四类预埋缺陷）
benchmark/     十个原创基准定义与报告
scripts/       演示、基准及集成冒烟脚本
tests/         自动化测试
```

## 本地运行

要求：Python 3.12+、Node.js 22+、Docker Desktop。

```powershell
python -m pip install -e ".[dev]"
docker build -t ojguard-runner:0.1.0 runner
python -m uvicorn backend.app.main:app --reload --port 8000
```

另开终端启动 MCP：

```powershell
python -m mcp_server.server
```

再启动前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。API 文档位于
`http://127.0.0.1:8000/docs`，健康检查为
`http://127.0.0.1:8000/api/v1/health`。

## 配置与费用保护

复制 `.env.example` 为 `.env`，只在本机填入 `DEEPSEEK_API_KEY`。`.env`、运行数据、
证据和前端构建产物均已忽略，不会进入 Git。

开发与确定性评测默认不调用模型。真实模型固定使用 DeepSeek `deepseek-chat`；估算花费
达到 6 元时提醒，达到 8 元时停止非必要调用，并为最终演示保留至少 2 元。日志、Trace、
API 与前端不得回显密钥。

本次 AgentTeams 安装与演示共观测到 37 次 DeepSeek 调用。按当前官方较高价模型、峰时
2 倍和保守汇率估算上限约 1.70 元；准确扣费以 DeepSeek 控制台为准。团队自主心跳已关闭，
平台 Manager 心跳为 24 小时，避免后台频繁消耗 10 元预算。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m ruff check . --exclude frontend --exclude .runtime --exclude data --exclude artifacts
npm --prefix frontend run build
python -m scripts.run_benchmark
python -m scripts.run_demo_audit
python -m scripts.smoke_runner
python -m scripts.smoke_patch_workflow
.\scripts\verify_agentteams_security.ps1
.\scripts\run_agentteams_demo.ps1 -TaskId OJGUARD-DEMO-LOCAL
```

当前确定性基准包含 10 个题包：8 个缺陷题包、2 个干净对照。报告范围明确限定为
`deterministic_baseline_only`，不会冒充 AgentTeams 或 LLM 的质量评测。

## 安全边界

- 不可信程序只能经过白名单 Runner 动作执行，不开放任意 Shell；
- 原题包只读，候选补丁只应用于独立工作副本；
- Worker 无权批准补丁或确认发布；
- 回归失败不能绕过发布门禁；
- 初赛版本不连接真实 OJ、不公网部署、不自动发布；
- RAG 未启用时明确报告禁用状态，不伪造检索结果。
- AgentTeams Pod 不挂载 Docker、Podman 或 containerd Socket；
- MCP 仅监听 `127.0.0.1:8020`，并保留精确 Host 白名单与 DNS 重绑定保护。

详细方案、验收状态与赛题映射见
[`OJGuard_项目方案.md`](OJGuard_项目方案.md)，赛题要求整理见
[`GOAI_Agent_Infra_赛道要求总结.md`](GOAI_Agent_Infra_赛道要求总结.md)。

参赛材料位于 `materials/` 与 `output/pdf/`：当前包含初赛方案 PDF、3～5 分钟演示脚本、
提交前检查清单和 AgentTeams 真实运行证据摘要。完整 Matrix 脱敏事件仅保留在本机
`.runtime/agentteams-demo-result.json`，不会把登录信息或 API Key 提交到仓库。

## 开源与第三方

OJGuard 采用 Apache-2.0 许可证。第三方项目、运行服务和许可证边界见
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。DeepSeek API 是外部商业服务，
API 密钥与模型输出不属于仓库开源内容。
