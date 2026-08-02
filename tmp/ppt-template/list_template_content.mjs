import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const p = await PresentationFile.importPptx(await FileBlob.load('./template-starter.pptx'));
for (const [index, slide] of p.slides.items.entries()) {
  const texts = slide.shapes.items
    .map((shape) => ({ id: shape.id, text: shape.toSnapshot?.().text ?? '', frame: shape.frame }))
    .filter((item) => item.text.trim());
  const pictures = slide.shapes.items
    .filter((shape) => {
      const snap = shape.toSnapshot?.();
      return shape.data?.imageReference || shape.data?.fill?.picture || shape.data?.type === 8 || snap?.kind === 'image';
    })
    .map((shape) => ({ id: shape.id, type: shape.data?.type, frame: shape.frame, imageReference: shape.data?.imageReference, snapshot: shape.toSnapshot?.() }));
  const images = slide.images.items.map((image) => ({ id: image.id, name: image.name, frame: image.position ?? image.frame, keys: Object.keys(image) }));
  console.log(JSON.stringify({ slide: index + 1, texts, pictures, images }));
}
