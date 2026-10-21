import wave

import pytest

from backend.spoken_text import is_contraction_only_change
from backend.voice import Voice, wav_bytes


def test_kokoro_is_preferred_and_piper_remains_a_fallback(monkeypatch):
    voice = Voice()
    voice.load()
    assert voice.engine in {"kokoro", "piper"}
    if voice.engine == "kokoro":
        assert voice.available()[0] is True


def test_synthesis_returns_playable_wav_audio(monkeypatch):
    voice = Voice()
    audio = voice.synthesize("Hello there, this is a short test.")
    assert audio[:4] == b"RIFF"
    with wave.open(__import__("io").BytesIO(audio), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() in {16000, 22050, 24000}
        assert wav.getnframes() > 1600


def test_emoji_only_text_is_refused_before_synthesis():
    voice = Voice()
    with pytest.raises(ValueError):
        voice.synthesize("😊")


def test_wav_bytes_helper_writes_pcm16():
    import numpy as np
    samples = np.zeros(1000, dtype="<i2")
    audio = wav_bytes(samples, 24000)
    with wave.open(__import__("io").BytesIO(audio), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnframes() == 1000


@pytest.mark.parametrize("quote,suggestion", [
    ("I am doing well", "I'm doing well"),
    ("I do not know", "I don't know"),
    ("It is fine", "It's fine"),
    ("I will call you", "I'll call you"),
    ("She cannot come", "She can't come"),
])
def test_contraction_only_changes_are_optional_style(quote, suggestion):
    assert is_contraction_only_change(quote, suggestion)


@pytest.mark.parametrize("quote,suggestion", [
    ("Yesterday I go to the park.", "Yesterday I went to the park."),
    ("She have two cats.", "She has two cats."),
])
def test_real_grammar_changes_are_not_treated_as_contractions(quote, suggestion):
    assert not is_contraction_only_change(quote, suggestion)
