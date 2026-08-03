import { FileBlob, PresentationFile } from '@oai/artifact-tool';
import fs from 'node:fs/promises';

const presentation = await PresentationFile.importPptx(await FileBlob.load('../../output/submission/OJGuard_项目介绍.compact.pptx'));
const pdf = await presentation.export({ format: 'pdf' });
await fs.writeFile('../../output/submission/OJGuard_项目介绍.pdf', Buffer.from(await pdf.arrayBuffer()));
