import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const p = await PresentationFile.importPptx(await FileBlob.load('./template-starter.pptx'));
const slide = p.slides.items[0];
function info(name, value) {
  const proto = value ? Object.getOwnPropertyNames(Object.getPrototypeOf(value)) : [];
  console.log(JSON.stringify({ name, keys: value ? Object.keys(value) : [], proto }));
}
info('presentation', p);
info('slides', p.slides);
info('slide', slide);
for (const collection of ['shapes', 'images', 'texts', 'groups', 'tables']) {
  const c = slide[collection];
  info(collection, c);
  const items = c?.items ?? [];
  console.log(JSON.stringify({ collection, count: items.length }));
  if (items[0]) {
    info(`${collection}[0]`, items[0]);
    console.log(JSON.stringify({
      collection,
      id: items[0].id,
      name: items[0].name,
      aid: items[0].aid,
      text: items[0].text,
      left: items[0].left,
      top: items[0].top,
      width: items[0].width,
      height: items[0].height,
    }));
  }
}
for (let si = 0; si < Math.min(5, p.slides.items.length); si += 1) {
  console.log(`SLIDE ${si + 1}`);
  for (const shape of p.slides.items[si].shapes.items) {
    const t = shape.text;
    console.log(JSON.stringify({
      id: shape.id,
      name: shape.name,
      frame: shape.frame,
      textKeys: t ? Object.keys(t) : [],
      textProto: t ? Object.getOwnPropertyNames(Object.getPrototypeOf(t)) : [],
      textPlain: t?.text,
      dataKeys: shape.data ? Object.keys(shape.data) : [],
      snapshot: shape.toSnapshot?.(),
    }));
  }
}
