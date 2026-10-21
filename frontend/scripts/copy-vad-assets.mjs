import { copyFile, mkdir, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const target = new URL('public/vendor/', root);
await mkdir(target, { recursive: true });
for (const [directory, accepts] of [
  ['node_modules/@ricky0123/vad-web/dist/', name => name === 'vad.worklet.bundle.min.js' || name === 'silero_vad_v5.onnx'],
  ['node_modules/onnxruntime-web/dist/', name => name.endsWith('.wasm') || name.endsWith('.mjs')],
]) {
  const source = new URL(directory, root);
  for (const name of await readdir(source)) {
    if (accepts(name)) await copyFile(new URL(name, source), new URL(name, target));
  }
}
console.log(`Local speech-detection assets copied to ${fileURLToPath(target)}`);
