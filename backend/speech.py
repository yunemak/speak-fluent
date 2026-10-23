import io
import wave

import numpy as np

from .config import WHISPER_PATH
from .voice import Voice

# Everyday phrases prime the recognizer without rewriting what the learner
# actually said. This one fixed repeated "doing well" mishearings ("Dean
# Well", "Dingwell") on fast and noisy speech, while tests confirmed that
# "doing good", a name followed by "well", and "not doing well" stay intact.
HOTWORDS = "I'm doing well, how are you?"


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
        durations = [max(segment.end - segment.start, 0.001) for segment in parts]
        no_speech = sum(duration * segment.no_speech_prob
                        for duration, segment in zip(durations, parts)) / sum(durations)
        return {"text": text, "no_speech_prob": round(float(no_speech), 3)}

    def synthesize(self, text):
        return self.voice.synthesize(text)
