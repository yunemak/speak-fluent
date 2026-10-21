"""Render the same sentence with each local voice so they can be compared.

Usage: .venv/bin/python scripts/compare_voices.py
Writes models/voice-samples/<engine>-<voice>.wav and prints the paths to play.
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.voice import Voice, wav_bytes

MODELS = Path(__file__).resolve().parent.parent / "models"
SAMPLES = MODELS / "voice-samples"
TEXT = "Hi there! How was your day? Tell me about something you enjoyed today."


def save(path, samples, rate):
    audio = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
    path.write_bytes(wav_bytes(audio, rate))
    return path


def main():
    voice = Voice()
    kokoro_ready, piper_ready = voice.available()
    if not (kokoro_ready or piper_ready):
        raise SystemExit("No local voices found. Run scripts/download_models.py first.")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    if kokoro_ready:
        voice.load()
        for name in voice.voices():
            voice.voice = name
            samples, rate = voice.kokoro.create(TEXT, voice=name, speed=1.0, lang="en-us")
            print(save(SAMPLES / f"kokoro-{name}.wav", samples, rate))
    if piper_ready:
        from piper import PiperVoice
        for path in sorted((MODELS / "piper").glob("*.onnx")):
            piper = PiperVoice.load(str(path))
            buffer = wave.open(str(SAMPLES / f"piper-{path.stem}.wav"), "wb")
            with buffer:
                piper.synthesize_wav(TEXT, buffer)
            print(SAMPLES / f"piper-{path.stem}.wav")


if __name__ == "__main__":
    main()
