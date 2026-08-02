# OJGuard AgentTeams 真实运行证据

## 结论

2026-08-02，OJGuard 在 AgentTeams v1.2.0 的独立 kind/Kubernetes 环境中完成真实多智能体演示。Team Leader 与四名专业 Worker 均参与，最终输出 `OJGUARD_DEMO_COMPLETE`；运行 `RUN-DEMO-1E470FB440` 的发布门禁为 `BLOCKED`，审批状态为 `HUMAN_ONLY`。

## 安全边界

- AgentTeams Controller 使用 `workerBackend=k8s`；
- 5 个 OJGuard 角色使用 OpenClaw Runtime；
- Worker Pod、Manager Pod 和 Controller Pod均未挂载 Docker、Podman 或 containerd Socket；
- OJGuard MCP 只监听宿主机回环地址 `127.0.0.1:8020`，并保留 DNS 重绑定保护；
- MCP 仅精确允许 `127.0.0.1:8020`、`localhost:8020` 和 `host.docker.internal:8020` 三个 Host；
- 不可信题包程序只由 OJGuard Docker Runner 执行，Agent 本身不接触宿主机命令或 Docker Socket。

## 角色结果

| 角色 | Finding | Evidence | 结果 |
|---|---|---|---|
| Specification Auditor | `F-SPEC-RUN-DEMO-1E470FB440` | `E-SPEC-RUN-DEMO-1E470FB440` | Validator 与题面约束不一致，High |
| Solution Analyst | `F-OVERFLOW-RUN-DEMO-1E470FB440` | `E-OVERFLOW-RUN-DEMO-1E470FB440` | 标程整数溢出，Critical |
| Adversarial Test Engineer | `F-COVERAGE-RUN-DEMO-1E470FB440` | `E-COVERAGE-RUN-DEMO-1E470FB440` | 负数反例覆盖缺失，High；全量证据哈希复验成功 |
| Checker Auditor | `F-CHECKER-RUN-DEMO-1E470FB440` | `E-CHECKER-RUN-DEMO-1E470FB440` | Checker 接受非法尾随 Token，Critical |

四条 Evidence 的 SHA-256 完整性检查全部通过。没有生成补丁、没有代替人类审批、没有绕过发布门禁。

## 预算记录

从本次 AgentTeams 安装、平台初始化、失败保护演示和最终成功演示的本地 Session Usage 汇总：37 次 DeepSeek API 调用，224,440 个未缓存输入 Token、640,640 个缓存命中 Token、14,084 个输出 Token。

按照 2026-08-02 DeepSeek 官方页面中较贵的 V4 Pro 常规单价、公告的峰时 2 倍上限，并使用 7.5 的保守美元兑人民币换算，估算总成本不超过约 1.70 元。该数字不是账单；准确扣费以 DeepSeek 控制台为准。团队自主心跳现已关闭，平台 Manager 心跳延长至 24 小时，后续不会频繁后台消耗预算。

机器可读摘要见 `materials/evidence/agentteams_demo_summary.json`；完整脱敏 Matrix 事件保存在本地忽略目录 `.runtime/agentteams-demo-result.json`。
