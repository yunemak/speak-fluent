import { MicVAD } from '@ricky0123/vad-web';
import { speechDetectionOptions } from './vad.js';

export function encodeWav(samples) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset, value) => [...value].forEach((letter, index) => view.setUint8(offset + index, letter.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true);
  text(8, 'WAVE'); text(12, 'fmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, 'data'); view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const value = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, value * (value < 0 ? 32768 : 32767), true);
  });
  return buffer;
}

export class BrowserAudio {
  context = null;
  vad = null;
  stream = null;
  output = null;
  generation = 0;

  // Called synchronously from Start/Retry so the browser permits audible output.
  unlock() {
    if (!this.context || this.context.state === 'closed') this.context = new AudioContext();
    return this.context.resume();
  }

  async listen(callbacks) {
    const generation = ++this.generation;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: {
        channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true,
      } });
    } catch {
      throw new Error('Microphone unavailable. Allow microphone access in Chromium and check your Linux input device, then retry.');
    }
    if (generation !== this.generation) {
      this.stream.getTracks().forEach(track => track.stop());
      return;
    }
    const vad = await MicVAD.new({
      model: 'v5', startOnLoad: false, audioContext: this.context,
      baseAssetPath: '/vendor/',
      // Absolute same-origin URL keeps Vite from treating ONNX's runtime .mjs
      // import as application source (public assets must be served unchanged).
      onnxWASMBasePath: new URL('/vendor/', window.location.href).href,
      ortConfig: ort => { ort.env.wasm.numThreads = 1; },
      getStream: async () => this.stream,
      ...speechDetectionOptions(callbacks.onSpeechStart,
        (samples, options) => callbacks.onSpeechEnd(encodeWav(samples), options)),
    });
    if (generation !== this.generation) {
      await vad.destroy();
      return;
    }
    this.vad = vad;
    await vad.start();
  }

  async pauseInput() {
    this.stream?.getTracks().forEach(track => track.stop());
    await this.vad?.pause();
  }

  stop() {
    this.output?.finish('interrupted');
  }

  async play(bytes, current, onStart) {
    const context = this.context;
    const decoded = await context.decodeAudioData(bytes.slice(0));
    if (!current()) return 'interrupted';
    if (context.state !== 'running') throw new Error('Audio is paused by the browser. Press Retry to allow playback.');
    const source = context.createBufferSource();
    source.buffer = decoded;
    source.connect(context.destination);
    return new Promise((resolve, reject) => {
      let settled = false;
      const output = {
        finish: reason => {
          if (settled) return;
          settled = true;
          source.onended = null;
          if (reason !== 'ended') source.stop();
          source.disconnect();
          if (this.output === output) this.output = null;
          resolve(reason);
        },
      };
      this.output = output;
      source.onended = () => output.finish('ended');
      try {
        source.start();
        onStart();
      } catch (error) {
        this.output = null;
        source.disconnect();
        reject(error);
      }
    });
  }

  async close() {
    this.generation += 1;
    this.stop();
    this.stream?.getTracks().forEach(track => track.stop());
    const vad = this.vad;
    const context = this.context;
    this.vad = null;
    this.stream = null;
    this.context = null;
    try { await vad?.destroy(); } finally {
      if (context && context.state !== 'closed') await context.close();
    }
  }
}
