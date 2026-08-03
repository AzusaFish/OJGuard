# Third-party notices

OJGuard 自有代码使用 Apache License 2.0。下列项目由各自作者拥有版权，使用时遵循
其许可证；本文件是依赖边界说明，不替代依赖包内的许可证原文。

| 项目 | 用途 | 许可证 / 边界 |
|---|---|---|
| AgentTeams v1.2.0 | 多 Agent 编排、Matrix、共享文件 | Apache-2.0；独立部署，不复制其源码 |
| Kubernetes kind v0.31.0 | 本地独立 Kubernetes 集群 | Apache-2.0；运行时下载并校验，不随仓库分发 |
| Helm v3.20.2 | 安装官方 AgentTeams Chart | Apache-2.0；运行时下载并校验，不随仓库分发 |
| Model Context Protocol Python SDK | MCP 服务端与客户端协议 | MIT |
| FastAPI、Pydantic、Uvicorn | 后端 API 与数据模型 | MIT / BSD-3-Clause |
| Vue、Vue Router、Pinia、Vite | 前端应用与构建 | MIT |
| Element Plus | 前端组件库 | MIT |
| Apache ECharts | 基准图表 | Apache-2.0 |
| PyYAML、python-dotenv、python-multipart | 配置与上传解析 | MIT / BSD 系许可证 |
| GCC / C++ 标准库 | Docker Runner 编译工具链 | 随基础镜像分发，遵循其各自许可证 |
| DeepSeek API | 可选的大模型服务 | 外部商业 API；密钥、账单和服务输出不随仓库分发 |

`frontend/package-lock.json` 和 Python 项目元数据固定直接依赖版本范围。发布材料或镜像前，
仍应对最终锁定的间接依赖执行一次许可证扫描，并随提交包保留完整 NOTICE/License 文件。
