# OJGuard DeepSeek 最终验收报告

## 结论

2026-08-03 完成真实 AgentTeams + DeepSeek 端到端验收。权威验收任务为 `OJGUARD-FINAL-ACCEPT-20260803-B`，事故为 `INC-D4B166F492`，最终状态为 `RESOLVED`。验收通过。

## 核心结果

- 事故从干净的 `TRIAGING` 状态开始，仅包含 22 条原始信号，不含预计算根因、实验、影响或处置方案；
- Incident Manager 完成 11 次动态路由决策；
- Signal、Root Cause、Impact、Remediation、Rejudge、Verification 六个专业 Worker 全部参与；
- 产生 8 次结构化 Worker 响应；
- 持久化 2 个竞争假设和 1 个二维对照实验；
- 精确识别 703 名候选人、742 条受影响提交及 72 项晋级变化；
- 控制组 `20/20`、灰度 `38/38`、全量 `500+184` 均执行成功；
- 独立验证覆盖率为 100%，重复、遗漏和越界均为 0；
- 技术审批、业务审批和关闭审批均由参赛者以不同角色上下文手动完成，没有启用自动审批；
- 最终证据包含 11 次路由、8 次 Worker 响应和 1 次最终报告，共 20 条当前事故的有效逻辑响应；
- 最终报告同时绑定当前 `task_id`、`incident_id`、初始/最终状态和唯一完成标记。

## 审查中发现并修复的问题

1. Windows PowerShell 会把 Python 标准错误过早提升为终止错误，导致 Traceback 被截断；现已完整捕获进程输出后再判断退出码。
2. PowerShell 原生命令行会破坏 JSON 与多行摘要参数；现改为 UTF-8 Base64 传递元数据和摘要。
3. Windows PowerShell 默认 GBK 会导致中文状态输出失败；运行脚本现固定使用 UTF-8。
4. 恢复逻辑曾从共享 Team Leader 房间读取其他事故的路由和最终报告；现只从当前 `AgentRunEvent` 恢复路由，且所有新路由和最终报告均强制绑定当前 `incident_id`。
5. Matrix 流式输出可能产生部分片段和重复完整片段；现只接受最后一个完整、唯一、绑定当前事故的最终报告事件。
6. 直接执行脚本曾可绕过前端的真实调用开关；脚本现在也强制检查 `LLM_REAL_CALLS_ENABLED=true`。

## 安全与费用边界

- 验收结束后已恢复 `LLM_REAL_CALLS_ENABLED=false`；
- 导出的 JSON 未发现 API Key、Access Token、Password 或 `sk-...` 密钥模式；
- 证据文件只记录脱敏的路由、Worker、工具、审批、状态和报告；
- 诊断和最终报告重生成期间产生过额外外部调用，实际计费 Token 与金额应以 DeepSeek 控制台为准；项目不伪造厂商账单数据；
- 最终提交证据中的逻辑闭环严格归属于当前事故，不混入诊断事故或其他历史任务。

## 权威证据

- `output/evidence/agentteams/agentteams-demo-result.json`
- SQLite `AgentRun`：`ARUN-EF5F1CF60AF7`
- SQLite `IncidentContext`：`INC-D4B166F492`
- `output/evidence/incidents/runtime-regression-report.json`

