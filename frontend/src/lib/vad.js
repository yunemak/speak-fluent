// A single probable-speech frame can be a breath/cough. Confirm a short run of
// speech before interrupting, while keeping buffered audio from before onset.
export function speechDetectionOptions(onSpeechStart, onSpeechEnd) {
  let positiveMs = 0;
  let confirmed = false;
  const reset = () => { positiveMs = 0; confirmed = false; };
  return {
    redemptionMs: 1000,
    preSpeechPadMs: 500,
    // Capture brief closing words too; playback still needs 320 ms confirmation.
    minSpeechMs: 128,
    positiveSpeechThreshold: 0.65,
    negativeSpeechThreshold: 0.4,
    onSpeechStart: () => {},
    onSpeechRealStart: () => {},
    onFrameProcessed: (probabilities, frame) => {
      if (probabilities.isSpeech >= 0.65) positiveMs += frame.length / 16;
      if (!confirmed && positiveMs >= 320) {
        confirmed = true;
        onSpeechStart();
      }
    },
    onSpeechEnd: samples => {
      const farewellOnly = !confirmed;
      reset();
      onSpeechEnd(samples, { farewellOnly });
    },
    // Unconfirmed noise never changed conversation state; do not change it now.
    onVADMisfire: reset,
  };
}
