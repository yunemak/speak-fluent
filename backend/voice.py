"""Local voice output: Kokoro when available, Piper as the fallback.

Both engines are fully local. Kokoro sounds far more natural; Piper is kept
because it is small and already installed, so a missing Kokoro download still
leaves the app usable.
"""
import io
import wave

import numpy as np

from .config import KOKORO_MODEL, KOKORO_VOICES, PIPER_VOICE_PATH, VOICE_NAME
from .spoken_text import spoken_text


class Voice:
    """Loads one engine lazily and produces 16-bit mono WAV bytes."""

    def __init__(self):
        self.kokoro = None
        self.piper = None
        self.engine = None
        self.voice = VOICE_NAME

    def available(self):
        return KOKORO_MODEL.is_file() and KOKORO_VOICES.is_file(), PIPER_VOICE_PATH.is_file()

    def load(self):
        if self.engine:
            return
        if KOKORO_MODEL.is_file() and KOKORO_VOICES.is_file():
            from kokoro_onnx import Kokoro
            self.kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
            # Validate the name now: a typo in SPEAK_FLUENT_VOICE would
            # otherwise only fail the first spoken reply mid-practice.
            names = self.kokoro.get_voices()
            if self.voice not in names:
                raise ValueError(
                    f"Voice {self.voice!r} is not in the local voice pack. "
                    f"Unset SPEAK_FLUENT_VOICE for the default or pick one from "
                    f"scripts/compare_voices.py (for example af_heart, af_nicole, am_michael).")
            self.engine = "kokoro"
            return
        from piper import PiperVoice
        self.piper = PiperVoice.load(str(PIPER_VOICE_PATH))
        self.engine = "piper"

    def voices(self):
        if not KOKORO_MODEL.is_file() or not KOKORO_VOICES.is_file():
            return []
        from kokoro_onnx import Kokoro
        if self.kokoro is None:
            self.kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
        return self.kokoro.get_voices()

    def synthesize(self, text):
        text = spoken_text(text)
        if not text:
            raise ValueError("No speakable text remains.")
        self.load()
        if self.engine == "kokoro":
            return self._kokoro(text)
        return self._piper(text)

    def _kokoro(self, text):
        samples, rate = self.kokoro.create(text, voice=self.voice, speed=1.0, lang="en-us")
        audio = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
        return wav_bytes(audio, rate)

    def _piper(self, text):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            self.piper.synthesize_wav(text, wav)
        return buffer.getvalue()


def wav_bytes(samples, rate):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()
