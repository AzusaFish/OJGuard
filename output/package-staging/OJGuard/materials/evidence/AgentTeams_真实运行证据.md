# OJGuard AgentTeams 真实运行证据

## 结论

- Team：`ojguard-incident-team`；
- Team Leader：`ojguard-incident-manager`；
- Worker：6 个，状态 `Running`，Team 状态 `Active 6/6`；
- 模型：DeepSeek `deepseek-chat`；
- 任务：`OJGUARD-FINAL-20260802`；
- 事故：`INC-67AAB2379B`；
- 最终状态：`RESOLVED`；
- 六个 Worker 均留下独立 `WORKER_COMPLETE` 响应，Team Leader 在收到六项结果后完成汇总；
- 原始脱敏事件见 `output/evidence/agentteams/agentteams-demo-result.json`。

## 六个 Worker 与工具证据

| Worker | 唯一工具调用 | 运行结论 |
|---|---|---|
| Signal Aggregator | `incident.list_signals` | 失败率 8.3%→41.4%，镜像部署后 21 分钟出现同代码超时投诉；只确认时间相关，不直接判根因 |
| Root Cause Analyst | `judge.replay_submission` | 读取带 SHA-256 的真实 Runner 对照证据；正常镜像 3/3 OK，退化镜像 3/3 TLE，结论可复现 |
| Impact Analyst | `impact.calculate_scope` | 703 名候选人、742 条提交、703 项预计成绩变化、72 项预计晋级变化 |
| Remediation Planner | `rejudge.create_plan` | 控制 20、灰度 38、全量 500+184；控制/灰度失败即停，全量需要 L3 业务审批 |
| Rejudge Executor | `score.calculate_changes` | 计算 703 项成绩变化，不执行正式成绩写回 |
| Verification Auditor | `verification.verify_incident` | RESOLVED，覆盖率 100%，重复 0、遗漏 0、越界 0 |

## Team Leader 汇总

Team Leader 先调用 `report.generate_incident_report` 取得事故报告，再接收六项独立检查结果。最终消息包含：

- `task_id=OJGUARD-FINAL-20260802`；
- `incident_id=INC-67AAB2379B`；
- `stage=RESOLVED`；
- 六类角色结论；
- `OJGUARD_DEMO_COMPLETE` 完成标记；
- 单人角色模拟披露。

## 审批与权限边界

- MCP 不提供批准接口；Agent 不能批准全量重评、成绩写回、通知或事故关闭；
- AgentTeams Pod 不挂载 Docker、Podman 或 containerd Socket；
- Java 实验由宿主侧受控 Runner 生成证据，Worker 只读取带哈希的结果；
- 单人参赛者在 OJGuard 工作台中切换技术审批/业务审批角色上下文；这用于验证职责门禁，不表示真实多人签批；
- 演练只作用于模拟事故和临时成绩，不连接真实 OJ 或正式成绩库。

## 可复核文件

- `output/evidence/agentteams/agentteams-demo-result.json`：六个 Worker 的脱敏事件、发送者、时间和 Team Leader 最终消息；
- `output/evidence/java-runtime-comparison.json`：正常/退化 Java 运行时对照实验；
- `output/evidence/incidents/runtime-regression-report.json`：主事故闭环报告；
- `agentteams/ojguard-team.yaml`：Team/Worker 配置；
- `scripts/run_agentteams_demo.ps1`：有响应上限的协作演练；
- `scripts/export_agentteams_evidence.ps1`：脱敏证据导出。
