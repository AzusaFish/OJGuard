# OJGuard

基于 AgentTeams 的编程题包多智能体质量验证与发布门禁。

> 当前状态：工程骨架开发中。比赛材料中的“计划实现”不代表已经产生运行证据。

## 已确定范围

- C++17、非交互题；
- AgentTeams Manager + 四个专业 Worker；
- FastAPI 后端与独立 Runner；
- Vue 3 完整前端；
- SQLite、共享任务文件与 JSONL Trace；
- DeepSeek `deepseek-chat`，开发期默认 Mock；
- RAG 接口预留，初赛默认关闭。

## 本地开发

1. 将 `.env.example` 复制为 `.env` 并填写 `DEEPSEEK_API_KEY`；
2. 启动后端：`python -m uvicorn backend.app.main:app --reload --port 8000`；
3. 健康检查：`http://127.0.0.1:8000/api/v1/health`；
4. 运行测试：`python -m unittest discover -s tests -v`。

真实模型调用默认关闭，后续通过配置显式启用。不要提交 `.env`。

## 文档

- `OJGuard_项目方案.md`：确认实施版项目方案；
- `GOAI_Agent_Infra_赛道要求总结.md`：赛题要求与提交检查清单。

## License

Apache-2.0
