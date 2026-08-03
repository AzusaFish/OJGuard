# OJGuard Agent Identities

本目录保存 OJGuard Incident Team 的 1 个 TeamLeader 与 6 个专业 Worker 身份卡。`identities/*.yaml` 是机器可读源文件，也是参赛手册附录 A 的一致性来源。

便于评审阅读的汇总清单位于 `materials/Agent_Identity_清单.md`，其中同时说明了角色编排、任务拆解、上下文传递、协同执行、状态追踪、验证、审批回滚和经验沉淀。

所有 Worker 必须遵守：

- 不把模型判断直接标记为已确认 Finding；
- 不访问 Docker API、宿主命令或真实模型密钥；
- 只通过授权 Skill/MCP Tool 工作；
- 输出结构化 artifact_id、evidence_id 和错误状态；
- 高风险修改和最终发布必须交给人类。

Incident Manager 只能从后端生成的合法 `RouteOption` 中选择，不得把固定宿主流程包装成模型决策。根因阶段允许多个实验候选和 `INCONCLUSIVE` 补选；灰度失败后只允许进入版本化恢复计划、重新审批或人工复核。
