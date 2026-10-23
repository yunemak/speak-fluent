// A single probable-speech frame can be a breath/cough. Confirm a short,
// recent run of speech before interrupting, while keeping buffered audio from
// before onset. Requiring a current run rejects separate bursts that would add
// up to the threshold over time.
const THRESHOLD = 0.65;

export function createSpeechGate(onConfirm, {
  confirmMs = 320,
  currentRunMs = 192,
  windowMs = 700,
  threshold = THRESHOLD,
} = {}) {
  let frames = [];
  let clock = 0;
  let confirmed = false;
  return {
    push(probability, frameMs) {
      clock += frameMs;
      frames.push({ at: clock, positive: probability >= threshold, ms: frameMs });
      while (frames.length && frames[0].at <= clock - windowMs) frames.shift();
      if (confirmed) return { positiveMs: 0, runMs: 0, confirmed };
      const positiveMs = frames.reduce(
        (total, frame) => total + (frame.positive ? frame.ms : 0), 0);
      let runMs = 0;
      for (let index = frames.length - 1; index >= 0 && frames[index].positive; index -= 1) {
        runMs += frames[index].ms;
      }
      if (positiveMs >= confirmMs && runMs >= currentRunMs) {
        confirmed = true;
        onConfirm();
      }
      return { positiveMs, runMs, confirmed };
    },
    reset() {
      frames = [];
      clock = 0;
      confirmed = false;
    },
    get confirmed() {
      return confirmed;
    },
  };
}

export function speechDetectionOptions(onSpeechStart, onSpeechEnd) {
  const gate = createSpeechGate(onSpeechStart);
  return {
    redemptionMs: 1000,
    preSpeechPadMs: 500,
    // Capture brief closing words too; playback still needs confirmed speech.
    minSpeechMs: 128,
    positiveSpeechThreshold: THRESHOLD,
    negativeSpeechThreshold: 0.4,
    onSpeechStart: () => {},
    onSpeechRealStart: () => {},
    onFrameProcessed: (probabilities, frame) => {
      gate.push(probabilities.isSpeech, frame.length / 16);
    },
    onSpeechEnd: samples => {
      const farewellOnly = !gate.confirmed;
      gate.reset();
      onSpeechEnd(samples, { farewellOnly });
    },
    // Unconfirmed noise never changed conversation state; do not change it now.
    onVADMisfire: () => gate.reset(),
  };
}
