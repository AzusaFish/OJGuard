import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const input = './live-edit-audit/template-starter.pptx';
const output = '../../output/submission/OJGuard_项目介绍.pptx';
const renderDir = './qa-live-final-render';
const layoutDir = './qa-live-final-layout';

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));

await fs.mkdir('./live-edit-audit/template-starter-layout', { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(
    `./live-edit-audit/template-starter-layout/slide-${String(index + 1).padStart(2, '0')}.layout.json`,
    await layout.text(),
  );
}

function setText(slideNumber, shapeId, value) {
  const slide = presentation.slides.items[slideNumber - 1];
  const target = slide.shapes.getById(String(shapeId));
  if (!target) throw new Error(`Missing shape ${shapeId} on slide ${slideNumber}`);
  target.text = value;
}

function addSources(slideNumber, lines) {
  const notes = presentation.slides.items[slideNumber - 1].speakerNotes;
  const marker = '[Sources]';
  const current = notes.textFrame.text ?? '';
  const cleaned = current.includes(marker) ? current.split(marker)[0].trimEnd() : current.trimEnd();
  notes.textFrame.setText([cleaned, marker, ...lines].filter(Boolean).join('\n'));
  notes.setVisible(true);
}

setText(2, 33, '后端、Vue3 前端、AgentTeams 动态路由与恢复');
setText(2, 34, '63 项测试 + 两类协作证据可复核');
setText(7, 38, '共享 IncidentContext 生成合法 RouteOption；Manager 选择实验，AgentRun/Event 按序记录路由、工具、门禁与状态。');
setText(9, 38, '3 个实验候选可补选；灰度失败进入 PAUSED，经新计划与重新审批恢复；真实协作已完成 20 条响应。');
setText(11, 38, '9 个 Skill 定义协作边界；12 个 MCP 工具支持候选实验与版本化恢复，确定性状态机拒绝合同外路由和越权执行。');
setText(13, 38, '真实 AgentTeams 证明 6 个 Worker 参与；零成本证据验证 3 候选补选与灰度恢复；两类证据分级、不混淆。');
setText(15, 28, 'Runner、AgentRun、动态路由与恢复');
setText(15, 29, '真实协作 + 零成本异常链证据');
setText(17, 38, '真实协作从 TRIAGING 推进至 RESOLVED；确定性证据补齐“3 候选→补选实验”和“灰度失败→新计划→重审批→恢复灰度”，63 项测试全部通过。');

addSources(9, [
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
  'OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json',
  'OJGuard materials/evidence/AgentTeams_真实运行证据.md',
]);
addSources(11, [
  'OJGuard materials/MCP_工具契约与迁移说明.md',
  'OJGuard tests/test_agentteams_runtime_control.py',
]);
addSources(13, [
  'OJGuard output/evidence/java-runtime-comparison.json',
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
  'OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json',
]);
addSources(15, [
  'OJGuard README.md',
  'OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json',
]);
addSources(17, [
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
  'OJGuard output/evidence/agentteams/deterministic-recovery-evidence.json',
  'OJGuard output/evidence/incidents/runtime-regression-report.json',
]);

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
await fs.writeFile('./qa-live-final-montage.png', new Uint8Array(await montage.arrayBuffer()));

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
