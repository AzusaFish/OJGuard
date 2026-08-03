import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const presentation = await PresentationFile.importPptx(await FileBlob.load('./template-starter.pptx'));
const output = '../../output/submission/OJGuard_项目介绍.pptx';

function shape(slideNumber, id) {
  return presentation.slides.items[slideNumber - 1].shapes.getById(String(id));
}

function setText(slideNumber, id, value) {
  const item = shape(slideNumber, id);
  if (!item) throw new Error(`Missing shape ${id} on slide ${slideNumber}`);
  item.text = value;
}

function setCards(slideNumber, eyebrow, title, cards) {
  setText(slideNumber, 2, eyebrow);
  setText(slideNumber, 3, title);
  const ids = [[7, 8, 9], [12, 13, 14], [17, 18, 19], [22, 23, 24], [27, 28, 29], [32, 33, 34]];
  cards.forEach((card, index) => {
    const [heading, body, detail] = ids[index];
    setText(slideNumber, heading, card[0]);
    setText(slideNumber, body, card[1]);
    setText(slideNumber, detail, card[2]);
  });
}

function addSources(slideNumber, lines) {
  const notes = presentation.slides.items[slideNumber - 1].speakerNotes;
  const marker = '[Sources]';
  const current = notes.textFrame.text ?? '';
  const clean = current.includes(marker) ? current.split(marker)[0].trimEnd() : current.trimEnd();
  notes.textFrame.setText([clean, marker, ...lines].filter(Boolean).join('\n'));
  notes.setVisible(true);
}

// Cover
setText(1, 5, 'GOAI 世界人工智能开源大赛 · Agent Infra');
setText(1, 6, 'OJGuard | 在线测评事故响应与可信重评');
setText(1, 18, '单人团队 · 可运行开源作品');
setText(1, 19, '多 Agent 协同调查、受控处置与可验证关闭');

// Project overview
setCards(2, 'P0 · 项目概览', '从异常信号到可信重评的 Agent Infra', [
  ['应用场景', '在线测评批量误判事故', '招聘考试、教育与竞赛 OJ'],
  ['核心目标', '定位根因并冻结影响范围', '只重评真正受影响的提交'],
  ['方案设计', '状态机驱动多 Agent 协作', '任务、证据和权限相互约束'],
  ['能力分工', '1 个 Manager + 6 个 Worker', '独立调查、规划、执行与核验'],
  ['工具底座', '9 Skills / 12 MCP 工具', '确定性事实与动作全部留痕'],
  ['落地基础', '前后端、Runner 与审计台账', '63 项测试和三类场景证据'],
]);

// Scene and value divider
setText(3, 2, '第一章');
setText(3, 3, '场景与价值');

// Quantified stakes
setText(4, 3, '第一章 · 事故代价');
setText(4, 4, '一次环境回归会污染成绩与晋级结果');
setText(4, 5, '固定场景数据中错误率从 8.3% 升至 41.4%，影响 703 名候选人与 742 次提交；处理结果必须能够被复核和追责。');
setText(4, 7, '固定种子 20260802 · Java Runner 真实 OK / TLE 对照');

// Business value
setCards(5, '第一章 · 业务价值', '事故响应需要同时保护公平、效率与信任', [
  ['招聘考试', '批量误判可能改变录用排序', '需要精确范围与晋级重算'],
  ['在线教育', '错误成绩影响学习反馈', '需要快速纠错与解释证据'],
  ['竞赛 OJ', '环境波动可能改变排名', '需要统一规则和可信重评'],
  ['运营效率', '缩短定位、审批和重评时间', '减少人工交叉核对成本'],
  ['用户信任', '每个结论均可回溯证据', '投诉处理不依赖口头解释'],
  ['审计合规', '关键动作经过门禁并留痕', '支持事后复盘和责任界定'],
]);

// Generalization
setText(6, 3, '第一章 · 场景泛化');
setText(6, 4, '同一闭环覆盖三类 OJ 事故');
setText(6, 5, '运行时回归、节点退化和 Checker 缺陷共享状态机与证据契约，新增事故类型只需扩展 Playbook 和工具适配器。');
setText(6, 7, '三类固定种子场景覆盖率均为 100%');

// Solution divider
setText(7, 5, '第二章');
setText(7, 6, '方案设计');
setText(7, 8, '对应评分维度');
setText(7, 9, '多 Agent 协同与自主闭环能力');
setText(7, 11, '25%');

// Architecture
setText(8, 2, '第二章 · 总体架构');
setText(8, 3, 'Agent 负责决策，确定性工具负责事实与执行');
setText(8, 38, '信号进入 IncidentContext；Manager 选择合法 RouteOption；Worker 调用 Skill/MCP；状态机校验审批、批次和验证结果。');

// Agent roles
setText(9, 2, '第二章 · Agent 分工');
setText(9, 3, '1 个 Manager 编排 6 个专职 Worker');
setText(9, 38, 'Signal 聚合信号，Root Cause 设计实验，Impact 冻结范围，Planner 生成计划，Executor 受控执行，Verifier 独立核验。');

// Task decomposition
setCards(10, '第二章 · 任务拆解', '主任务被拆为六个可验收阶段', [
  ['信号归一', '聚合告警、日志和投诉', 'Signal Worker 输出统一快照'],
  ['根因调查', '建立竞争假设与实验候选', 'Root Cause 输出证据结论'],
  ['影响定界', '计算候选人和提交集合', 'Impact 输出冻结范围哈希'],
  ['处置规划', '生成控制、灰度和全量计划', 'Planner 输出版本化方案'],
  ['受控执行', '仅运行已获批批次', 'Executor 使用幂等键写入结果'],
  ['独立核验', '重算覆盖、重复和边界', 'Verifier 决定能否关闭事故'],
]);

// Context transfer
setCards(11, '第二章 · 上下文传递', '结构化 IncidentContext 代替隐式聊天记忆', [
  ['状态快照', '保存事故阶段与当前约束', '每次路由读取同一事实源'],
  ['历史事件', 'AgentRun/Event 顺序记录', '支持恢复、增量查询和 SSE'],
  ['证据引用', '假设、实验、范围和批次有 ID', 'Worker 输出必须携带 refs'],
  ['结构化输出', 'Agent 结果成为下一步输入', 'Schema 校验字段和状态'],
  ['工具回写', 'MCP 结果写入事故台账', '避免只存在模型对话中'],
  ['交接校验', '状态机验证预期结果', '不完整上下文不会推进流程'],
]);

// Routing and state
setCards(12, '第二章 · 协同执行', '动态路由受状态机与证据共同约束', [
  ['合法选项', '当前状态生成 RouteOption', '拒绝跨阶段或越权动作'],
  ['候选实验', '同一根因可有多个实验', 'Manager 选择信息量更高者'],
  ['证据不足', 'INCONCLUSIVE 保持调查态', '允许从剩余候选中补选'],
  ['确定性校验', '工具结果决定状态是否推进', '模型不能替代数值判断'],
  ['状态转移', '每一步声明 expected state', '异常结果进入明确分支'],
  ['人工门禁', '高风险路由等待审批', '批准对象与计划版本绑定'],
]);

// Result validation
setCards(13, '第二章 · 结果验证', '关闭事故前必须通过六类独立检查', [
  ['实验充分性', '根因实验必须 PASSED', 'INCONCLUSIVE 不视为成功'],
  ['范围一致性', '重评集合匹配冻结哈希', '禁止跨范围成绩写入'],
  ['批次完整性', '控制、灰度、全量均完成', '失败或暂停批次不计覆盖'],
  ['幂等一致性', '重复重评数量必须为 0', '批次键阻止重复执行'],
  ['结果重算', '重新计算成绩与晋级变化', '不复用执行 Agent 的结论'],
  ['关闭条件', '覆盖 100%，漏评与越界为 0', '全部断言通过才 RESOLVED'],
]);

// Exception branches
setCards(14, '第二章 · 异常分支', '失败不会被隐藏，而是进入可恢复状态', [
  ['证据不足', '实验返回 INCONCLUSIVE', '保持调查态并补选实验'],
  ['工具失败', '超时、Schema 或依赖异常', '记录错误并转人工处理'],
  ['状态冲突', 'Worker 输出不符合预期', '拒绝写入并保留上下文'],
  ['灰度失败', '事故立即进入 PAUSED', '回滚失败批次并阻断全量'],
  ['审批拒绝', '计划保持不可执行', '修改计划后重新发起审批'],
  ['恢复失败', 'canary_retry 未通过', '继续暂停或升级人工处置'],
]);

// Security boundaries
setCards(15, '第二章 · 安全边界', '风险控制贯穿建议、审批、执行与关闭', [
  ['最小权限', 'Worker 只能调用授权工具', '分析角色没有批量执行权'],
  ['双重审批', '技术与业务门禁分别留痕', '高风险动作必须显式批准'],
  ['范围冻结', '计划绑定影响集合哈希', '后续批次禁止扩大范围'],
  ['幂等保护', '事故、批次和提交都有键', '重试不会产生重复写入'],
  ['暂停回滚', '灰度异常立即阻断全量', '失败批次保存替代关系'],
  ['秘密隔离', '密钥仅从本地环境读取', '日志、证据与提交包均脱敏'],
]);

// Skill divider
setText(16, 2, '第三章');
setText(16, 3, 'Skill 与工具集成');
setText(16, 12, '对应评分维度');
setText(16, 13, 'Skill 工程体系与生态复用');
setText(16, 15, '25%');

// Skills
setText(17, 2, '第三章 · Skill 工程');
setText(17, 3, '9 个 Skill 覆盖调查、处置与核验');
setText(17, 8, '25%');
setText(17, 38, '每个 Skill 定义输入输出、调用条件、依赖工具、失败处理、安全边界、幂等键、验收标准、复用价值和协作关系。');

// MCP tools
setCards(18, '第三章 · MCP 工具集', '12 个工具提供确定性事实与受控动作', [
  ['信号与部署', '读取异常分布和变更记录', '为事故分诊提供事实'],
  ['假设与重放', '生成候选并执行对照实验', '返回 PASSED / INCONCLUSIVE'],
  ['题包审计', '检查 Checker、数据与配置', '定位题目侧系统性缺陷'],
  ['影响定界', '计算候选人和提交集合', '冻结范围并生成 SHA-256'],
  ['计划与审批', '创建版本化重评计划', '审批结果绑定计划 revision'],
  ['执行与验证', '运行批次并生成报告', '幂等执行与独立一致性核验'],
]);

// Tool integration and RAG
setCards(19, '第三章 · 集成契约', 'Skill 抽象任务，MCP 连接真实系统', [
  ['结构契约', '工具声明参数与返回 Schema', 'Agent 输出可被稳定校验'],
  ['调用审计', '记录工具、参数和结果摘要', '失败重试保留完整事件链'],
  ['错误处理', '超时、重试和转人工明确', '不会静默吞掉工具异常'],
  ['权限边界', '读操作与写操作分级授权', '批量动作受审批和状态约束'],
  ['上下文回写', '工具结果进入 IncidentContext', '后续 Agent 共享同一事实'],
  ['RAG 扩展', '保留知识检索适配器契约', '可接 Runbook 与历史事故库'],
]);

// Feasibility divider
setText(20, 5, '第四章');
setText(20, 6, '可行性与落地计划');
setText(20, 8, '对应评分维度');
setText(20, 9, '工程落地与安全可审计');
setText(20, 11, '20%');

// Feasibility
setCards(21, '第四章 · 工程可行性', '核心闭环已有可运行实现和验证依据', [
  ['业务前端', 'Vue 3 事故工作台', '总览、详情、审批与重评'],
  ['服务后端', 'FastAPI + 领域状态机', '事故、路由、事件和报告 API'],
  ['数据台账', 'SQLite 可审计存储', '保存状态、审批、批次与事件'],
  ['Agent Infra', 'AgentTeams + Skills + MCP', '角色、任务和工具契约完整'],
  ['执行验证', 'Java Runner + 固定种子', '真实 OK/TLE 与三类场景报告'],
  ['质量保证', '63 tests + Ruff + Vue build', '秘密扫描与提交包审计通过'],
]);

// Landing plan
setCards(22, '第四章 · 落地计划', '从旁路观察逐步进入生产写路径', [
  ['阶段一', '接入告警、日志与提交数据', '建立只读适配器和基线指标'],
  ['阶段二', '旁路生成事故与影响建议', '人工确认结果，不写入成绩'],
  ['阶段三', '启用审批和控制组重评', '验证权限、幂等和回滚能力'],
  ['阶段四', '开放灰度与分批执行', '达到阈值后再进入全量'],
  ['阶段五', '接入监控、工单和 Runbook', '沉淀事故模板和经验规则'],
  ['验收指标', '范围准确、覆盖完整、零越界', '同时评估耗时、成本与可靠性'],
]);

// Open-source plan
setCards(23, '第四章 · 开放 / 开源计划', '以可复用契约降低其他 OJ 的接入成本', [
  ['开源许可', 'Apache-2.0', '允许使用、修改和再分发'],
  ['开放代码', '前后端、Runner 与状态机', '提供本地运行和容器配置'],
  ['开放能力', '9 Skills / 12 MCP 工具', '输入输出和安全边界完整'],
  ['扩展接口', 'OJ Adapter / RAG / Playbook', '新增系统无需改写核心流程'],
  ['复现资产', '三类场景、测试与证据报告', '便于验证迁移后的行为一致性'],
  ['演进方向', '补充队列、配置与资源事故', '持续完善适配器和观测标准'],
]);

for (const [index, slide] of presentation.slides.items.entries()) {
  const page = slide.shapes.items.find((item) => {
    const text = item.toSnapshot?.().text ?? '';
    return item.frame?.top > 650 && /^\d+$/.test(text);
  });
  if (page) page.text = String(index + 1);
}

const sources = {
  1: ['OJGuard README.md'],
  2: ['OJGuard README.md', 'OJGuard OJGuard_项目方案.md'],
  3: ['OJGuard OJGuard_项目方案.md'],
  4: ['OJGuard output/evidence/incidents/runtime-regression-report.json', 'OJGuard output/evidence/java-runtime-comparison.json'],
  5: ['OJGuard OJGuard_项目方案.md'],
  6: ['OJGuard output/evidence/incidents/scenario-summary.json'],
  7: ['OJGuard agentteams/ojguard-team.yaml'],
  8: ['OJGuard backend/app/services/incident_workflow.py', 'OJGuard backend/app/services/agent_routing.py'],
  9: ['OJGuard materials/Agent_Identity_清单.md', 'OJGuard agents/identities/'],
  10: ['OJGuard agentteams/ojguard-team.yaml', 'OJGuard skills/'],
  11: ['OJGuard materials/上下文与可观测性说明.md', 'OJGuard backend/app/services/repository.py'],
  12: ['OJGuard backend/app/services/agent_routing.py', 'OJGuard tests/test_agent_runs.py'],
  13: ['OJGuard backend/app/services/trusted_rejudge.py', 'OJGuard tests/test_agentteams_runtime_control.py'],
  14: ['OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json'],
  15: ['OJGuard materials/MCP_工具契约与迁移说明.md', 'OJGuard scripts/run_agentteams_demo.ps1'],
  16: ['OJGuard skills/', 'OJGuard mcp_server/'],
  17: ['OJGuard skills/', 'OJGuard materials/MCP_工具契约与迁移说明.md'],
  18: ['OJGuard mcp_server/tools.py', 'OJGuard materials/MCP_工具契约与迁移说明.md'],
  19: ['OJGuard materials/上下文与可观测性说明.md'],
  20: ['OJGuard README.md'],
  21: ['OJGuard README.md', 'OJGuard materials/提交前检查清单.md'],
  22: ['OJGuard OJGuard_项目方案.md'],
  23: ['OJGuard README.md', 'OJGuard LICENSE'],
};
for (const [slideNumber, lines] of Object.entries(sources)) addSources(Number(slideNumber), lines);

await fs.mkdir('./final-render', { recursive: true });
await fs.mkdir('./final-layout', { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, '0')}`;
  const png = await presentation.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(`./final-render/${stem}.png`, new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(`./final-layout/${stem}.layout.json`, await layout.text());
}

const inspect = await presentation.inspect({
  kind: 'slide,textbox,shape,image,notes,layout',
  maxChars: 60000,
});
await fs.writeFile('./guided-final.inspect.ndjson', inspect.ndjson, 'utf8');

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
