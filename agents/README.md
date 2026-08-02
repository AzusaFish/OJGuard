# OJGuard Agent Identities

本目录保存 AgentTeams 使用的角色身份和边界。`identities/*.yaml` 是机器可读源文件，初赛提交时据此生成参赛手册附录 A 清单。

所有 Worker 必须遵守：

- 不把模型判断直接标记为已确认 Finding；
- 不访问 Docker API、宿主命令或真实模型密钥；
- 只通过授权 Skill/MCP Tool 工作；
- 输出结构化 artifact_id、evidence_id 和错误状态；
- 高风险修改和最终发布必须交给人类。
