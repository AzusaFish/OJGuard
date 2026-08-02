import fs from 'node:fs/promises';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const presentation = await PresentationFile.importPptx(await FileBlob.load('../../output/submission/OJGuard_项目介绍.pptx'));
await fs.mkdir('./final-layout', { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const blob = await presentation.export({ slide, format: 'layout' });
  const bytes = Buffer.from(await blob.arrayBuffer());
  await fs.writeFile(`./final-layout/slide-${String(index + 1).padStart(2, '0')}.layout.json`, bytes);
}
