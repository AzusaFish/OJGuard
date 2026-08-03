import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const input = '../../output/submission/OJGuard_项目介绍.pptx';
const output = '../../output/submission/OJGuard_项目介绍.compact.pptx';
const renderDir = './compact-final-render';
const layoutDir = './compact-final-layout';

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));

function slide(sourceSlideNumber) {
  return presentation.slides.items[sourceSlideNumber - 1];
}

function shape(sourceSlideNumber, id) {
  return slide(sourceSlideNumber).shapes.getById(String(id));
}

function setText(sourceSlideNumber, id, value, fontSize) {
  const item = shape(sourceSlideNumber, id);
  if (!item) throw new Error(`Missing shape ${id} on source slide ${sourceSlideNumber}`);
  item.text = value;
  if (fontSize) item.text.style = { ...item.text.style, fontSize };
}

function setCards(sourceSlideNumber, eyebrow, title, cards) {
  setText(sourceSlideNumber, 2, eyebrow);
  setText(sourceSlideNumber, 3, title);
  const ids = [
    [7, 8, 9],
    [12, 13, 14],
    [17, 18, 19],
    [22, 23, 24],
    [27, 28, 29],
    [32, 33, 34],
  ];
  cards.forEach((card, index) => {
    const [headingId, bodyId, detailId] = ids[index];
    setText(sourceSlideNumber, headingId, card[0]);
    setText(sourceSlideNumber, bodyId, card[1]);
    setText(sourceSlideNumber, detailId, card[2]);
  });
}

function setSources(sourceSlideNumber, lines) {
  const notes = slide(sourceSlideNumber).speakerNotes;
  const marker = '[Sources]';
  const current = notes.textFrame.text ?? '';
  const clean = current.includes(marker) ? current.split(marker)[0].trimEnd() : current.trimEnd();
  notes.textFrame.setText([clean, marker, ...lines].filter(Boolean).join('\n'));
  notes.setVisible(true);
}

function replaceLegacyStateStrip(sourceSlideNumber) {
  const currentSlide = slide(sourceSlideNumber);
  currentSlide.shapes.add({
    geometry: 'rect',
    position: { left: 637.5, top: 521, width: 576, height: 43 },
    fill: '#FFFFFF',
    line: { style: 'solid', fill: '#FFFFFF', width: 0 },
  });
  const stateText = currentSlide.shapes.add({
    geometry: 'textbox',
    position: { left: 649, top: 523, width: 552, height: 38 },
    fill: 'none',
    line: { style: 'solid', fill: 'none', width: 0 },
  });
  stateText.text = 'TRIAGING → INVESTIGATING → IMPACT_ASSESSING → REMEDIATION_PLANNING\nAPPROVAL_PENDING → EXECUTING → REJUDGING → VERIFYING → RESOLVED';
  stateText.text.style = {
    fontSize: 8.5,
    color: '#17203F',
    bold: true,
    alignment: 'center',
  };
}

// 1 — cover
setText(1, 5, 'GOAI 世界人工智能开源大赛 · Agent Infra');
setText(1, 6, 'OJGuard |\n在线测评事故响应与可信重评');
setText(1, 19, 'AgentTeams 驱动调查、处置与验证；确定性工具守住事实和执行边界');
setText(1, 18, '单人团队 · 可运行开源作品');

// 2 — compact executive summary
setCards(2, 'P0 · 30 秒项目概览', '核心不是“会分析”，而是让 AgentTeams 驱动可信处置', [
  ['高风险场景', '批量误判影响成绩与晋级', '必须精确定界并可回溯'],
  ['协同控制面', '1 Manager + 6 Worker', '职责、上下文和权限分离'],
  ['动态决策', '多候选实验按证据补选', 'INCONCLUSIVE 不强行推进'],
  ['受控执行', '技术 / 业务 / 关闭三道门禁', '灰度失败立即暂停与重规划'],
  ['能力底座', '9 Skills × 12 MCP 工具', '任务抽象与系统接入分层'],
  ['工程证据', '66 tests + 三类事故场景', '真实协作与确定性恢复分级'],
]);

// 4 — scenario and value
setText(4, 3, '场景与价值 · 运行时回归');
setText(4, 4, '一次环境回归，可能改写数百人的成绩与晋级');
setText(4, 5, '错误率 8.3% → 41.4%，影响 703 名候选人、742 条提交和 72 个晋级结果；OJGuard 将异常转为可复核根因、冻结范围、受控批次和关闭证据。', 15);
setText(4, 7, '固定种子 20260802 · Java Runner：正常 3/3 OK，退化 3/3 TLE', 13);
replaceLegacyStateStrip(4);

// 6 — generalization
setText(6, 3, '场景泛化 · 三类事故');
setText(6, 4, '同一 AgentTeams 闭环覆盖三类 OJ 故障');
setText(6, 5, '运行时回归 703 人 / 742 条 / 72 个晋级变化；节点退化 118 人 / 119 条 / 14 个变化；Checker 缺陷 71 人 / 73 条 / 8 个变化。三类场景均完成 100% 覆盖核验。', 14);
setText(6, 7, '复用状态机、证据契约和重评引擎；新增场景只扩展 Playbook 与 Adapter', 13);
replaceLegacyStateStrip(6);

// 8 — architecture and exact state machine
setText(8, 2, '方案设计 · 总体架构');
setText(8, 3, 'AgentTeams 决策，状态机约束执行');
setText(8, 38, 'Incident Manager 读取 IncidentContext 并选择 RouteOption；Worker 调用 Skill / MCP。主链：TRIAGING → INVESTIGATING → IMPACT_ASSESSING → REMEDIATION_PLANNING → APPROVAL_PENDING → EXECUTING → REJUDGING → VERIFYING → RESOLVED；异常进入 PAUSED 或 HUMAN_REVIEW_REQUIRED。', 13);

// 9 — agent division, task decomposition and context transfer
setText(9, 2, '方案设计 · Agent 分工与协作');
setText(9, 3, '1 Manager + 6 Worker：职责制衡');
setText(9, 38, 'Manager 决定“下一步调用谁”；Signal、Root Cause、Impact、Planner、Executor、Verifier 分别交付可校验产物。IncidentContext、Evidence ID、范围哈希和 AgentRun/Event 在角色间传递，避免一个 Agent 同时提出结论、执行写操作并自我验收。', 14);

// 12 — dynamic routing, exception branches and gates
setCards(12, '方案设计 · 动态协同与异常分支', '下一步由 AgentTeams 决定，失败由确定性策略接管', [
  ['合法路由', '状态生成 RouteOption 集合', 'Manager 只能在合法动作中选择'],
  ['竞争假设', '多条可证伪根因并行存在', '选择信息增益更高的实验'],
  ['证据不足', 'INCONCLUSIVE 保持调查态', '从剩余候选补选而非硬判'],
  ['灰度失败', 'PAUSED 并阻断全量批次', '保存失败证据并执行回滚'],
  ['恢复计划', 'revision 2 supersedes rev1', '撤销旧审批，重新灰度验证'],
  ['人工门禁', '技术 / 业务 / 关闭审批', 'Agent 无批准接口，不能自批'],
]);

// 18 — Skills and MCP in one page
setCards(18, 'Skill 与工具集成 · 9 Skills × 12 MCP', 'Skill 定义可复用任务，MCP 连接确定性事实与受控动作', [
  ['信号分诊', 'normalize / correlate Skills', '信号、提交与部署读取工具'],
  ['根因实验', 'hypothesis / replay Skills', '候选假设与对照重放工具'],
  ['题包审计', 'package-audit Skill', 'Checker、数据与配置审计'],
  ['影响定界', 'impact-scope Skill', '候选人 / 提交集合 + SHA-256'],
  ['计划审批', 'remediation-plan Skill', '版本计划与审批状态查询'],
  ['执行核验', 'execute / verify / report Skills', '幂等批次、独立核验与报告'],
]);

// 19 — context, observability, security and RAG boundary
setCards(19, '上下文、可观测性与安全边界', '每次决策、工具调用和状态推进都有可查询依据', [
  ['共享上下文', 'IncidentContext 保存业务状态', '范围、计划、审批和 Evidence ID'],
  ['协同轨迹', 'AgentRun / Event 顺序留痕', '路由、Worker、工具和理由可查'],
  ['实时观测', '快照 API + 增量事件 + SSE', '支持恢复、审计和前端消费'],
  ['异常处理', '超时、重试、冲突和转人工', '失败不会被静默吞掉'],
  ['安全控制', '读写分级 + 幂等 + 范围哈希', '批量动作受审批和状态约束'],
  ['RAG 扩展', '保留知识检索适配器契约', '可接 Runbook，不虚构已实现能力'],
]);

// 21 — feasibility, landing and open-source plan
setCards(21, '可行性、落地与开放计划', '已有可运行闭环；66 项测试、Ruff、Vue build 与提交包审计通过', [
  ['前端工作台', 'Vue 3：总览、详情与审批', '只展示用户需要的业务入口'],
  ['服务与台账', 'FastAPI + SQLite 状态机', '事故、路由、批次与事件 API'],
  ['Agent Infra', 'AgentTeams + Skills + MCP', '核心协同链已真实运行验收'],
  ['旁路接入', '先读告警、日志和提交数据', '只生成建议，不写正式成绩'],
  ['受控写入', '控制组 → 灰度 → 分批全量', '阈值、回滚和三道人工门禁'],
  ['开放复用', 'Apache-2.0 + OJ Adapter', '开放代码、契约、场景与证据'],
]);

// 22 — live AgentTeams acceptance
setCards(22, '工程证据 · 真实 AgentTeams 验收', 'DeepSeek 与 6 个 Worker 从 TRIAGING 动态推进到 RESOLVED', [
  ['非事后复核', 'live_dynamic_routing', 'posthoc_review = false'],
  ['完整团队', '1 Leader + 6 Worker', '六个专业角色均留下独立响应'],
  ['动态决策', '11 次 ROUTE_DECISION', '每轮重读状态并核对预期结果'],
  ['有界调用', '20 条模型响应', '11 路由 + 8 Worker + 1 报告'],
  ['人工门禁', '技术 / 业务 / 关闭共 3 次', '单人以不同角色上下文验收'],
  ['独立核验', '覆盖 100%，重复 / 遗漏 / 越界 = 0', '最终状态 RESOLVED'],
]);

// 23 — evidence index
setCards(23, 'Evidence Index · 主张—指标—文件—复现命令', '关键结论均可从仓库文件定位，并用对应脚本重复验证', [
  ['AgentTeams 核心', '11 路由 · 8 Worker · 20 响应', 'agentteams-demo-result.json · export_agentteams_evidence.ps1'],
  ['异常恢复', 'INCONCLUSIVE 补选 · PAUSED → rev2', 'deterministic-recovery-evidence.json · generate_orchestration_recovery_evidence.py'],
  ['三类场景', '703/742 · 118/119 · 71/73；均 100%', 'scenario-summary.json · generate_incident_evidence.py'],
  ['Java 对照', '正常 3/3 OK · 退化 3/3 TLE', 'java-runtime-comparison.json · run_java_regression_experiment.py'],
  ['质量门禁', '66 tests · Ruff · Vue build', 'python -m unittest discover -s tests -v'],
  ['提交包', '必需文件 / UTF-8 名称 / 链接 / 秘密扫描', 'build_submission_package.ps1 · verify_submission_package.py'],
]);

for (const id of [9, 14, 19, 24, 29, 34]) {
  shape(23, id).text.style = { ...shape(23, id).text.style, fontSize: 11 };
}
for (const id of [8, 13, 18, 23, 28, 33]) {
  shape(23, id).text.style = { ...shape(23, id).text.style, fontSize: 13 };
}

const notes = {
  1: ['OJGuard README.md'],
  2: ['OJGuard README.md', 'OJGuard OJGuard_项目方案.md'],
  4: ['OJGuard output/evidence/incidents/runtime-regression-report.json', 'OJGuard output/evidence/java-runtime-comparison.json'],
  6: ['OJGuard output/evidence/incidents/scenario-summary.json'],
  8: ['OJGuard backend/app/domain/incidents.py', 'OJGuard backend/app/services/agent_routing.py', 'OJGuard backend/app/services/incident_workflow.py'],
  9: ['OJGuard agentteams/ojguard-team.yaml', 'OJGuard materials/Agent_Identity_清单.md'],
  12: ['OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json', 'OJGuard tests/test_agentteams_runtime_control.py'],
  18: ['OJGuard skills/', 'OJGuard mcp_server/tools.py', 'OJGuard materials/MCP_工具契约与迁移说明.md'],
  19: ['OJGuard materials/上下文与可观测性说明.md', 'OJGuard backend/app/api/agent_runs.py'],
  21: ['OJGuard README.md', 'OJGuard materials/提交前检查清单.md', 'OJGuard LICENSE'],
  22: ['OJGuard output/evidence/agentteams/agentteams-demo-result.json', 'OJGuard materials/evidence/AgentTeams_真实运行证据.md'],
  23: ['OJGuard README.md', 'OJGuard output/evidence/agentteams/', 'OJGuard output/evidence/incidents/', 'OJGuard scripts/'],
};

for (const [sourceSlideNumber, lines] of Object.entries(notes)) {
  setSources(Number(sourceSlideNumber), lines);
}

// Keep only the 12 high-information slides; remove chapter dividers and pages
// whose content has been consolidated above. Remove from the end to preserve indexes.
const keep = new Set([1, 2, 4, 6, 8, 9, 12, 18, 19, 21, 22, 23]);
for (let index = presentation.slides.items.length - 1; index >= 0; index -= 1) {
  if (!keep.has(index + 1)) presentation.slides.remove(index);
}

// Refresh inherited page markers after compaction.
for (const [index, currentSlide] of presentation.slides.items.entries()) {
  const page = currentSlide.shapes.items.find((item) => {
    const text = item.toSnapshot?.().text ?? '';
    return item.frame?.top > 650 && /^\d+$/.test(text);
  });
  if (page) page.text = String(index + 1);
}

await fs.mkdir(renderDir, { recursive: true });
await fs.mkdir(layoutDir, { recursive: true });
for (const [index, currentSlide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, '0')}`;
  const png = await presentation.export({ slide: currentSlide, format: 'png', scale: 1 });
  await fs.writeFile(`${renderDir}/${stem}.png`, new Uint8Array(await png.arrayBuffer()));
  const layout = await currentSlide.export({ format: 'layout' });
  await fs.writeFile(`${layoutDir}/${stem}.layout.json`, await layout.text());
}

const montage = await presentation.export({ format: 'png', montage: true, scale: 1 });
await fs.writeFile('./compact-final-montage.png', new Uint8Array(await montage.arrayBuffer()));

const inspect = await presentation.inspect({
  kind: 'slide,textbox,shape,image,notes,layout',
  maxChars: 80000,
});
await fs.writeFile('./compact-final.inspect.ndjson', inspect.ndjson, 'utf8');

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(`saved ${presentation.slides.items.length} slides to ${output}`);
