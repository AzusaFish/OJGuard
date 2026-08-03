import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const input = './template-starter.pptx';
const output = '../../output/submission/OJGuard_项目介绍.pptx';
const screenshots = {
  approval: '../../output/evidence/screenshots/incident-approval.png',
  rejudge: '../../output/evidence/screenshots/rejudge-results.png',
  verified: '../../output/evidence/screenshots/verification-resolved.png',
};

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));

function shape(slideNumber, id) {
  return presentation.slides.items[slideNumber - 1].shapes.getById(String(id));
}

function setText(slideNumber, id, value, options = {}) {
  const item = shape(slideNumber, id);
  if (!item) throw new Error(`Missing shape ${id} on slide ${slideNumber}`);
  item.text = value;
  if (options.fontSize) item.text.fontSize = options.fontSize;
  if (options.bold !== undefined) item.text.bold = options.bold;
  if (options.color) item.text.color = options.color;
}

function svgDataUrl(markup) {
  return `data:image/svg+xml;base64,${Buffer.from(markup, 'utf8').toString('base64')}`;
}

function svgShell(body, width = 1280, height = 720) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="100%" height="100%" rx="24" fill="#F7F9FC"/>
    <style>
      text{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:#1B1F3B}
      .h{font-size:32px;font-weight:700}.t{font-size:22px;font-weight:600}.b{font-size:19px}.s{font-size:16px;fill:#526074}
      .card{fill:#FFFFFF;stroke:#D8E0EC;stroke-width:2}.navy{fill:#0B1F3A}.orange{fill:#FF6B35}.green{fill:#0AA37F}.blue{fill:#2F6BFF}.purple{fill:#8A4FFF}
      .white{fill:#FFFFFF}.muted{fill:#526074}.line{stroke:#C9D5E5;stroke-width:4;fill:none}.dash{stroke-dasharray:10 8}
    </style>${body}</svg>`;
  const replacements = [
    ['class="t white"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#FFFFFF;font-size:22px;font-weight:600"'],
    ['class="b white"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#FFFFFF;font-size:19px"'],
    ['class="s white"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#FFFFFF;font-size:16px"'],
    ['class="h"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#1B1F3B;font-size:32px;font-weight:700"'],
    ['class="t"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#1B1F3B;font-size:22px;font-weight:600"'],
    ['class="b"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#1B1F3B;font-size:19px"'],
    ['class="s"', 'style="font-family:Microsoft YaHei,sans-serif;fill:#526074;font-size:16px"'],
    ['class="card"', 'fill="#FFFFFF" stroke="#D8E0EC" stroke-width="2"'],
    ['class="navy"', 'fill="#0B1F3A"'],
    ['class="orange"', 'fill="#FF6B35"'],
    ['class="green"', 'fill="#0AA37F"'],
    ['class="blue"', 'fill="#2F6BFF"'],
    ['class="purple"', 'fill="#8A4FFF"'],
    ['class="line"', 'stroke="#C9D5E5" stroke-width="4" fill="none"'],
  ];
  return replacements.reduce((result, [from, to]) => result.replaceAll(from, to), svg);
}

function metricsSvg() {
  return svgShell(`
    <text x="56" y="68" class="h">一次运行时回归，污染的不只是判题</text>
    <text x="56" y="102" class="s">固定种子 20260802 · Java 运行时对照实验</text>
    <rect x="56" y="146" width="250" height="178" rx="18" class="card"/><text x="82" y="194" class="t">参赛规模</text><text x="82" y="260" class="h">5,000</text><text x="82" y="294" class="s">20,000 次提交</text>
    <rect x="330" y="146" width="250" height="178" rx="18" class="card"/><text x="356" y="194" class="t">影响范围</text><text x="356" y="260" class="h">703 / 742</text><text x="356" y="294" class="s">候选人 / 受影响提交</text>
    <rect x="56" y="350" width="250" height="178" rx="18" class="card"/><text x="82" y="398" class="t">成绩变化</text><text x="82" y="464" class="h">703</text><text x="82" y="498" class="s">预计晋级变化 72</text>
    <rect x="330" y="350" width="250" height="178" rx="18" class="card"/><text x="356" y="398" class="t">可信核验</text><text x="356" y="464" class="h">100%</text><text x="356" y="498" class="s">重/漏/越界均为 0</text>
    <path d="M650 165 H1135" class="line"/><circle cx="695" cy="165" r="17" class="orange"/><circle cx="835" cy="165" r="17" class="blue"/><circle cx="975" cy="165" r="17" class="purple"/><circle cx="1115" cy="165" r="17" class="green"/>
    <text x="650" y="225" class="t">信号</text><text x="790" y="225" class="t">定界</text><text x="930" y="225" class="t">审批</text><text x="1070" y="225" class="t">重评</text>
    <rect x="650" y="290" width="485" height="238" rx="22" class="navy"/>
    <text x="684" y="340" class="t white">核心价值</text>
    <text x="684" y="390" class="b white">• 把主观排查变成可复核证据链</text>
    <text x="684" y="430" class="b white">• 只重评受影响提交，并保证幂等</text>
    <text x="684" y="470" class="b white">• 关闭前强制校验覆盖率与边界</text>`);
}

function generalizationSvg() {
  return svgShell(`
    <text x="56" y="68" class="h">同一闭环，覆盖多类 OJ 事故</text><text x="56" y="103" class="s">已实现三类可执行固定种子场景</text>
    <rect x="56" y="150" width="356" height="410" rx="22" class="card"/><rect x="56" y="150" width="356" height="70" rx="22" class="orange"/><text x="82" y="195" class="t white">Java 运行时回归</text><text x="82" y="270" class="b">703 / 742 受影响</text><text x="82" y="310" class="b">正常 3/3 OK</text><text x="82" y="350" class="b">退化 3/3 TLE</text><text x="82" y="410" class="s">镜像对照 + SHA-256 证据</text><text x="82" y="455" class="s">主演示场景</text>
    <rect x="462" y="150" width="356" height="410" rx="22" class="card"/><rect x="462" y="150" width="356" height="70" rx="22" class="blue"/><text x="488" y="195" class="t white">评测节点退化</text><text x="488" y="270" class="b">118 / 119 受影响</text><text x="488" y="310" class="b">性能偏差与节点关联</text><text x="488" y="350" class="b">预计晋级变化 14</text><text x="488" y="410" class="s">节点隔离 + 精准重评</text><text x="488" y="455" class="s">泛化场景 A</text>
    <rect x="868" y="150" width="356" height="410" rx="22" class="card"/><rect x="868" y="150" width="356" height="70" rx="22" class="green"/><text x="894" y="195" class="t white">Checker 缺陷</text><text x="894" y="270" class="b">71 / 73 受影响</text><text x="894" y="310" class="b">判定逻辑与版本关联</text><text x="894" y="350" class="b">预计晋级变化 8</text><text x="894" y="410" class="s">规则修复 + 结果核验</text><text x="894" y="455" class="s">泛化场景 B</text>
    <text x="56" y="632" class="t">统一状态机：DETECTED → DIAGNOSING → SCOPED → APPROVED → REJUDGING → VERIFYING → RESOLVED</text>`);
}

function architectureSvg() {
  const boxes = [
    ['异常信号','告警 / 投诉 / 分布偏移','#FF6B35'],['AgentTeams','主管理器 + 6 专职 Worker','#8A4FFF'],['确定性工具','12 个 MCP 工具','#2F6BFF'],['审批闸门','控制组 / 灰度 / 全量','#0AA37F'],['可信重评','幂等批次 + 结果核验','#0B1F3A']
  ];
  let body = `<text x="54" y="70" class="h">证据驱动的在线测评事故闭环</text><text x="54" y="107" class="s">Agent 负责协同与解释，确定性工具负责事实与执行</text>`;
  boxes.forEach(([title, desc, color], i) => {
    const x = 48 + i * 244;
    body += `<rect x="${x}" y="180" width="210" height="150" rx="20" fill="#FFFFFF" stroke="${color}" stroke-width="4"/><text x="${x+22}" y="225" class="t">${title}</text><text x="${x+22}" y="270" class="s">${desc}</text>`;
    if (i < boxes.length - 1) body += `<path d="M${x+212} 255 H${x+238}" stroke="#9DB0C8" stroke-width="5"/><path d="M${x+232} 245 l12 10 -12 10" fill="#9DB0C8"/>`;
  });
  body += `<rect x="48" y="390" width="1178" height="185" rx="22" class="navy"/><text x="80" y="435" class="t white">治理底座</text><text x="80" y="480" class="b white">十阶段事故状态机 · 审批留痕 · 高风险动作阻断 · 重评幂等键 · 覆盖率与边界核验</text><text x="80" y="525" class="b white">SQLite 事故台账 · JSON / HTML 报告 · Java 真实运行对照 · AgentTeams 运行证据</text>`;
  return svgShell(body);
}

function agentsSvg() {
  const roles = [['Team Leader','汇总状态 / 分派任务'],['Signal Worker','信号融合'],['Root Cause','根因证据'],['Impact Worker','影响定界'],['Plan Worker','重评计划'],['Rejudge Worker','批次执行'],['Verify Worker','关闭核验']];
  let body = `<text x="48" y="66" class="h">主管理器编排 6 个专职 Worker</text><text x="48" y="102" class="s">共享事故编号与事实快照，输出可追溯阶段结果</text>`;
  roles.forEach(([name, desc], i) => {
    const row = i === 0 ? 0 : i <= 3 ? 1 : 2;
    const col = i === 0 ? 0 : i <= 3 ? i - 1 : i - 4;
    const x = i === 0 ? 450 : 55 + col * 405;
    const y = i === 0 ? 140 : row === 1 ? 300 : 470;
    const w = i === 0 ? 380 : 360;
    body += `<rect x="${x}" y="${y}" width="${w}" height="112" rx="18" class="card"/><rect x="${x}" y="${y}" width="12" height="112" rx="6" class="${i===0?'orange':i<=3?'blue':'green'}"/><text x="${x+32}" y="${y+45}" class="t">${name}</text><text x="${x+32}" y="${y+80}" class="s">${desc}</text>`;
  });
  return svgShell(body);
}

function governanceSvg() {
  return svgShell(`
    <text x="52" y="67" class="h">自主分析，受控执行</text><text x="52" y="105" class="s">建议可并行，高风险动作必须通过人工闸门</text>
    <rect x="52" y="160" width="330" height="105" rx="18" class="card"/><text x="78" y="207" class="t">并行研判</text><text x="78" y="240" class="s">根因 / 影响 / 重评计划</text>
    <rect x="475" y="160" width="330" height="105" rx="18" class="card"/><text x="501" y="207" class="t">证据冲突</text><text x="501" y="240" class="s">置信度不足则回退调查</text>
    <rect x="898" y="160" width="330" height="105" rx="18" class="card"/><text x="924" y="207" class="t">批准执行</text><text x="924" y="240" class="s">单人按角色上下文确认</text>
    <path d="M382 212 H475 M805 212 H898" class="line"/>
    <rect x="52" y="330" width="1176" height="230" rx="22" class="navy"/>
    <text x="86" y="378" class="t white">三道安全闸门</text>
    <circle cx="117" cy="435" r="24" class="orange"/><text x="108" y="443" class="t white">1</text><text x="160" y="442" class="b white">控制组：确认修复不会改变健康提交</text>
    <circle cx="117" cy="490" r="24" class="blue"/><text x="108" y="498" class="t white">2</text><text x="160" y="497" class="b white">灰度批次：比较错误率、耗时与成绩漂移</text>
    <circle cx="700" cy="435" r="24" class="green"/><text x="691" y="443" class="t white">3</text><text x="743" y="442" class="b white">全量重评：幂等执行，批次状态可恢复</text>
    <text x="743" y="497" class="b white">关闭条件：覆盖 100%，重/漏/越界均为 0</text>`);
}

function skillsSvg() {
  const groups = [
    ['信号与定界','信号归一\n事件关联\n影响定界','#2F6BFF'],
    ['根因审查','控制复现\n题包审计','#8A4FFF'],
    ['处置执行','处置规划\n受控重评','#FF6B35'],
    ['独立核验','一致性核验\n事故报告','#0AA37F']
  ];
  let body = `<text x="50" y="66" class="h">9 个 Skill，把经验沉淀为可复用能力</text><text x="50" y="103" class="s">统一输入输出、依赖、失败处理与审批边界</text>`;
  groups.forEach(([title, lines, color], i) => {
    const x = 50 + i * 300;
    body += `<rect x="${x}" y="155" width="270" height="350" rx="22" class="card"/><rect x="${x}" y="155" width="270" height="72" rx="22" fill="${color}"/><text x="${x+28}" y="201" class="t white">${title}</text>`;
    lines.split('\n').forEach((line,j)=> body += `<rect x="${x+22}" y="${255+j*70}" width="226" height="48" rx="12" fill="#F2F5FA"/><text x="${x+37}" y="${286+j*70}" class="b">${line}</text>`);
  });
  body += `<rect x="50" y="550" width="1170" height="76" rx="18" class="navy"/><text x="78" y="598" class="b white">12 个 MCP 工具：信号 / 部署 / 重放 / 题包 / 影响 / 重评 / 成绩 / 核验 / 报告</text>`;
  return svgShell(body);
}

function evidenceSvg() {
  return svgShell(`
    <text x="54" y="70" class="h">真实 Java Runner 对照证据</text><text x="54" y="108" class="s">同一提交、同一限制，仅运行时镜像不同</text>
    <rect x="54" y="158" width="535" height="340" rx="22" class="card"/><rect x="54" y="158" width="535" height="72" rx="22" class="green"/><text x="82" y="204" class="t white">normal-17</text><text x="82" y="282" class="h">3 / 3 OK</text><text x="82" y="334" class="b">39 ms · 45 ms · 61 ms</text><text x="82" y="392" class="s">所有样例均在 80 ms 限制内</text><text x="82" y="442" class="s">Runner 结果已固化至证据文件</text>
    <rect x="641" y="158" width="535" height="340" rx="22" class="card"/><rect x="641" y="158" width="535" height="72" rx="22" class="orange"/><text x="669" y="204" class="t white">degraded-17</text><text x="669" y="282" class="h">3 / 3 TLE</text><text x="669" y="334" class="b">92 ms · 91 ms · 83 ms</text><text x="669" y="392" class="s">同一限制下稳定超时</text><text x="669" y="442" class="s">镜像与结果均带 SHA-256</text>
    <rect x="54" y="548" width="1122" height="76" rx="18" class="navy"/><text x="84" y="596" class="b white">结论：运行时退化与错误结果存在可复核因果证据，重评范围由事实筛选而非模型猜测。</text>`);
}

function finalSvg() {
  return svgShell(`
    <text x="54" y="70" class="h">从事故创建到可信关闭：全链路已跑通</text>
    <rect x="54" y="132" width="250" height="150" rx="20" class="card"/><text x="80" y="180" class="t">AgentTeams</text><text x="80" y="238" class="h">6 / 6</text><text x="80" y="266" class="s">Worker 完成协作</text>
    <rect x="330" y="132" width="250" height="150" rx="20" class="card"/><text x="356" y="180" class="t">影响范围</text><text x="356" y="238" class="h">703 / 742</text><text x="356" y="266" class="s">候选人 / 提交</text>
    <rect x="606" y="132" width="250" height="150" rx="20" class="card"/><text x="632" y="180" class="t">批次</text><text x="632" y="238" class="h">4 / 4</text><text x="632" y="266" class="s">控制 / 灰度 / 全量</text>
    <rect x="882" y="132" width="294" height="150" rx="20" class="card"/><text x="908" y="180" class="t">最终状态</text><text x="908" y="238" class="h">RESOLVED</text><text x="908" y="266" class="s">覆盖率 100%</text>
    <path d="M80 370 H1150" class="line"/><circle cx="110" cy="370" r="18" class="orange"/><circle cx="330" cy="370" r="18" class="purple"/><circle cx="550" cy="370" r="18" class="blue"/><circle cx="770" cy="370" r="18" class="green"/><circle cx="990" cy="370" r="18" class="navy"/>
    <text x="76" y="425" class="b">发现</text><text x="296" y="425" class="b">诊断</text><text x="516" y="425" class="b">审批</text><text x="736" y="425" class="b">重评</text><text x="956" y="425" class="b">关闭</text>
    <rect x="54" y="490" width="1122" height="108" rx="20" class="navy"/><text x="84" y="535" class="b white">GitHub：github.com/AzusaFish/OJGuard</text><text x="84" y="570" class="s white">Apache-2.0 · Vue3 + FastAPI + AgentTeams · 证据与三类场景随仓库提供</text>`);
}

async function replaceImages(slideNumber, sources) {
  const slide = presentation.slides.items[slideNumber - 1];
  const frames = slide.images.items.map((item) => ({
    left: item.position.left,
    top: item.position.top,
    width: item.position.width,
    height: item.position.height,
  }));
  for (const item of [...slide.images.items]) slide.images.deleteById(item.id);
  if (frames.length !== sources.length) throw new Error(`Slide ${slideNumber}: expected ${frames.length} sources, got ${sources.length}`);
  for (let i = 0; i < sources.length; i += 1) {
    const source = sources[i];
    let image;
    if (source.path) {
      const bytes = await fs.readFile(source.path);
      const blob = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      image = slide.images.add({ blob, fit: source.fit ?? 'contain', alt: source.alt });
    } else {
      image = slide.images.add({ dataUrl: svgDataUrl(source.svg), fit: source.fit ?? 'contain', alt: source.alt });
    }
    image.position = frames[i];
  }
}

const textMap = {
  1: {5:'GOAI 世界人工智能开源大赛 · Agent Infra',6:'OJGuard\n在线测评事故响应与可信重评',18:'单人团队 · 可运行开源作品',19:'从异常信号到可信重评，以证据驱动闭环'},
  2: {2:'P0 · 一页纸速览',3:'作品简介',7:'项目名称',8:'面向在线测评运营',9:'OJGuard',12:'问题与场景',13:'环境异常会污染评测结果',14:'难定位、难定界、难安全重评',17:'核心解决方案',18:'多 Agent 协同 + 确定性工具',19:'发现→定界→审批→重评→核验',22:'创新点与差异化',23:'证据优先、幂等重评、状态机治理',24:'高风险动作必须人工批准',27:'开放 / 复用价值',28:'9 Skills / 12 MCP 工具',29:'可迁移节点退化与 Checker 缺陷',32:'当前进展',33:'后端、Vue3 前端、AgentTeams',34:'三类场景与运行证据均可复现'},
  3: {5:'目录',9:'场景与价值',13:'工程落地与证据',17:'方案总览',21:'开源与复用',25:'AgentTeams 协同',29:'演示路径',33:'Skill / MCP 工程',37:'验证结果'},
  4: {2:'第一章',3:'场景与价值',5:'对应评分维度',6:'场景价值与行业可复制性',8:'25%'},
  5: {3:'第一章',4:'真实事故：Java 运行时回归',5:'镜像切换后错误率从 8.3% 升至 41.4%。OJGuard 将异常还原为可复核证据、精确影响范围与可信重评任务。',7:'固定种子 20260802 · 三类场景均可复现'},
  6: {2:'第二章',3:'方案总览'},
  7: {2:'第二章 · 承上启下',3:'方案总览',38:'共享 IncidentContext 与全链路 Trace 传递上下文；Agent 负责协同，确定性工具负责事实与执行。'},
  8: {5:'第三章',6:'AgentTeams 协同设计',8:'对应评分维度',9:'多 Agent 协同与自主闭环能力',11:'25%'},
  9: {2:'第三章',3:'AgentTeams 协同设计',38:'Team Leader 编排 6 个专职 Worker；共享事故状态，证据冲突则回退，高风险执行必须经过人工批准。'},
  10: {2:'第四章',3:'Skill / MCP 工程体系',12:'对应评分维度',13:'Skill 工程体系与生态复用',15:'25%'},
  11: {2:'第四章 · 本赛题必选项',3:'9 个可复用 Skill',8:'25%',38:'每个 Skill 均声明输入输出、依赖工具、失败、安全、复用和 Agent 协作；12 个 MCP 工具具备 Schema、门禁、幂等与迁移契约。'},
  12: {5:'第五章',6:'工程落地与运行证据',8:'对应评分维度',9:'工程落地与安全可审计',11:'20%'},
  13: {2:'第五章',3:'可复现证据链',38:'真实 Java Runner 对照、审批轨迹、分批重评与关闭核验共同组成可审计证据；报告可导出 JSON / HTML。'},
  14: {2:'第六章',3:'开放 / 开源贡献',17:'对应评分维度',18:'开放 / 开源贡献',20:'5%'},
  15: {2:'第六章 · Apache-2.0',3:'开放 / 开源贡献',7:'代码仓库',8:'完整源码与运行说明',9:'github.com/AzusaFish/OJGuard',12:'可复用资产',13:'9 Skills、12 MCP 工具、三类场景',14:'可单独接入其他 OJ',17:'扩展边界',18:'适配器契约预留',19:'队列 / 配置类事故可新增 Playbook',22:'运行方式',23:'PowerShell 脚本或本地启动',24:'演示数据一键生成',27:'证据包',28:'Runner、AgentTeams、事故报告',29:'均随提交附件提供',32:'完成状态',33:'前后端与闭环已可运行',34:'Demo 由参赛者现场录制'},
  16: {4:'第七章 · 对应「当前进展」与整体可行性',5:'Demo 与提交状态'},
  17: {2:'第七章 · 可运行成果',3:'已完成的闭环证据',38:'创建事故 → 角色审批 → 控制组 → 灰度 → 全量重评 → 关闭核验；浏览器端已完成全链路实测。'},
};

for (const [slideNumber, entries] of Object.entries(textMap)) {
  for (const [id, value] of Object.entries(entries)) setText(Number(slideNumber), id, value);
}

for (const [index, slide] of presentation.slides.items.entries()) {
  const page = slide.shapes.items.find((item) => item.frame?.top > 650 && /^\d+$/.test(item.toSnapshot?.().text ?? ''));
  if (page) page.text = String(index + 1);
}

await replaceImages(5, [
  { svg: metricsSvg(), alt: 'Java runtime regression metrics' },
  { svg: generalizationSvg(), alt: 'Three executable incident scenarios' },
]);
await replaceImages(7, [{ svg: architectureSvg(), alt: 'OJGuard end-to-end architecture' }]);
await replaceImages(9, [
  { svg: agentsSvg(), alt: 'AgentTeams roles' },
  { svg: governanceSvg(), alt: 'Approval and conflict governance' },
]);
await replaceImages(11, [{ svg: skillsSvg(), alt: 'Nine reusable Skills and twelve MCP tools' }]);
await replaceImages(13, [
  { path: screenshots.approval, alt: 'Approval workflow screenshot' },
  { path: screenshots.rejudge, alt: 'Rejudge results screenshot' },
  { path: screenshots.verified, alt: 'Verification resolved screenshot' },
  { svg: evidenceSvg(), alt: 'Java runner evidence summary' },
]);
await replaceImages(17, [
  { path: screenshots.verified, alt: 'Resolved incident screenshot' },
  { svg: finalSvg(), alt: 'OJGuard completed evidence summary' },
]);

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
