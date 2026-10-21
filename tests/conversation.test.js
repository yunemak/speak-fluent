import test from 'node:test';
import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import { Conversation } from '../frontend/src/lib/conversation.js';
import { speechDetectionOptions } from '../frontend/src/lib/vad.js';
import { FrameProcessor } from '../frontend/node_modules/@ricky0123/vad-web/dist/frame-processor.js';
import { Message } from '../frontend/node_modules/@ricky0123/vad-web/dist/messages.js';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function harness(overrides = {}) {
  const calls = { replies: [], plays: [], transcriptions: [], saves: [], reports: 0, stops: 0, paused: 0 };
  let output;
  const audio = {
    unlock: async () => {}, listen: async () => {}, close: async () => {},
    pauseInput: async () => { calls.paused += 1; },
    stop: () => { calls.stops += 1; output?.resolve('interrupted'); output = null; },
    play: async (bytes, current, start) => {
      if (!current()) return 'interrupted';
      calls.plays.push(bytes); start();
      output = deferred();
      return output.promise;
    },
    end: () => { output?.resolve('ended'); output = null; },
  };
  const api = {
    health: async () => ({ ready: true }),
    save: async body => { calls.saves.push(body); return { id: body.id, title: 'Saved practice', filename: `${body.id}.md` }; },
    reply: async body => { calls.replies.push(body); return { request_id: body.request_id, text: 'How was your day?' }; },
    speech: async body => body.text,
    transcribe: async wav => { calls.transcriptions.push(wav); return { text: wav, is_farewell: wav === 'Goodbye.' }; },
    report: async body => { calls.reports += 1; return { request_id: body.request_id, report_text: 'Useful feedback.' }; },
    ...overrides,
  };
  const c = new Conversation(api, audio, () => {});
  return { c, api, audio, calls };
}

function detector(c, text = 'Recognized speech.') {
  const options = speechDetectionOptions(() => c.speechStart(),
    (_samples, capture) => c.speechEnd(text, capture));
  let probability = 0;
  const processor = new FrameProcessor(async () => ({ isSpeech: probability, notSpeech: 1 - probability }),
    () => {}, options, 32);
  const events = {
    [Message.SpeechStart]: options.onSpeechStart,
    [Message.SpeechRealStart]: options.onSpeechRealStart,
    [Message.SpeechEnd]: options.onSpeechEnd,
    [Message.VADMisfire]: options.onVADMisfire,
    [Message.FrameProcessed]: (_audio, event) => options.onFrameProcessed(event.probs, event.frame),
  };
  processor.resume();
  return async (value, frames) => {
    probability = value;
    for (let i = 0; i < frames; i++) {
      await processor.process(new Float32Array(512), event => events[event.msg]?.(event.audio, event));
    }
  };
}

test('brief speech-like noise and uncertain sound leave playback and its speaking state intact', async () => {
  const { c, audio, calls } = harness();
  const starting = c.start();
  await setImmediate();
  const frames = detector(c);
  const stopsBefore = calls.stops;
  await frames(0.95, 4); // 128 ms false onset: enough to trigger the old callback
  await frames(0.05, 32); // let VAD reject it as a misfire
  await frames(0.5, 40); // uncertain sound below the new threshold
  assert.equal(calls.stops, stopsBefore);
  assert.equal(c.state.phase, 'speaking');
  assert.equal(c.state.speaking, true);
  assert.equal(c.state.turns[0].interrupted, false);
  assert.equal(calls.transcriptions.length, 1); // short candidate checked, then ignored
  assert.equal(c.state.turns.length, 1);
  audio.end();
  await starting;
});

test('confirmed speech interrupts at 320 ms and its captured turn still drives a reply', async () => {
  const { c, audio, calls } = harness();
  const starting = c.start();
  await setImmediate();
  const frames = detector(c);
  await frames(0.95, 9);
  assert.equal(c.state.speaking, true);
  await frames(0.95, 1);
  assert.equal(c.state.speaking, false);
  assert.equal(c.state.turns[0].interrupted, true);
  await frames(0.05, 32);
  await setImmediate();
  assert.equal(calls.replies.at(-1).turns.at(-1).text, 'Recognized speech.');
  audio.end();
  await starting;
});

test('a brief goodbye bypasses the interruption threshold only after recognition confirms closing', async () => {
  const recognized = deferred();
  const { c, audio, calls } = harness({ transcribe: () => recognized.promise });
  const starting = c.start();
  await setImmediate();
  const frames = detector(c, 'Goodbye.');
  await frames(0.95, 5); // 160 ms, below the 320 ms interruption threshold
  await frames(0.05, 32);
  assert.equal(c.state.phase, 'speaking');
  assert.equal(c.state.turns[0].interrupted, false);
  recognized.resolve({ text: 'Goodbye.', is_farewell: true });
  await setImmediate();
  assert.equal(c.state.phase, 'feedback-speaking');
  assert.equal(c.state.turns[0].interrupted, true);
  assert.equal(calls.reports, 1);
  assert.equal(calls.paused, 1);
  audio.end();
  await starting;
  await setImmediate();
  assert.equal(c.state.phase, 'complete');
});

test('a short farewell while listening produces feedback instead of being dropped as noise', async () => {
  const { c, audio, calls } = harness();
  const starting = c.start();
  await setImmediate(); audio.end(); await starting;
  const frames = detector(c, 'Goodbye.');
  await frames(0.95, 5);
  await frames(0.05, 32);
  await setImmediate();
  assert.equal(calls.reports, 1);
  assert.equal(c.state.phase, 'feedback-speaking');
  audio.end(); await setImmediate();
  assert.equal(c.state.phase, 'complete');
});

test('failed recognition of a brief noise cannot interrupt or corrupt live playback', async () => {
  const { c, audio } = harness({ transcribe: async () => { throw new Error('Unavailable'); } });
  const starting = c.start();
  await setImmediate();
  const frames = detector(c);
  await frames(0.95, 5);
  await frames(0.05, 32);
  await setImmediate();
  assert.equal(c.state.phase, 'speaking');
  assert.equal(c.state.speaking, true);
  assert.equal(c.state.turns[0].interrupted, false);
  audio.end(); await starting;
});

test('a rejected noise onset does not discard a pending generated reply', async () => {
  const late = deferred();
  let body;
  const { c, audio, calls } = harness({ reply: request => { body = request; return late.promise; } });
  const starting = c.start();
  await setImmediate();
  const frames = detector(c);
  await frames(0.9, 3);
  await frames(0.05, 32);
  assert.equal(c.state.phase, 'thinking');
  late.resolve({ request_id: body.request_id, text: 'Here is your reply.' });
  await setImmediate();
  assert.equal(calls.plays.length, 1);
  audio.end();
  await starting;
});

test('an interrupted opening that arrives late cannot speak or enter the transcript', async () => {
  const late = deferred();
  let body;
  const { c, calls } = harness({ reply: request => { body = request; return late.promise; } });
  const starting = c.start();
  await setImmediate();
  c.speechStart();
  late.resolve({ request_id: body.request_id, text: 'An obsolete opening.' });
  await starting;
  assert.equal(calls.plays.length, 0);
  assert.equal(c.state.turns.length, 0);
  assert.equal(c.state.userSpeaking, true);
});

test('late synthesis after interruption is discarded even when transport ignores abort', async () => {
  const late = deferred();
  const { c, calls } = harness({ speech: () => late.promise });
  const starting = c.start();
  await setImmediate();
  c.speechStart();
  late.resolve('late WAV');
  await starting;
  assert.equal(calls.plays.length, 0);
  assert.equal(c.state.turns.length, 0);
});

test('audible interruption stops synchronously and records that not all words were heard', async () => {
  const { c, calls, audio } = harness();
  const starting = c.start();
  await setImmediate();
  assert.equal(c.state.speaking, true);
  c.speechStart();
  assert.equal(c.state.speaking, false);
  assert.equal(c.state.turns[0].interrupted, true);
  c.speechEnd('I went swimming.');
  await setImmediate();
  assert.equal(calls.replies.at(-1).turns.at(-1).text, 'I went swimming.');
  audio.end();
  await starting;
});

test('real utterances remain ordered; starting another never cancels recognition', async () => {
  const first = deferred();
  const captured = [];
  const { c, calls, audio } = harness({ transcribe: (wav, signal) => {
    captured.push({ wav, signal });
    return wav === 'first' ? first.promise : Promise.resolve({ text: 'Second turn.', is_farewell: false });
  } });
  const starting = c.start();
  await setImmediate(); audio.end(); await starting;
  c.speechStart(); c.speechEnd('first');
  c.speechStart(); c.speechEnd('second');
  assert.equal(captured.length, 1);
  assert.equal(captured[0].signal.aborted, false);
  first.resolve({ text: 'First turn.', is_farewell: false });
  await setImmediate();
  assert.deepEqual(c.state.turns.filter(t => t.role === 'user').map(t => t.text), ['First turn.', 'Second turn.']);
  assert.equal(calls.replies.length, 2); // one opening plus one reply after both turns
  audio.end();
});

test('farewell closes input, drops later queued speech, and completes only after the report is heard', async () => {
  const farewell = deferred();
  const { c, calls, audio } = harness({ transcribe: () => farewell.promise });
  const starting = c.start();
  await setImmediate(); audio.end(); await starting;
  c.speechStart(); c.speechEnd('Goodbye.');
  c.speechStart(); c.speechEnd('Too late.');
  farewell.resolve({ text: 'Goodbye.', is_farewell: true });
  await setImmediate();
  assert.equal(calls.reports, 1);
  assert.equal(calls.paused, 1);
  assert.equal(calls.replies.length, 1);
  assert.equal(c.state.phase, 'feedback-speaking');
  assert.equal(calls.saves.length, 0);
  c.speechStart(); // report cannot be interrupted by a practice turn
  assert.equal(c.state.phase, 'feedback-speaking');
  audio.end(); await setImmediate();
  assert.equal(c.state.phase, 'complete');
  assert.equal(calls.saves.length, 1);
  assert.equal(calls.saves[0].report_text, 'Useful feedback.');
  assert.deepEqual(c.state.turns.filter(t => t.role === 'user').map(t => t.text), ['Goodbye.']);
});

test('save failure retains the finished session and retries the same ID without replaying feedback', async () => {
  const saves = [];
  const { c, audio, calls } = harness({ save: async body => {
    saves.push(structuredClone(body));
    if (saves.length === 1) throw new Error('Disk full. Please retry saving.');
    return { id: body.id, title: 'Saved practice', filename: `${body.id}.md` };
  } });
  const starting = c.start();
  await setImmediate(); audio.end(); await starting;
  c.speechStart(); c.speechEnd('Goodbye.');
  await setImmediate();
  assert.equal(saves.length, 0);
  audio.end(); await setImmediate();
  assert.equal(c.state.phase, 'error');
  assert.equal(c.state.retryLabel, 'Retry save');
  assert.equal(c.state.report, 'Useful feedback.');
  assert.equal(c.state.savedConversation, null);
  const plays = calls.plays.length;
  await c.retry();
  assert.equal(c.state.phase, 'complete');
  assert.deepEqual(saves[0], saves[1]);
  assert.equal(calls.plays.length, plays);
  assert.equal(calls.reports, 1);
  assert.equal(c.state.savedConversation.id, c.state.sessionId);
});

test('recognition retry preserves the failed utterance and never invents text', async () => {
  let attempts = 0;
  const { c, audio } = harness({ transcribe: async wav => {
    attempts += 1;
    if (attempts === 1) throw new Error('Recognition failed.');
    return { text: wav, is_farewell: false };
  } });
  const starting = c.start();
  await setImmediate(); audio.end(); await starting;
  c.speechStart(); c.speechEnd('I like cooking.'); await setImmediate();
  assert.equal(c.state.phase, 'error');
  assert.equal(c.state.turns.filter(t => t.role === 'user').length, 0);
  await c.retry(); await setImmediate();
  assert.equal(c.state.turns.filter(t => t.role === 'user').length, 1);
  assert.equal(attempts, 2);
  audio.end();
});
