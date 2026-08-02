# OJGuard 项目方案

> 基于 AgentTeams 的编程题包多智能体质量验证与发布门禁
>
> 版本：0.3.0（确认实施版）  
> 更新日期：2026 年 8 月 2 日

---

## 一、项目定义

### 1.1 项目名称

**项目名称：** OJGuard  
**参赛标题：** OJGuard——多智能体编程题包发布门禁  
**英文名称：** OJGuard: Multi-Agent Release Gate for Programming Problem Packages

后续代码仓库、界面、报告、PPT 和演示视频统一使用 **OJGuard**，不再使用其他产品名称。

### 1.2 一句话定位

> OJGuard 将人工验题中的规格核对、程序审查、反例搜索、Checker 审计和发布复核，转化为可执行、可验证、可审计的多智能体发布门禁。

### 1.3 核心判断

OJGuard 不宣称由大模型证明任意程序正确，而采用以下原则：

> **大模型提出风险假设，确定性程序验证假设，多 Agent 交叉制衡，最终由证据和发布规则作出决策。**

任何严重问题都必须附带静态证据、可复现反例或沙箱运行记录。没有确定性证据的结论只能标记为疑似问题或转交人工审核。

### 1.4 已确认的实施决策

| 项目 | 确认方案 |
|---|---|
| 代码仓库 | `https://github.com/AzusaFish/OJGuard` |
| 开源协议 | Apache-2.0 |
| 主场景 | OJ、算法竞赛和编程教育；技术招聘作为复制场景 |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + ECharts |
| 前端开发顺序 | 核心闭环与 API 稳定后集中开发 |
| 模型 | DeepSeek `deepseek-chat`，不默认调用 `deepseek-reasoner` |
| API 预算 | 总预算 10 元；6 元提醒，8 元停止非必要调用，保留 2 元用于演示 |
| RAG | 预留真实接口契约，初赛默认关闭 |
| 部署 | Windows + Docker Desktop，本地单用户、无登录、不公网部署 |
| Git | 使用 `develop` 开发分支；未经确认不推送、不发布 Release |
| 修复策略 | 自动生成候选补丁，人工批准后应用副本，回归通过后二次确认 |

---

## 二、问题、用户与价值

### 2.1 问题背景

在线评测、编程教育、企业招聘和高校课程在发布题目前，需要核对题面、题解、Validator、标准程序、测试数据和 Checker。现有题包工具擅长结构、格式、编译和已有测试检查，但以下问题仍高度依赖人工经验：

- 题面约束与 Validator 实际范围不一致；
- 标准程序存在整数溢出、边界遗漏或复杂度退化；
- 测试数据遗漏关键结构，使典型错误程序通过；
- Checker 未完整读取输出，错误接受非法结果；
- 修改后缺乏完整回归和可追踪的发布审批记录。

这些问题跨越自然语言理解、程序分析、测试生成、真实执行和安全审核，单一 Agent 难以同时可靠完成，且最终结论不能只依赖语言生成。

### 2.2 目标用户

- OJ 和编程教育平台的内容质量团队；
- 企业技术招聘和开发者认证团队；
- 高校程序设计课程教师；
- 算法竞赛出题、验题和裁判团队；
- 管理编程题库的研发与运营人员。

### 2.3 可验证价值

初赛不使用没有实验依据的商业收益数字。项目通过以下实测指标说明价值：

- 预埋缺陷召回率和确认问题准确率；
- 干净题包误阻断率；
- 新测试淘汰错误程序的数量；
- 严重 Finding 的证据完整率和重放成功率；
- 修复后完整回归通过率；
- 单题包运行时间、程序执行次数和模型调用成本。

---

## 三、初赛 MVP 范围

### 3.1 支持范围

为了保证在初赛截止前形成真实闭环，首版严格限定为：

- Kattis 风格或 OJGuard 标准目录格式的题包；
- C++17 标准程序、错误程序和 Checker；
- 非交互题；
- 标准输出或简单自定义 Checker；
- 单机 Docker 环境；
- 一次处理一个题包；
- 一个完整主 Demo，加 8～12 个原创小型基准题包。

### 3.2 非目标

初赛版本不实现：

- 任意程序的形式化正确性证明；
- Java、Python、Rust 等多语言执行；
- 交互题、输出型题和分布式压力测试；
- 完整 OJ 或生产发布平台；
- 自动覆盖原始题包；
- 用户注册、团队权限、支付和生产级账号系统；
- 公网部署和真实 OJ 发布；
- 完整 RAG、向量数据库、符号执行或 SMT 求解。

### 3.3 上下文能力选择

赛道要求在记忆、RAG、共享状态和轨迹可观测中至少实现两项。OJGuard 初赛实现：

1. **共享状态管理**：保存任务、假设、Finding、证据、补丁、审批和发布状态；
2. **轨迹可观测**：记录 Agent 决策、Skill 调用、工具执行、耗时、错误和证据关系。

同时预留 RAG Provider 和独立接口，使复赛接入向量数据库时无需修改 Agent 和 Skill 契约。初赛不实现知识入库和向量检索，因此不将 RAG 计入已经实现的上下文能力。

### 3.4 RAG 预留契约

- 内部服务端口：`8010`；
- API 前缀：`/api/v1/rag`；
- 开关：`RAG_ENABLED=false`；
- Provider 接口：`DisabledRagProvider`、未来可替换的 `VectorRagProvider`；
- 预留操作：文档写入、文档删除、语义检索和健康检查；
- 初赛行为：接口返回明确的 `RAG_DISABLED`，不得伪装成已完成检索；
- 前端行为：设置页显示“接口已预留，知识库未启用”。

---

## 四、总体架构

```text
              OJGuard Vue 3 控制台
     上传 / 进度 / Finding / 证据 / 审批 / 报告
                         ↓
                FastAPI 业务后端
                         ↓
                  Judge Manager
       ┌──────┼────────┬───────────┐
       ↓      ↓        ↓           ↓
规格审计 Agent  程序分析 Agent  对抗测试 Agent  Checker 审计 Agent
       └──────┴────────┴───────────┘
              ↓
       AgentSkill 能力层
              ↓
        OJGuard MCP Server
              ↓
      OJGuard Runner Service
       ├─ 题包标准化与基础检查
       ├─ 编译、执行和资源限制
       ├─ 测试生成与差分测试
       ├─ Checker 恶意输出测试
       └─ 证据保存与重放
              ↓
        临时隔离执行容器
              ↓
  AgentTeams 共享文件 + SQLite + Trace

Element / AgentTeams Dashboard：查看 Matrix 原始协作轨迹并供人工介入
```

### 4.1 推理与执行分离

Agent 负责理解、规划、提出风险假设、选择验证策略和解释结果。Runner 负责确定性的编译、运行、对拍、资源限制和证据固化。

Agent 不得：

- 直接访问 Docker Socket；
- 直接执行任意宿主机命令；
- 把自然语言判断直接写成已确认 Finding；
- 绕过发布策略修改最终状态；
- 覆盖原始题包。

### 4.2 技术栈

| 模块 | 初赛实现 |
|---|---|
| 多 Agent 协同 | AgentTeams v1.2.0，固定版本 |
| 业务前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、ECharts |
| Agent 原始协作界面 | Element，必要时使用 AgentTeams Dashboard |
| 后端与 Runner | Python 3.12、FastAPI、Pydantic |
| 工具协议 | 本地 OJGuard MCP Server；MCP Tool 使用 Pydantic/JSON Schema |
| 状态存储 | SQLite |
| Agent 共享文件 | AgentTeams MinIO 共享任务目录 |
| 执行沙箱 | Docker 临时容器，C++17/GCC |
| 题包基础检查 | problemtools 能力子集和 OJGuard 自有规则 |
| 可观测 | JSONL Trace、结构化日志和汇总指标 |
| 报告 | Markdown + 静态 HTML |
| 模型 | DeepSeek `deepseek-chat`，OpenAI 兼容调用方式 |
| RAG 预留 | 独立 `8010` 端口和 `/api/v1/rag` 契约，默认关闭 |

### 4.3 Vue 前端与 AgentTeams 的边界

OJGuard Vue 前端是比赛 Demo 的主要产品界面，负责题包上传、任务进度、Finding、Evidence、测试记录、补丁审批、回归结果、基准评测和系统设置。AgentTeams 负责真实的 Manager–Workers 调度、Matrix 消息、共享文件、Heartbeat 和人工介入，Vue 不模拟 Agent 工作。

后端把真实 AgentTeams 事件转换为结构化事件并通过 SSE 或 WebSocket 推送给 Vue，例如任务创建、Worker 接受任务、Hypothesis 产生、Runner 执行、Evidence 固化和 Finding 确认。Vue 的“查看 AgentTeams 原始轨迹”按钮在新窗口打开对应 Element 房间，不直接嵌入 Element，避免登录、跨域和界面冲突。

完整前端包含：

1. 系统总览；
2. 题包上传与新建审计；
3. 审计任务详情；
4. Agent 协作时间线；
5. Finding 与证据中心；
6. 测试用例和执行记录；
7. 补丁审批与回归；
8. 基准评测；
9. Agent、模型和系统设置。

前端采用中文界面、桌面优先和响应式布局，默认深色主题并支持浅色主题。为减少返工，前期先固定 OpenAPI、事件和数据 Schema，核心闭环稳定后再集中实现页面。

### 4.4 DeepSeek 成本与密钥控制

- `.env` 使用标准 `KEY=value` 格式，实际密钥不得进入 Git；
- `.gitignore` 必须忽略 `.env`，仓库只提交 `.env.example`；
- 统一变量为 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`；
- 开发测试默认使用 Mock Provider，只有集成验证和最终评测调用真实模型；
- 相同输入使用缓存，源码先做确定性预处理，只发送必要片段；
- 每个任务限制模型调用次数、输入长度和输出 Token；
- 记录 Token 与估算成本，但 Trace、日志、异常和前端永不输出密钥；
- 累计估算达到 6 元提醒，达到 8 元停止非必要真实调用并请求人工决定。

---

## 五、多 Agent 身份与边界

OJGuard 使用一个 Manager 和四个专业 Worker。四个 Worker 可以并行读取题包，但只能通过结构化任务、Matrix 消息和共享证据交换上下文。

| Agent | 核心职责 | 无权执行的操作 | 主要输出 |
|---|---|---|---|
| Judge Manager | 建立任务、拆解工作、追踪状态、处理冲突、触发门禁 | 不直接认定算法正确，不绕过人工审批 | TaskContext、任务分配、最终流程状态 |
| Specification Auditor | 提取题目契约，核对题面、配置、样例和 Validator | 不判定程序实现正确，不修改题包 | ProblemContract、规格冲突、歧义 |
| Solution Analyst | 分析算法、数值范围、边界分支和复杂度风险 | 不将未验证推断标记为 confirmed | Hypothesis、静态 Finding、验证计划 |
| Adversarial Test Engineer | 生成边界、差分、错误解驱动和变形测试 | 不批准补丁，不直接改变发布状态 | GeneratedTest、ExecutionRecord、反例 |
| Checker Auditor | 审计 Checker，并独立复核严重证据 | 不代表人类批准发布，不覆盖原题包 | 漏洞、绕过用例、证据复核结果 |

每个 Agent Identity 在复赛代码包中必须包含名称、身份、职责、能力边界、输入、输出、Skill、MCP Tool、协同关系、权限、失败处理和人工介入条件。初赛正式清单按参赛手册附录 A 排版，当前定义如下：

| Agent | 输入 | Skill / Tool | 失败处理 | 人工介入条件 |
|---|---|---|---|---|
| Judge Manager | package_id、策略、预算、共享状态 | 基础检查、Release Gate、任务管理 | Worker 超时后查询、重试、重派；预算耗尽则暂停 | 证据冲突、高风险补丁、最终发布 |
| Specification Auditor | 题面、配置、Validator、样例 | `extract-problem-contract`、只读文件工具 | 返回部分 Contract 并标记未知字段 | 来源冲突、题意歧义、无法解析格式 |
| Solution Analyst | Contract、标程、错误程序 | `audit-reference-solution`、源码读取工具 | 解析失败降级为编译诊断；推断保持 suspected | 算法语义不明确、静态结论与执行冲突 |
| Adversarial Test Engineer | Contract、Hypothesis、测试预算 | 测试生成、Validator、差分测试、重放 | 固定种子重试；Oracle 冲突或预算耗尽则停止 | Oracle 不可信、无法产生合法输入 |
| Checker Auditor | Checker、答案、输出契约、Finding | Checker 审计、恶意输出测试、证据复核 | 崩溃/超时安全拒绝并保存证据 | 修复可能改变多解或浮点语义 |

### 5.1 冲突处理

例如 Solution Analyst 判断存在溢出风险，但 Test Engineer 没有找到反例时，Manager 不选择相信其中一方，而创建新的验证任务：

1. 检查理论范围推导；
2. 扩大或定向构造极值；
3. 更换独立 Oracle；
4. 达到预算仍无法验证时转为 `HUMAN_REVIEW_REQUIRED`。

### 5.2 生成与审批分离

Worker 可以生成补丁建议，但不能批准。确定性 Release Gate 根据证据和规则给出建议状态，最终高风险修改和发布由人类确认。

---

## 六、AgentTeams 真实映射

OJGuard 不只在架构图中提到 AgentTeams，而按其运行方式实现以下映射：

| AgentTeams 能力 | OJGuard 实现 |
|---|---|
| Manager–Workers | Judge Manager 给四个专业 Worker 分配结构化验题任务 |
| Matrix Rooms | 展示任务分派、进度、冲突、重试和人工指令 |
| 共享文件 | 使用 `shared/tasks/{task_id}` 交换规格、假设、证据索引和结果 |
| Worker 隔离 | 每个 Worker 在独立容器内运行，只持有受限工具权限 |
| 人工介入 | 用户可暂停、追加约束、批准补丁、要求重试或拒绝发布 |
| 状态追踪 | Manager 更新任务元数据和 OJGuard 状态机 |
| Heartbeat | 已验证平台 Heartbeat；为保护 10 元预算，Team 自主心跳默认关闭、平台 Manager 调整为 24 小时 |
| 原始轨迹证明 | Vue 提供到对应 Element 房间的入口，评审可核验原始协作消息 |

### 6.1 安全部署实况

当前使用 AgentTeams v1.2.0 官方 Helm Chart 和独立 kind/Kubernetes 集群，Controller 的
`workerBackend` 为 `k8s`。平台 Manager、OJGuard Team Leader 与四个专业 Worker 均为真实
Pod；Controller、Manager、Worker 都没有挂载 Docker、Podman 或 containerd Socket。
v1.2.0 的 CoPaw 镜像在 Kubernetes 后端存在工作区路径与 MinIO 同步不兼容，因此当前采用
官方 Chart 的稳定 OpenClaw Runtime，并在材料中明确记录该兼容性选择。

### 6.2 共享任务目录

```text
shared/tasks/{task_id}/
├── meta.json
├── spec.md
├── context.json
├── contract.json
├── hypotheses.json
├── findings.json
├── evidence-index.json
└── result.md
```

Matrix 消息只传递摘要、状态和文件引用，不在 Agent 之间反复发送完整题包或无限长对话。

### 6.3 TaskContext

```yaml
task_id: T-001
package_id: PKG-001
run_id: RUN-001
stage: TESTING
contract_artifact_id: ART-010
active_hypothesis_ids: [H-001]
confirmed_finding_ids: [F-001]
evidence_ids: [EV-001, EV-002]
approval_state: NOT_REQUESTED
budgets:
  test_cases: 200
  execution_seconds: 180
  llm_calls: 20
```

---

## 七、Runner 沙箱与权限设计

### 7.1 独立 Runner

所有不可信代码由独立 `ojguard-runner` 接收结构化请求并在临时执行容器中运行。Agent 只能调用受限接口，不能提交任意 Shell 命令。

`ojguard-runner` 是受信任的控制面执行服务，也是唯一拥有创建临时执行容器权限的组件。初赛本地环境由它通过 Docker Desktop API 创建沙箱；AgentTeams Manager、Worker 和被测程序均不能访问 Docker API。下文“不挂载 Docker Socket”特指 Agent 容器和临时执行容器。生产环境应进一步把 Runner 部署在独立执行节点，并通过受限容器控制代理替代直接的宿主 Docker 权限。

Runner 的允许动作采用白名单：

- `inspect_package`；
- `compile_artifact`；
- `run_test_case`；
- `differential_test`；
- `validate_input`；
- `probe_checker`；
- `replay_evidence`。

### 7.2 沙箱限制

- 默认禁止网络；
- 题包以只读方式挂载，输出写入独立工作目录；
- 限制 CPU、内存、时间、进程数和输出大小；
- 不挂载宿主敏感目录、系统设备和 Docker Socket；
- 使用非 root 用户；
- 每次任务使用新容器并在结束后销毁；
- 所有结果先写入证据目录，再由 Runner 返回摘要和证据 ID。

### 7.3 风险等级

| 等级 | 示例 | 策略 |
|---|---|---|
| L0 | 读取题面、代码和配置 | 自动 |
| L1 | 编译、运行、生成临时测试 | 沙箱内自动 |
| L2 | 生成补丁、修改题包副本 | 需要人工批准 |
| L3 | 覆盖原题包、标记生产发布 | 必须人工审批，初赛 Demo 不执行真实发布 |
| L4 | 开放网络、访问生产凭证、任意宿主命令 | 默认禁止 |

### 7.4 三级修复权限

#### 第一级：自动生成候选补丁

系统可以自动生成 Diff，但不修改文件。首版支持：

- 扩大已由证据确认溢出的整数类型；
- Checker 强制读取到 EOF、拒绝多余 Token；
- Checker 拒绝 `NaN`、`inf` 和解析异常；
- 将已验证反例加入回归测试；
- 补充测试分组、必要元数据和可复现随机种子；
- 修正编译器能够确定的简单构建配置问题。

候选补丁必须关联 Finding、Evidence、风险等级、修改原因和预计回归范围。

#### 第二级：人工批准后应用工作副本

用户在 Vue 前端查看文件 Diff 和证据后批准。系统只修改独立工作副本，保存补丁、审批人、审批时间和修改前后哈希。拒绝或撤销审批时不得修改。

#### 第三级：完整回归后二次确认

补丁应用后重新执行基础检查、原始测试、新增回归测试、Oracle 对拍、错误程序测试和 Checker 攻击测试。全部通过只能产生 `READY_FOR_RELEASE` 建议，必须由用户二次确认；初赛不连接真实 OJ 发布接口。

### 7.5 只建议与永远禁止的操作

题面与 Validator 冲突、时间/内存限制、浮点误差、多解规则、标准算法、题目语义和评分规则只生成候选方案，必须由人工选择。

系统永远禁止自动覆盖或删除原题包、删除原始测试、发布到真实 OJ、关闭安全检查、开放执行容器网络、访问生产凭证、执行任意宿主命令，以及在回归失败后强制标记通过。

---

## 八、核心 Skill 工程体系

### 8.1 统一返回结构

```yaml
skill: string
version: string
invocation_id: string
status: SUCCESS | PARTIAL | FAILED | HUMAN_REVIEW
outputs: object
finding_ids: string[]
evidence_ids: string[]
metrics:
  duration_ms: integer
  tool_calls: integer
error:
  code: string | null
  retryable: boolean
  message: string | null
```

### 8.2 Skill 清单

| Skill | 输入 | 输出 | 调用条件 | 验证与失败处理 | 安全边界 |
|---|---|---|---|---|---|
| `inspect-problem-package` | package_id、format | 文件清单、基础错误、编译目标 | 题包收到后 | Schema/编译检查；格式错误立即阻断 | 只读题包，不执行未知脚本 |
| `extract-problem-contract` | package_id、statement/validator artifact_id | Contract、冲突、歧义 | 基础检查通过后 | 每个字段保留来源；冲突转人工 | 只读，无网络 |
| `audit-reference-solution` | contract_id、solution_id | 算法摘要、风险假设、静态证据 | Contract 生成后 | 推断不直接确认；解析失败返回 partial | 只读源码，不直接执行 |
| `generate-adversarial-tests` | contract_id、hypothesis_id、budget、seed | 测试 artifact_id、覆盖标签 | 存在待验证假设 | 每个输入先通过 Validator；固定种子可重放 | 限制数量和文件大小 |
| `differential-test-solutions` | oracle_id、candidate_ids、case_ids、limits | 分歧、执行记录、反例 | 测试生成后 | Oracle 冲突转人工；超时终止；调用幂等 | 仅通过 Runner 沙箱执行 |
| `audit-output-validator` | checker_id、answer_id、output_contract_id | 漏洞、绕过用例、补丁建议 | 存在 Checker 时 | 绕过必须由真实 Checker 执行确认 | 恶意输出限制大小，不允许命令注入 |
| `release-gate-problem-package` | findings、evidence、approval、policy | 决策、阻断项、必要动作 | 专业检查完成后 | 纯规则程序；证据缺失不得 PASS | 不修改文件，不代替人工批准 |

### 8.3 版本、幂等与回滚

- Skill 使用语义化版本；
- 同一 `invocation_id` 重试不重复创建 Finding；
- 工具调用记录 Skill、Runner、编译器和规则版本；
- 新版本发布前运行基准集；
- 指标退化时回滚到上一固定版本；
- 规则变化不得修改既有历史证据。

### 8.4 MCP 权限、依赖与复用

OJGuard 选择实际实现本地 MCP Server，而不是只保留“未来可迁移”的等价接口。MCP Server 只向 Worker 暴露 `inspect_package`、`compile_artifact`、`run_test_case`、`validate_input`、`differential_test`、`probe_checker` 和 `replay_evidence` 白名单工具。

- **协议与 Schema**：MCP Tool 输入输出由 Pydantic 模型生成 JSON Schema；
- **鉴权**：Worker 使用 AgentTeams/Higress 下发的受限消费者身份，不持有真实服务密钥；
- **最小权限**：规格和程序 Agent 只读，测试和 Checker Agent 才能请求执行任务；
- **审计**：每次调用记录 invocation_id、Agent、Tool、参数摘要、版本、耗时、错误码和 Evidence；
- **超时与重试**：只对标记为 retryable 的基础设施错误有限重试；
- **幂等**：相同 invocation_id 不重复生成 Finding 或修改副本；
- **降级**：MCP 不可用时任务进入 FAILED/HUMAN_REVIEW，不把失败视为通过；
- **复用**：题包检查、差分测试、Checker 探测和证据重放可以被其他 Agent、CI 或外部 OJ 适配器独立调用。

---

## 九、证据与状态模型

### 9.1 结论等级

```text
CONFIRMED              已有可复现运行证据
STATICALLY_PROVEN      有确定性静态规则或范围证明
SUSPECTED              只有模型推断或弱证据
HUMAN_REVIEW_REQUIRED  证据冲突、语义不明确或超出能力边界
```

### 9.2 Finding

```yaml
id: F-001
package_id: PKG-001
run_id: RUN-001
source_agent: solution-analyst
category: integer_overflow
severity: critical
confidence_class: CONFIRMED
description: 标准程序使用 int32 保存理论上可达 2e14 的结果
hypothesis_id: H-001
evidence_ids: [EV-010, EV-011, EV-012]
replay_action: replay_evidence
requires_human_review: false
```

### 9.3 Evidence

```yaml
id: EV-010
type: differential_execution
producer: ojguard-runner
artifact_path: artifacts/PKG-001/RUN-001/executions/EV-010.json
sha256: string
created_at: string
tool_version: string
seed: 42
inputs: [ART-101]
outputs: [ART-102, ART-103]
```

### 9.4 证据目录

```text
artifacts/{package_id}/{run_id}/
├── manifest.json
├── contract.json
├── hypotheses.json
├── findings.json
├── trace.jsonl
├── cases/
├── executions/
├── patches/
└── report.html
```

### 9.5 状态机

```text
RECEIVED
  → BASELINE_VALIDATING
  → ANALYZING
  → TESTING
  → EVIDENCE_REVIEW
  → BLOCKED / HUMAN_REVIEW_REQUIRED / PASS_CANDIDATE
  → PATCH_PENDING_APPROVAL
  → REVALIDATING
  → READY_FOR_RELEASE / BLOCKED
```

任意阶段还可以进入 `FAILED`、`CANCELLED` 或 `BUDGET_EXHAUSTED`，不得把工具失败当作检查通过。

---

## 十、端到端闭环

1. 用户上传题包，系统计算摘要并生成不可变原始副本；
2. Manager 创建任务，调用基础检查 Skill；
3. 规格 Agent 与程序 Agent 并行产生 Contract 和 Hypothesis；
4. 测试 Agent 根据 Hypothesis 生成测试并调用 Runner；
5. Checker Agent 并行执行输出校验攻击，并复核严重证据；
6. Manager 对冲突结论创建补充验证任务；
7. Release Gate 检查严重度、证据完整性和审批状态；
8. 严重问题使题包进入 `BLOCKED`；
9. Worker 生成带 Diff、风险和证据的候选补丁，不修改文件；
10. 用户第一次审批后，系统只修改题包工作副本；
11. 回归失败时放弃修改副本并保持 `BLOCKED`；
12. 全部门禁通过后生成 `READY_FOR_RELEASE` 建议和审计报告；
13. 用户进行第二次审批，确认候选题包可发布；
14. 初赛只记录发布决定，不连接或操作真实 OJ；
15. 已确认 Finding、最小反例、补丁结果和失败策略沉淀为回归测试、错误模式条目和后续基准资产。

---

## 十一、主 Demo

### 11.1 Demo 题目

使用团队原创的 **Maximum Segment Score** C++17 题包，预埋四类缺陷：

1. 题面声明 `|a_i| <= 10^9`，Validator 实际限制为 `10^6`；
2. 标程使用 32 位整数保存理论上可达 `2 × 10^14` 的结果；
3. 原测试不包含负数，使一个错误贪心程序通过；
4. Checker 只读取第一个整数，接受尾随非法输出。

### 11.2 预期演示结果

```text
发布结论：BLOCKED

已确认严重问题：
- 标程整数溢出：提供极值输入、标程输出、Oracle 输出和重放入口
- Checker 接受尾随输出：提供恶意输出和 Checker 返回记录

已确认中等问题：
- 题面与 Validator 约束不一致：提供双来源定位
- 原测试遗漏负数：提供错误程序最小反例
```

用户批准后，系统修改题包副本、补充回归测试并修复确定性问题。重新运行后给出新的发布状态和修复前后对比。

### 11.3 必须演示的异常路径

至少展示以下一个异常：

- Oracle 与另一独立实现产生冲突；或
- 候选程序编译失败；或
- 测试任务超时并耗尽预算。

系统必须转入重试、降级或人工审核，不能把异常隐藏在最终报告中。

---

## 十二、基准评测设计

仅靠一个预设 Demo 不足以证明能力。初赛建立 8～12 个团队原创的小型题包：

| 类别 | 建议数量 |
|---|---:|
| 整数范围和边界缺陷 | 2 |
| Validator/题面不一致 | 2 |
| 错误程序漏测 | 2～3 |
| Checker 漏洞 | 2 |
| 干净题包 | 2～3 |

每个题包提供机器可读标签：

```yaml
package_id: BENCH-001
expected_findings:
  - category: integer_overflow
    severity: critical
clean_package: false
```

### 12.1 报告指标

- 缺陷级 Precision、Recall；
- 严重缺陷召回率；
- 干净题包误阻断率；
- 证据完整率；
- 重放成功率；
- 新测试淘汰错误程序数量；
- 平均运行时间和 P95；
- Agent、Skill、LLM 和程序执行次数；
- 修复前后完整回归通过率。

所有数值以实际实验结果填写，不预先承诺未经验证的效果。

---

## 十三、初赛验收标准

提交前必须满足：

- AgentTeams 真实运行，版本和部署方法明确；
- 四个专业 Worker 真实交换任务、状态和证据；
- 主 Demo 的四类缺陷均由真实工具验证；
- 每个严重 Finding 具备证据 ID 和重放入口；
- 至少展示一次异常、重试或人工接管；
- 至少完成一次候选补丁审批和完整回归；
- 至少完成一次回归通过后的二次发布确认；
- Vue 前端展示的 Agent 事件能够追溯到 AgentTeams 原始轨迹；
- 原始题包不被覆盖；
- 基准集包含缺陷题包和干净题包；
- 生成真实量化报告，不只展示主观案例；
- 提供 README、运行入口、示例配置、测试方法和开源许可证。

建议内部目标，而非对外提前宣称的成绩：

- 主 Demo 四类缺陷检出率 100%；
- 主 Demo 严重 Finding 证据完整率 100%；
- 主 Demo 证据重放成功率 100%；
- 干净题包不得因工具错误直接进入 `READY_FOR_RELEASE` 或错误隐藏失败；
- 指定演示机器上单题包流程控制在 5 分钟内。

---

## 十四、完成计划与责任划分

本计划按依赖关系和风险排序，不再绑定具体日期。标记说明：

- **[Codex]**：可以由 Codex 在本地仓库中独立实现、测试和整理；
- **[你]**：必须由参赛者本人判断、授权、填写或提交；
- **[共同]**：Codex 先提供成品或候选项，由你作最终确认。

### P0：已完成并已有运行证据

- [x] **[Codex]** 建立 FastAPI、SQLite、状态机、预算保护和安全 ZIP 导入；
- [x] **[Codex]** 建立 Docker C++17 Runner 与 CPU、内存、时间、进程、网络和输出限制；
- [x] **[Codex]** 实现 Validator、Oracle、错误程序、Checker 探测及证据重放；
- [x] **[Codex]** 实现 Finding、Evidence、SHA-256 校验、JSONL Trace、JSON/HTML 报告；
- [x] **[Codex]** 实现纯规则 Release Gate、工作副本、双审批和五项完整回归；
- [x] **[Codex]** 完成 7 个 Skill、8 个 MCP 工具和 MCP HTTP 服务；
- [x] **[Codex]** 完成 10 个原创基准题包及确定性评测脚本；
- [x] **[Codex]** 完成 Vue 3 控制台并通过桌面、移动端和交互检查；
- [x] **[Codex]** 预留 `8010` RAG 契约并保持默认关闭；
- [x] **[Codex]** 完成 README、CI 与第三方依赖边界说明。

**现有验收证据：** 自动化测试通过；前端类型检查与正式构建通过；真实 Docker 主 Demo
稳定发现四类缺陷并生成 4 条 Finding、4 份 Evidence 和 `BLOCKED` 报告；补丁闭环已验证
原题包哈希不变；确定性基准 8/8 缺陷命中、0/2 干净题包误阻断、基准 LLM 调用为 0；
AgentTeams 真实协作已产生四角色回复、证据哈希复验和 Leader 汇总标记。

### P1：AgentTeams 真实协作链路

- [x] **[Codex]** 固定 AgentTeams v1.2.0，完成平台 Manager、Team Leader、四个专业 Worker、Team、MCP 和资源限制清单；
- [x] **[你]** 选择方案 B：AgentTeams 不挂载本机 Docker Socket；
- [x] **[Codex]** 安装独立 kind/Kubernetes 环境并验证 Matrix、MinIO、Element、K8s Worker 与 Heartbeat；
- [x] **[Codex]** 通过 AgentTeams 完成真实协作 Demo，保存脱敏 Matrix 轨迹、工具调用、四角色回复和 Leader 汇总；
- [x] **[Codex]** Vue 架构与设置页显示 K8s 安全状态，并提供 Element 原始房间入口；
- [ ] **[共同]** 评估真实协作结果是否足以证明不是顺序脚本，并选择演示中最清晰的一条冲突/重派路径。

### P2：模型集成与成本评估

- [x] **[Codex]** 完成 DeepSeek 环境变量、模型选择和 6/8 元预算门禁设计；
- [x] **[你]** 确认允许开始真实 API 评测，并核对 `.env` 中密钥有效、余额可用；
- [x] **[Codex]** 复用确定性 run 完成小样本调用，记录缓存命中与 Token；
- [x] **[Codex]** 本轮保守成本上限估算约 1.70 元，未达到 6 元提醒阈值；
- [ ] **[共同]** 判断模型输出对规格提取、风险假设与任务分派是否带来可展示的增益；若没有增益，不把模型效果作为核心卖点。

### P3：提交材料与最终演示

- [x] **[Codex]** 完成 500 字以内作品简介初稿、PPT 叙事结构、Agent Identity 与 Skill 清单；
- [x] **[Codex]** 生成 14 页方案 PDF，加入真实反例、Trace、基准和安全边界，并完成逐页渲染检查；
- [ ] **[共同]** 审阅 PPT 中的产品定位、创新点、行业价值和对外表述；
- [ ] **[你]** 提供参赛主体、团队/学校/企业名称、成员分工、Logo 和需要披露的联系信息；
- [x] **[Codex]** 编写 3～5 分钟 Demo 脚本、镜头顺序和故障备用方案；
- [ ] **[你]** 录制或出镜，并确认声音、隐私和展示账号可以提交；
- [ ] **[Codex]** 在干净环境执行最终复现、密钥扫描、许可证检查和提交包一致性审计；
- [ ] **[你]** 登录比赛平台，确认官方字段、文件大小和截止时间，完成最终上传。

### 完成定义

项目完成不是“页面能打开”，而是同时满足：AgentTeams 真实协作可核验、主 Demo 可重放、
补丁双审批不越权、基准数字可重算、报告与代码一致、材料无密钥和虚假结论，并由你完成
安全部署方案、模型费用与最终提交三类人工确认。

---

## 十五、初赛 PPT 叙事

建议采用以下 14 页结构：

1. 编程题包发布为什么仍依赖专家验题；
2. 现有格式工具无法覆盖的高价值问题；
3. OJGuard 的目标用户与边界；
4. “模型提出假设、程序验证假设”的核心理念；
5. 五个 Agent 的真实职责与制衡；
6. AgentTeams 的运行映射和共享任务；
7. Skill、工具和独立 Runner 架构；
8. 不可信代码的安全沙箱；
9. 主 Demo 的四类缺陷；
10. 可复现 Evidence 和 Trace；
11. 人工审批、回滚和异常路径；
12. 基准集与真实量化结果；
13. 跨 OJ、教育和招聘平台的复用方式；
14. 当前进展、开源内容和复赛计划。

---

## 十六、风险与应对

### 16.1 模型分析不可靠

模型输出默认是 Hypothesis。只有确定性规则或真实运行可以将其升级为 confirmed Finding。

### 16.2 Demo 被认为是预设脚本

除主 Demo 外提交原创基准集、干净题包、批量结果和可复算脚本，并现场改变随机种子或测试预算。

### 16.3 Docker-in-Docker 和高权限风险

Agent 永不持有 Docker Socket。只有独立 Runner 具有受限的执行容器创建能力，对外只暴露白名单任务接口。

### 16.4 AgentTeams 运行兼容性

v1.2.0 CoPaw Kubernetes 镜像的工作区与 MinIO 同步路径不一致，当前显式回退到官方 OpenClaw Runtime。演示前先用零模型 MCP 调用验证 Runner 链路，真实协作复用已生成 run，减少模型工具循环和费用。

### 16.5 题意契约提取过度承诺

初赛只支持 Demo 所需的整数、数组、范围和输出类型，并保留来源定位。无法可靠提取的字段标记未知或转人工，不伪造确定结论。

### 16.6 自动修复改变题意

自动修复只作用于副本。初赛优先演示整数类型和 Checker 尾随输出等确定性补丁；涉及题面语义的约束冲突由人工选择修复方向。

---

## 十七、复赛增强方向

初赛闭环稳定后，再按优先级扩展：

1. 在已预留的 Provider 契约上实现历史 Finding、错误模式和规范 RAG；
2. 标准 Kattis、DOMjudge 和 Polygon 适配器；
3. Java、Python、Rust 等多语言；
4. 更丰富的 Checker 和浮点输出测试；
5. 错误解驱动的最小反例搜索；
6. OpenTelemetry/AgentLoop 可观测接入；
7. CI 插件和真实 OJ 发布接口；
8. 公开的题包缺陷与反例基准集。

---

## 十八、开源计划

OJGuard 核心工程计划采用 Apache-2.0 许可证，开源：

- Agent Identity 和协作配置；
- AgentSkill 定义与 Schema；
- OJGuard Runner 和受限工具接口；
- 题包适配器；
- 差分测试和证据重放工具；
- Checker 审计规则；
- 原创 Demo 与基准题包；
- 审计报告模板；
- 部署、测试和 Skill 接入文档。

第三方模型、AgentTeams、编译器和 problemtools 分别列明版本、许可证、调用边界和替代方式。仓库不提交 API Key、个人信息或来源不明的竞赛题包。

仓库在本地 `develop` 分支完成阶段性开发。每个里程碑形成独立提交；推送远程、创建 PR 和发布 Release 均在人工确认后进行。

---

## 十九、初赛 500 字以内作品简介草案

**OJGuard** 是面向在线评测、编程教育和技术招聘的多智能体题包质量验证与发布门禁。传统工具能检查格式、编译和已有测试，却难以发现题面与 Validator 不一致、标程溢出、测试遗漏错误算法及 Checker 绕过等问题。

OJGuard 基于 AgentTeams 构建 Judge Manager 与规格审计、程序分析、对抗测试、Checker 审计四个 Worker。系统坚持“大模型提出风险假设、确定性程序验证假设”：Agent 负责理解和规划，独立 Runner 在沙箱中完成编译、对拍和 Checker 测试。严重问题必须附带可重放证据；补丁仅作用于副本，经人工批准和回归后才能通过门禁。

项目将规格提取、程序审计、差分测试、Checker 审计和发布门禁沉淀为可复用 Skill，通过共享状态与 Trace 保存证据。当前 Demo 已真实发现四类预埋缺陷，完成双审批修复回归，并以 10 个原创题包报告确定性基线的召回率、误阻断率和成本。核心代码、Agent、Skill、Runner、前端、Demo 与基准集采用 Apache-2.0 开源。

---

## 二十、项目价值总结

OJGuard 解决的不是“让 AI 帮忙做题”，而是：

> **如何让一套编程测评内容在发布前经过多角色协作、真实程序验证、安全审批和可复现审计。**

项目的竞争力不来自 Agent 数量或工具数量，而来自一个可现场验证的事实链：

```text
风险假设
→ 定向测试
→ 沙箱执行
→ 可复现证据
→ 独立复核
→ 人工审批
→ 完整回归
→ 发布门禁
```

---

## 二十一、赛题要求符合性审阅

本表区分“已有本地证据”和“仍需参赛者确认”。不得把确定性基线结果表述为 AgentTeams
或大模型效果。

### 21.1 硬性要求

| 赛题要求 | OJGuard 对应内容 | 方案状态 | 提交前证据 |
|---|---|---|---|
| 至少 3 个不同职能 Agent | Team Leader + 4 个专业 Worker，另有平台 Manager | 5 个角色均真实运行并完成协作 | Matrix 四角色回复与 Leader 汇总已保存 |
| 以 AgentTeams 为协同基点 | Manager–Workers、Matrix、MinIO、Heartbeat、Element | v1.2.0 K8s 环境已运行 | Element 房间、MinIO 工作区和 Pod 状态可现场核验 |
| Agent Identity 清单 | 身份、边界、I/O、Skill、权限、失败与人工介入 | 5 份 YAML 已完成并测试 | 材料中导出正式表格 |
| Skill 必选 | 7 个核心 Skill、统一返回、版本和回滚 | 7 份 `SKILL.md` 已完成并验证 | 演示中调用 OJGuard MCP 并按角色约束回复 |
| MCP 或等价工具契约 | 本地 OJGuard MCP Server | 8 个工具已实现，AgentTeams 端真实调用通过 | `get_run_bundle` 与 `verify_run_evidence` 轨迹已保存 |
| 至少两项上下文能力 | 共享状态管理 + 轨迹可观测 | SQLite、Evidence、JSONL Trace、Matrix 已运行 | 提交结构化摘要并现场打开 Element |
| 端到端任务闭环 | 上传—分析—验证—审批—修复—回归—确认—沉淀 | 确定性闭环与 AgentTeams 协同段均通过 | 视频中连接协同段与人工审批段 |
| 结果验证 | 编译、Validator、Oracle、差分和 Checker 探测 | 真实 Docker 执行通过 | 提交可重放反例与命令 |
| 执行证据 | Finding、Evidence、哈希、Trace、报告 | 4 Finding、4 Evidence、JSON/HTML 报告已生成 | 截图并打包脱敏产物 |
| 审批、回滚和审计 | 三级权限、双审批、工作副本和完整回归 | 已验证，原题包哈希不变 | 用真人审批重录最终 Demo |
| 经验沉淀 | Finding、反例、修复结果转为回归与基准资产 | 10 题基准与回归脚本已完成 | 增加 Agent 经验回写示例 |

### 21.2 初赛提交要求

| 材料 | 当前状态 | 提交前动作 |
|---|---|---|
| 项目名称约 20 字 | 符合：OJGuard——多智能体编程题包发布门禁 | 保持统一名称 |
| 500 字以内简介 | 已按真实进展更新 | 提交平台粘贴后复核字数 |
| 方案 PPT/PDF | 14 页 PDF 已生成并逐页检查 | 用真实 AgentTeams 证据更新状态页后终审 |
| AgentTeams 代码包 | K8s、Team/Worker/MCP 配置和复现脚本已完成 | 提交前执行一次干净复现 |
| 样例输入输出和证据 | 已生成真实 Demo 产物 | 选择脱敏产物纳入提交包 |
| 开源协议与边界 | Apache-2.0 与第三方 NOTICE 已完成 | 发布前扫描间接依赖 |

### 21.3 评分维度审阅

| 评分维度 | 当前方案判断 | 主要补强证据 |
|---|---|---|
| 场景价值与行业可复制性 25% | 主场景收敛，已有原创基准 | 仍需用户/访谈证据或真实题包案例 |
| 多 Agent 协同与自主闭环 25% | 真实五角色协作、并行回复与 Leader 汇总已完成 | 视频突出 4/4 分工、证据复核和人工门禁 |
| Skill 工程体系与生态复用 25% | 7 个 Skill、8 个 MCP 工具与真实调用已完成 | 补外部题包适配示例 |
| 工程落地、安全与可审计 20% | Runner、Trace、报告、审批和前端已有证据 | 补干净环境一键复现与异常视频 |
| 开放与开源贡献 5% | 许可证、CI、Demo 和基准边界清晰 | 推送后检查仓库可访问性和 NOTICE |

### 21.4 审阅结论

OJGuard 的场景、五 Agent 分工、七个 Skill、两项上下文能力、确定性验证、证据、双审批、
回归和开源边界符合赛题方向。AgentTeams v1.2.0 已在无宿主 Socket 的 Kubernetes 后端
真实运行，Matrix 中存在四角色回复、MCP 工具调用、证据完整性复核和 Leader 汇总。
当前技术硬性缺口已由“真实协作未启动”转为“提交材料尚未全部换成真实轨迹截图”；此外仍需
参赛者提供主体信息、复核对外表述、录制视频并完成平台上传。PPT 和视频必须继续明确区分
确定性基线、AgentTeams 协作结果和模型输出，不能把 8/8 基准命中率写成 LLM 指标。
