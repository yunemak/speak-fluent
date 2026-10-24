"""Check the actual local recognizer with synthetic minimal-pair examples.

Run: .venv/bin/python scripts/verify_recognition.py
Optional: --wav /path/to/recording.wav (mono PCM16, 16 kHz)
Synthetic results do not establish accuracy on a learner's microphone/accent.
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import WHISPER_PATH
from backend.speech import Speech
from scripts.verify_speech import microphone_wav


# Include genuine uses of the confusing words: a blanket substitution of
# "taught" or "eats" would corrupt them. Keep a learner grammar error too.
CASES = [
    ("If you put it on the water, that approximately its mass.", "its mass"),
    ("Probably they thought a lot of n-gen, you know, six-gen.", "they thought"),
    ("They taught a lot of students about engines.", "they taught"),
    ("The animal eats grass. Its mass is about ten kilograms.", "eats grass its mass"),
    ("Yesterday I go to the park.", "yesterday i go to the park"),
    ("I'm doing well, how are you?", "i'm doing well"),
    ("I meant the letter C on computer science.", "letter c"),
    ("I was studying some C projects.", "c projects"),
    ("I meant the literacy on computer science.", "letter c"),
    # The technical priming must not swallow ordinary words with the same sound.
    ("The sea was calm. I like sea projects.", "sea projects"),
    ("I like to see the sea.", "see the sea"),
    ("I need to see the project.", "see the project"),
    ("Literacy is important in computer science.", "literacy is important"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path, help="Transcribe an existing microphone recording instead of synthetic examples.")
    args = parser.parse_args()
    speech = Speech()
    speech.load_recognizer()
    print(f"Recognizer: {WHISPER_PATH.name}")

    def recognize(audio):
        started = time.monotonic()
        result = speech.transcribe(audio)
        print(f"{time.monotonic() - started:.2f}s: {result['text']}")
        return result["text"]

    if args.wav:
        recognize(args.wav.read_bytes())
        return

    # Fixed voice makes this smoke check independent of the user's TTS choice.
    speech.voice.voice = "af_heart"
    failures = []
    for phrase, expected in CASES:
        text = recognize(microphone_wav(speech.synthesize(phrase)))
        normalized = re.sub(r"[^a-z0-9' ]", " ", text.lower())
        normalized = " ".join(normalized.split())
        if expected not in normalized:
            failures.append(f"Expected {expected!r} in {text!r}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("Synthetic recognition checks passed. Verify microphone recordings separately.")


if __name__ == "__main__":
    main()
