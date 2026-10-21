import io
import wave

import numpy as np

from .config import VOICE_PATH, WHISPER_PATH
from .spoken_text import spoken_text


class Speech:
    def __init__(self):
        self.whisper = None
        self.voice = None

    def load_recognizer(self):
        if self.whisper is None:
            from faster_whisper import WhisperModel
            self.whisper = WhisperModel(str(WHISPER_PATH), device="cpu", compute_type="int8",
                                        cpu_threads=4, local_files_only=True)

    def load_voice(self):
        if self.voice is None:
            from piper import PiperVoice
            self.voice = PiperVoice.load(str(VOICE_PATH))

    def transcribe(self, audio):
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Use mono PCM16 WAV audio at 16 kHz.")
            frames = wav.readframes(wav.getnframes())
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if len(samples) < 1600 or np.max(np.abs(samples), initial=0) < 0.002:
            return ""
        self.load_recognizer()
        segments, _ = self.whisper.transcribe(samples, language="en", beam_size=5,
                                              condition_on_previous_text=False)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def synthesize(self, text):
        text = spoken_text(text)
        if not text:
            raise ValueError("No speakable text remains.")
        self.load_voice()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            self.voice.synthesize_wav(text, wav)
        return buffer.getvalue()
