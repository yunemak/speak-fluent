"""Local voice output: Kokoro when available, Piper as the fallback.

Both engines are fully local. Kokoro sounds far more natural; Piper is kept
because it is small and already installed, so a missing Kokoro download still
leaves the app usable.
"""
import io
import wave

import numpy as np

from .config import KOKORO_INT8_MODEL, KOKORO_MODEL, KOKORO_VOICES, PIPER_VOICE_PATH, VOICE_NAME
from .spoken_text import spoken_text


class Voice:
    """Loads one engine lazily and produces 16-bit mono WAV bytes."""

    def __init__(self):
        self.kokoro = None
        self.piper = None
        self.engine = None
        self.voice = VOICE_NAME

    def _kokoro_model(self):
        for path in (KOKORO_MODEL, KOKORO_INT8_MODEL):
            if path.is_file():
                return path
        return None

    def available(self):
        return self._kokoro_model() is not None and KOKORO_VOICES.is_file(), PIPER_VOICE_PATH.is_file()

    def load(self):
        if self.engine:
            return
        model = self._kokoro_model()
        if model is not None and KOKORO_VOICES.is_file():
            from kokoro_onnx import Kokoro
            self.kokoro = Kokoro(str(model), str(KOKORO_VOICES))
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
        model = self._kokoro_model()
        if model is None or not KOKORO_VOICES.is_file():
            return []
        from kokoro_onnx import Kokoro
        if self.kokoro is None:
            self.kokoro = Kokoro(str(model), str(KOKORO_VOICES))
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
        samples = self._master(np.asarray(samples, dtype=np.float32), rate)
        audio = (samples * 32767).astype("<i2")
        return wav_bytes(audio, rate)

    @staticmethod
    def _low_pass(samples, rate, cutoff=9000.0, taps=127):
        """Remove Kokoro's narrow high-frequency hiss without dulling speech.

        The voice carries an unusually hot 9-12 kHz band that is heard as
        static on headphones. A linear-phase low-pass keeps the natural 4-9 kHz
        sibilance and removes the noisy top octave above 9 kHz.
        """
        cutoff = min(cutoff, rate * 0.45)
        if samples.size < taps or cutoff >= rate / 2:
            return samples
        half = (taps - 1) / 2
        positions = np.arange(taps) - half
        kernel = np.sinc((cutoff / (rate / 2)) * positions) * np.hamming(taps)
        kernel /= kernel.sum()
        padded = np.pad(samples, (taps // 2, taps // 2), mode="edge")
        return np.convolve(padded, kernel, mode="valid").astype(np.float32)

    @staticmethod
    def _master(samples, rate):
        """Filter hiss, remove DC, use the headroom, and fade edge clicks.

        Kokoro's raw output peaks around half scale and has a hot high band.
        Mastering a clean 0.9 peak keeps the voice clear without making the
        learner turn the speaker up into playback noise.
        """
        if samples.size == 0:
            return samples
        samples = Voice._low_pass(samples, rate)
        samples = samples - float(samples.mean())
        peak = float(np.max(np.abs(samples)))
        if peak > 0:
            samples = samples * (0.9 / peak)
        fade = min(int(rate * 0.008), samples.size // 2)
        if fade > 0:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            samples[:fade] *= ramp
            samples[-fade:] *= ramp[::-1]
        return np.clip(samples, -1.0, 1.0)

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
