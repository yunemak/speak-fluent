import io
import re
import wave

import numpy as np

from .config import WHISPER_PATH
from .voice import Voice

# Everyday phrases prime the recognizer without rewriting what the learner
# actually said. "doing well" fixed repeated mishearings ("Dean Well",
# "Dingwell") on fast and noisy speech. The technical terms keep the spoken
# letter "C" from becoming "sea"/"see" during computer-science turns while
# preserving ordinary uses of "sea" and "see" in the synthetic checks.
HOTWORDS = "I'm doing well, how are you? letter C, computer science"

# A self-correction makes the intended word explicit even when its sound is
# ambiguous. Keep this narrow so genuine uses of "literacy" stay untouched.
SELF_CORRECTIONS = (
    (re.compile(r"\b(I (?:meant|mean)) the literacy(?=\s+(?:on|in|of)\s+"
                r"(?:computer science|programming|computing)\b)", re.IGNORECASE),
     r"\1 the letter C"),
)


def correct_transcript(text):
    for pattern, replacement in SELF_CORRECTIONS:
        text = pattern.sub(replacement, text)
    return text


def restore_capitalization(text):
    """The technical hotwords can make Whisper drop sentence casing."""
    text = re.sub(r"(^|[.!?]\s+)([a-z])",
                  lambda match: match.group(1) + match.group(2).upper(), text)
    return re.sub(r"\bi(?=\b|['’])", "I", text)


class Speech:
    def __init__(self):
        self.whisper = None
        self.voice = Voice()

    def load_recognizer(self):
        if self.whisper is None:
            from faster_whisper import WhisperModel
            self.whisper = WhisperModel(str(WHISPER_PATH), device="cpu", compute_type="int8",
                                        cpu_threads=4, local_files_only=True)

    def transcribe(self, audio):
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Use mono PCM16 WAV audio at 16 kHz.")
            frames = wav.readframes(wav.getnframes())
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        peak = float(np.max(np.abs(samples), initial=0))
        if len(samples) < 1600 or peak < 0.002:
            return {"text": "", "no_speech_prob": 1.0}
        if peak < 0.9:
            # A quiet microphone should not cost recognition accuracy.
            samples = samples * (0.9 / peak)
        self.load_recognizer()
        segments, _ = self.whisper.transcribe(samples, language="en", beam_size=5,
                                              condition_on_previous_text=False,
                                              hotwords=HOTWORDS)
        parts = list(segments)
        text = " ".join(segment.text.strip() for segment in parts).strip()
        if not text:
            return {"text": "", "no_speech_prob": 1.0}
        text = correct_transcript(text)
        text = restore_capitalization(text)
        durations = [max(segment.end - segment.start, 0.001) for segment in parts]
        no_speech = sum(duration * segment.no_speech_prob
                        for duration, segment in zip(durations, parts)) / sum(durations)
        return {"text": text, "no_speech_prob": round(float(no_speech), 3)}

    def synthesize(self, text):
        return self.voice.synthesize(text)
