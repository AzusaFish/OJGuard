import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const input = './template-starter.pptx';
const output = '../../output/submission/OJGuard_项目介绍.pptx';
const renderDir = './final-render';
const layoutDir = './final-layout';

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));

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
  const ids = [
    [7, 8, 9],
    [12, 13, 14],
    [17, 18, 19],
    [22, 23, 24],
    [27, 28, 29],
    [32, 33, 34],
  ];
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

// 1 — cover
setText(1, 5, 'GOAI 世界人工智能开源大赛 · Agent Infra');
setText(1, 6, 'OJGuard | 在线测评事故响应与可信重评');
setText(1, 18, '单人团队 · 可运行开源作品');
setText(1, 19, '让多 Agent 真正驱动事故闭环，而不是事后复述结果');

// 2 — executive thesis
setCards(2, 'P0 · 30 秒结论', 'OJGuard 的核心不是聊天，而是可信处置', [
  ['业务问题', '批量误判会污染成绩与晋级', '事故影响必须被精确定界'],
  ['协同方式', '1 个 Manager + 6 个 Worker', '每个角色拥有独立边界'],
  ['决策创新', '多个合法实验可动态补选', '证据不足不会强行推进'],
  ['失败恢复', 'PAUSED → 新计划 → 重审批', '恢复灰度后才能继续全量'],
  ['工程底座', '9 Skills / 12 MCP 工具', 'AgentRun/Event 全链路留痕'],
  ['验证结果', '63 项测试与两类证据', '三类事故均可重复复现'],
]);

// 3 — stakes
setText(3, 3, '第一章 · 场景价值');
setText(3, 4, '一次运行时回归，可能改写数百人的结果');
setText(3, 5, '主演示中错误率从 8.3% 升至 41.4%，影响 703 名候选人与 742 次提交；事故处理必须可复核、可暂停、可恢复。');
setText(3, 7, '固定种子 20260802 · Java Runner 真实 OK / TLE 对照');

// 4 — gaps
setCards(4, '第一章 · 为什么现有方法不够', '普通告警平台与单轮问答无法完成可信重评', [
  ['信号割裂', '告警、日志、投诉彼此分散', '缺少统一 IncidentContext'],
  ['根因武断', '一次分析直接给出唯一答案', '没有竞争假设与补充实验'],
  ['事后复核', 'Agent 只解释已完成结果', '没有驱动任务与状态推进'],
  ['盲目重试', '灰度失败后原计划重跑', '没有回滚、版本与重审批'],
  ['证据缺口', '无法还原谁在何时做了什么', '缺少顺序事件与决策依据'],
  ['执行越权', '建议与高风险动作混在一起', '缺少人工门禁和最小权限'],
]);

// 5 — solution divider
setText(5, 2, '第二章');
setText(5, 3, '证据驱动的事故闭环');

// 6 — architecture
setText(6, 2, '第二章 · 系统总览');
setText(6, 3, 'Agent 负责决策，确定性工具负责事实与执行');
setText(6, 38, '信号进入统一 IncidentContext；Manager 只从合法 RouteOption 中选择下一步，状态机校验每次 Worker、MCP、审批和重评结果。');

// 7 — state machine
setCards(7, '第二章 · 共同事实源', '事故状态机把协作从对话变成工程流程', [
  ['发现与分诊', 'DETECTED → TRIAGING', '聚合告警并建立事故上下文'],
  ['调查与定界', 'INVESTIGATING → IMPACT', '实验不足时停留调查态'],
  ['计划与审批', 'PLANNING → APPROVAL', '冻结范围并建立执行计划'],
  ['受控执行', 'EXECUTING / PAUSED', '灰度失败立即暂停与回滚'],
  ['独立核验', 'VERIFYING', '检查覆盖、重复、遗漏和越界'],
  ['可信关闭', 'RESOLVED', '只有全部断言通过才能关闭'],
]);

// 8 — multi-agent divider
setText(8, 5, '第三章');
setText(8, 6, '多 Agent 协同不是堆角色，而是分离决策权');
setText(8, 8, '对应评分维度');
setText(8, 9, '多 Agent 协同与自主闭环能力');
setText(8, 11, '25%');

// 9 — why multiple agents
setCards(9, '第三章 · 为什么不能只有一个 Agent', '六类责任需要彼此制衡', [
  ['信息整合', 'Signal Worker 只处理信号', '不直接决定根因或重评'],
  ['实验设计', 'Root Cause 提出竞争实验', '不拥有批量执行权限'],
  ['范围冻结', 'Impact Worker 计算影响集', '范围哈希进入后续计划'],
  ['处置规划', 'Planner 生成版本化计划', '失败后创建 revision 2'],
  ['受控执行', 'Executor 只执行获批批次', '幂等键阻止重复重评'],
  ['独立验证', 'Verifier 不复用执行结论', '覆盖与边界必须重算'],
]);

// 10 — roles and decision rights
setText(10, 2, '第三章 · Agent Identity');
setText(10, 3, 'Manager 编排 6 个专职 Worker');
setText(10, 38, 'Manager 决定“下一步调用谁”；Worker 只在能力边界内调用工具；确定性状态机拥有最终推进权，高风险动作由人工审批。');

// 11 — dynamic routes
setCards(11, '第三章 · 动态路由', 'RouteOption 让下一步由现场证据决定', [
  ['状态约束', '当前状态生成合法动作集合', '非法跨阶段路由会被拒绝'],
  ['多候选实验', '每类事故生成 3 个候选', 'Manager 选择最有信息量者'],
  ['Worker 绑定', '动作绑定专职 Agent', '避免角色越权和职责漂移'],
  ['证据引用', '每个决定携带 evidence refs', '结果可回溯至假设与批次'],
  ['预期结果', '路由声明 expected result', '便于判断实验是否充分'],
  ['失败动作', '统一 failure_action', '异常转人工或进入恢复链'],
]);

// 12 — inconclusive reroute
setCards(12, '第三章 · 证据不足时怎么办', 'INCONCLUSIVE 不等于 PASSED', [
  ['候选一', 'cross-image replay', '比较基线与观测镜像'],
  ['候选二', 'cross-node replay', '比较健康与异常节点'],
  ['候选三', 'control replay', '验证健康控制组稳定性'],
  ['首轮不足', '第一实验返回 INCONCLUSIVE', '事故保持 INVESTIGATING'],
  ['Manager 改选', '从剩余合法候选中补选', '第二实验确认节点退化'],
  ['状态推进', '只有充分证据才进入影响分析', '模型不能绕过确定性校验'],
]);

// 13 — recovery
setCards(13, '第三章 · 失败恢复', '灰度失败触发新计划，而不是原地重试', [
  ['发现异常', 'canary 出现结果不一致', '批次记录失败原因'],
  ['立即暂停', '事故进入 PAUSED', '阻止后续全量执行'],
  ['回滚失败批次', '旧 canary 标记 ROLLED_BACK', '保存替代批次关系'],
  ['计划升级', '创建 remediation revision 2', '显式 supersedes revision 1'],
  ['审批失效', '旧技术审批自动 REVOKED', '新计划必须重新批准'],
  ['恢复执行', 'canary_retry → bulk → verify', '最终覆盖率重新计算'],
]);

// 14 — observability
setCards(14, '第三章 · 可观测协同', 'AgentRun / Event 还原整条决策链', [
  ['运行快照', 'AgentRun 保存状态与模型计数', '支持按事故查询最新运行'],
  ['顺序事件', 'sequence 单调递增', '事件 ID 幂等防止重复写入'],
  ['路由证据', '记录 action / worker / reason', '同时保存候选与证据引用'],
  ['执行证据', 'Worker、工具和状态分别留痕', '失败、暂停与恢复均可查询'],
  ['人工门禁', '审批事件独立保存', '技术、业务与关闭职责可审计'],
  ['实时消费', '快照、增量 API 与 SSE', '便于接入监控和评测平台'],
]);

// 15 — skill divider
setText(15, 2, '第四章');
setText(15, 3, 'Skill 与 MCP：把经验沉淀成基础设施');
setText(15, 12, '对应评分维度');
setText(15, 13, 'Skill 工程体系与生态复用');
setText(15, 15, '25%');

// 16 — skills
setText(16, 2, '第四章 · 任务能力抽象');
setText(16, 3, '9 个 Skill 覆盖调查、处置与核验');
setText(16, 8, '25%');
setText(16, 38, '每个 Skill 定义输入输出、依赖、失败处理、安全边界、幂等键、验收标准和协作关系。');

// 17 — MCP contracts
setCards(17, '第四章 · 工具接入契约', '12 个 MCP 工具提供确定性事实与受控动作', [
  ['信号与部署', 'signal + deployment tools', '读取异常分布与变更记录'],
  ['假设与重放', 'hypotheses / candidates / replay', '支持多实验和明确结果状态'],
  ['题包审计', 'problem package audit', '检查 Checker、数据与配置'],
  ['影响定界', 'candidate / submission scope', '冻结集合并生成 SHA-256'],
  ['计划与审批', 'plan + approval tools', '计划版本与审批对象绑定'],
  ['执行与验证', 'batch / verify / report', '幂等重评与独立一致性检查'],
]);

// 18 — context and RAG
setCards(18, '第四章 · 上下文增强', '当前能力可运行，RAG 作为可替换扩展', [
  ['共享上下文', 'IncidentContext 贯穿全流程', '保存状态、范围、计划与证据'],
  ['历史记忆', 'AgentRun/Event 提供事件历史', '支持按序恢复与增量消费'],
  ['Skill 封装', '检索与工具结果写回上下文', 'Agent 不依赖隐式聊天记忆'],
  ['确定性事实', 'SQL、Runner、MCP 作为事实源', '模型不替代数值与状态判断'],
  ['RAG 边界', '保留知识检索适配器契约', '当前不宣称已实现知识库 RAG'],
  ['迁移路径', '可接 Runbook 与历史事故库', '无需改写 Agent/Skill 协作链'],
]);

// 19 — engineering divider
setText(19, 5, '第五章');
setText(19, 6, '工程落地与可验证证据');
setText(19, 8, '对应评分维度');
setText(19, 9, '工程落地与安全可审计');
setText(19, 11, '20%');

// 20 — implementation
setCards(20, '第五章 · 可运行实现', '从浏览器工作台到受控重评执行器', [
  ['业务前端', 'Vue 3 事故工作台', '总览、详情、审批与重评'],
  ['服务后端', 'FastAPI + 领域状态机', '事故、路由、事件和报告 API'],
  ['数据台账', 'SQLite 可审计存储', '状态、审批、批次与 Agent 事件'],
  ['Agent Infra', 'AgentTeams + 9 Skills', '12 个 MCP 工具受状态约束'],
  ['执行证据', 'Java Runner + 固定种子', '真实 OK/TLE 与三类事故报告'],
  ['质量门禁', '63 tests + Ruff + build', '秘密扫描与提交包审计通过'],
]);

// 21 — evidence classes
setText(21, 2, '第五章 · 证据分级');
setText(21, 3, '真实协作与异常恢复分别证明不同能力');
setText(21, 38, '真实协作：6 个 Worker、20 条模型响应；异常恢复：3 候选补选、PAUSED、revision 2、重审批与恢复灰度。');

// 22 — generalization
setText(22, 3, '第六章 · 泛化与差异化');
setText(22, 4, '同一闭环覆盖三类 OJ 事故');
setText(22, 5, '运行时回归、节点退化和 Checker 缺陷共享状态机与证据契约；核心差异是受控执行和可验证结果。');
setText(22, 7, '三类场景覆盖率 100% · 可迁移多种 OJ');

// 23 — close
setText(23, 2, '第七章 · Demo 路线');
setText(23, 3, '让评委在一次演示中看到完整闭环');
setText(23, 38, '创建事故 → 动态选择实验 → 冻结影响范围 → 人工审批 → 控制/灰度/全量重评 → 关闭核验；同时展示灰度失败后的暂停与恢复证据。');

// Update inherited page markers without changing layout geometry.
for (const [index, slide] of presentation.slides.items.entries()) {
  const page = slide.shapes.items.find((item) => {
    const text = item.toSnapshot?.().text ?? '';
    return item.frame?.top > 650 && /^\d+$/.test(text);
  });
  if (page) page.text = String(index + 1);
}

const notes = {
  1: ['OJGuard README.md'],
  2: ['OJGuard README.md', 'OJGuard OJGuard_项目方案.md'],
  3: ['OJGuard output/evidence/incidents/runtime-regression-report.json', 'OJGuard output/evidence/java-runtime-comparison.json'],
  4: ['OJGuard materials/Agent_Identity_清单.md', 'OJGuard materials/上下文与可观测性说明.md'],
  5: ['OJGuard OJGuard_项目方案.md'],
  6: ['OJGuard backend/app/services/incident_workflow.py', 'OJGuard backend/app/services/agent_routing.py'],
  7: ['OJGuard backend/app/domain/incidents.py', 'OJGuard tests/test_agentteams_runtime_control.py'],
  8: ['OJGuard agentteams/ojguard-team.yaml'],
  9: ['OJGuard materials/Agent_Identity_清单.md'],
  10: ['OJGuard agentteams/ojguard-team.yaml', 'OJGuard agents/identities/'],
  11: ['OJGuard backend/app/services/agent_routing.py', 'OJGuard tests/test_agent_runs.py'],
  12: ['OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json'],
  13: ['OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json', 'OJGuard tests/test_agentteams_runtime_control.py'],
  14: ['OJGuard backend/app/api/agent_runs.py', 'OJGuard backend/app/services/repository.py'],
  15: ['OJGuard skills/', 'OJGuard mcp_server/'],
  16: ['OJGuard skills/', 'OJGuard materials/MCP_工具契约与迁移说明.md'],
  17: ['OJGuard mcp_server/tools.py', 'OJGuard materials/MCP_工具契约与迁移说明.md'],
  18: ['OJGuard materials/上下文与可观测性说明.md'],
  19: ['OJGuard README.md'],
  20: ['OJGuard README.md', 'OJGuard materials/提交前检查清单.md'],
  21: ['OJGuard output/evidence/agentteams/agentteams-demo-result.json', 'OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json'],
  22: ['OJGuard output/evidence/incidents/scenario-summary.json'],
  23: ['OJGuard README.md', 'OJGuard materials/evidence/AgentTeams_真实运行证据.md'],
};

for (const [slideNumber, lines] of Object.entries(notes)) addSources(Number(slideNumber), lines);

await fs.mkdir(renderDir, { recursive: true });
await fs.mkdir(layoutDir, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, '0')}`;
  const png = await presentation.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(`${renderDir}/${stem}.png`, new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(`${layoutDir}/${stem}.layout.json`, await layout.text());
}

const montage = await presentation.export({ format: 'png', montage: true, scale: 1 });
await fs.writeFile('./final-montage.png', new Uint8Array(await montage.arrayBuffer()));

const inspect = await presentation.inspect({
  kind: 'slide,textbox,shape,image,notes,layout',
  maxChars: 60000,
});
await fs.writeFile('./expanded-final.inspect.ndjson', inspect.ndjson, 'utf8');

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
