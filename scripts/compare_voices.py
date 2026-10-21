"""Render the same sentence with each local Piper voice for a listening test.

Usage: .venv/bin/python scripts/compare_voices.py
Writes models/voice-samples/<voice>.wav and prints the paths to play.
"""
import wave
from pathlib import Path

from piper import PiperVoice

MODELS = Path(__file__).resolve().parent.parent / "models" / "piper"
SAMPLES = MODELS.parent / "voice-samples"
TEXT = "Hi there! How was your day? Tell me about something you enjoyed today."


def main():
    voices = sorted(path for path in MODELS.glob("*.onnx"))
    if not voices:
        raise SystemExit("No local voices found. Run scripts/download_models.py first.")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for path in voices:
        target = SAMPLES / f"{path.stem}.wav"
        voice = PiperVoice.load(str(path))
        with wave.open(str(target), "wb") as wav:
            voice.synthesize_wav(TEXT, wav)
        print(target)


if __name__ == "__main__":
    main()
