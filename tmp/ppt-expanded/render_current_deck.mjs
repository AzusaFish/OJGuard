import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const input = '../../output/submission/OJGuard_项目介绍.pptx';
const renderDir = './current-final-render';
const layoutDir = './current-final-layout';

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
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
await fs.writeFile('./current-final-montage.png', new Uint8Array(await montage.arrayBuffer()));

const inspect = await presentation.inspect({
  kind: 'slide,textbox,shape,image,notes,layout',
  maxChars: 80000,
});
await fs.writeFile('./current-final.inspect.ndjson', inspect.ndjson, 'utf8');

console.log(`rendered ${presentation.slides.items.length} slides`);
