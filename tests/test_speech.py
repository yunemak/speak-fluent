import io
import wave

import numpy as np

from backend.speech import HOTWORDS, Speech, correct_transcript, restore_capitalization


class Segment:
    text = "I'm doing well, how are you?"

    def __init__(self):
        self.start = 0.0
        self.end = 1.0
        self.no_speech_prob = 0.01


def wav_bytes(samples):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return output.getvalue()


def test_recognition_primes_common_phrases_and_keeps_the_audio():
    speech = Speech()
    captured = {}

    class FakeWhisper:
        def transcribe(self, samples, **options):
            captured["samples"] = samples
            captured.update(options)
            return [Segment()], None

    speech.whisper = FakeWhisper()
    samples = np.sin(2 * np.pi * 220 * np.arange(3200) / 16000) * 0.3

    result = speech.transcribe(wav_bytes(samples))

    assert captured["hotwords"] == HOTWORDS
    assert captured["language"] == "en"
    assert np.isclose(float(np.max(np.abs(captured["samples"]))), 0.9, atol=1e-3)
    assert result == {"text": "I'm doing well, how are you?", "no_speech_prob": 0.01}


def test_self_correction_repairs_misheard_letter_c_without_rewriting_literacy():
    assert correct_transcript("I meant the literacy on computer science.") == \
        "I meant the letter C on computer science."
    assert correct_transcript("I mean the literacy in programming.") == \
        "I mean the letter C in programming."
    # Genuine literacy, other subjects, and missing self-correction stay intact.
    assert correct_transcript("Literacy is important in computer science.") == \
        "Literacy is important in computer science."
    assert correct_transcript("I meant the literacy rate in computer science.") == \
        "I meant the literacy rate in computer science."
    assert correct_transcript("The literacy on computer science is low.") == \
        "The literacy on computer science is low."


def test_transcript_capitalization_is_restored():
    assert restore_capitalization("yesterday i go to the park. i'm fine!") == \
        "Yesterday I go to the park. I'm fine!"
    assert restore_capitalization("the sea was calm, i like sea projects") == \
        "The sea was calm, I like sea projects"
