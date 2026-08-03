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

setText(2, 33, '后端、Vue3 前端、AgentTeams 动态闭环');
setText(2, 34, '59 项测试 + 20 条实跑响应可复核');
setText(7, 38, '共享 IncidentContext 传递事实；Team Leader 每轮按最新状态路由，Worker 工具写回后由确定性状态机验收。');
setText(9, 38, '实跑从 TRIAGING 开始：11 次动态路由、8 次工具写回；假设与实验分离，三个人工门禁后才关闭。');
setText(11, 38, '9 个 Skill 声明完整协作契约；12 个 MCP 工具受状态机与审批约束，根因工具将竞争假设和对照实验拆为两个回合。');
setText(13, 38, '真实 Runner、11 次 Agent 路由、8 次 Worker 工具写回、三个人工门禁与关闭核验共同组成可审计证据。');
setText(15, 28, 'Runner、动态路由、事故报告');
setText(15, 29, '11 路由 / 8 Worker 结果随附件提供');
setText(17, 38, '事故从 TRIAGING 启动，经竞争假设、二维实验、影响定界、三次人工门禁和可信重评后关闭；20 条 AgentTeams 响应已脱敏固化。');

addSources(9, [
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
  'OJGuard materials/evidence/AgentTeams_真实运行证据.md',
]);
addSources(13, [
  'OJGuard output/evidence/java-runtime-comparison.json',
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
]);
addSources(17, [
  'OJGuard output/evidence/agentteams/agentteams-demo-result.json',
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
