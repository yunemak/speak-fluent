import asyncio
import json
from uuid import uuid4

import pytest

from backend import llm
from backend.schemas import Turn
from backend.spoken_text import display_text, spoken_text
from backend.speech import Speech


def finding(quote="Yesterday I go to the park."):
    return {"summary": "A useful past-tense change.", "findings": [{
        "category": "grammar", "quote": quote,
        "suggestion": "Yesterday I went to the park.",
        "explanation": "Use the past tense for yesterday.",
    }]}


def test_grounded_correction_and_shared_report_text():
    feedback = llm.validate_feedback(json.dumps(finding()), ["Yesterday I go to the park."])
    text = llm.format_feedback(feedback)
    assert "Yesterday I go to the park." in text
    assert "Yesterday I went to the park." in text


def test_assistant_or_invented_quote_rejected():
    with pytest.raises(ValueError):
        llm.validate_feedback(json.dumps(finding()), ["I like swimming."])


def test_clean_sentence_does_not_require_a_finding():
    feedback = llm.validate_feedback('{"summary":"Nice practice.","findings":[]}', ["I like swimming."])
    assert "No clear wording issues" in llm.format_feedback(feedback)


@pytest.mark.parametrize("data", [
    {"done": False, "message": {"content": "unfinished"}},
    {"done": True, "done_reason": "length", "message": {"content": "partial"}},
    {"done": True, "done_reason": "stop", "message": {"content": " "}},
])
def test_incomplete_output_is_never_a_success(data):
    with pytest.raises(llm.ModelError):
        llm.completed_content(data)


def test_report_retries_grounding_once_and_fails_without_fake_report(monkeypatch):
    calls = []

    async def chat(*args, **kwargs):
        calls.append(kwargs)
        return json.dumps(finding())

    monkeypatch.setattr(llm, "chat", chat)
    turns = [Turn(id=uuid4(), role="user", text="I enjoy reading.")]
    with pytest.raises(llm.ModelError):
        asyncio.run(llm.report(turns))
    assert len(calls) == 2
    assert calls[-1]["retry_hint"]


def test_report_retries_truncated_output(monkeypatch):
    calls = []

    async def chat(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise llm.ModelError("truncated")
        return json.dumps(finding())

    monkeypatch.setattr(llm, "chat", chat)
    result = asyncio.run(llm.report([Turn(id=uuid4(), role="user", text="Yesterday I go to the park.")]))
    assert len(calls) == 2
    assert "went" in result["report_text"]


def test_reply_keeps_faces_for_display_but_synthesis_skips_them(monkeypatch):
    async def chat(*args, **kwargs):
        return "Congratulations! 🎉 How do you feel? :)"

    monkeypatch.setattr(llm, "chat", chat)
    text = asyncio.run(llm.reply([], True))
    assert text == "Congratulations! 🎉 How do you feel? :)"
    spoken = []

    class RecordingVoice:
        def synthesize_wav(self, text, wav):
            spoken.append(text)
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0")

    speech = Speech()
    speech.voice = RecordingVoice()
    assert speech.synthesize(text).startswith(b"RIFF")
    assert spoken == ["Congratulations! How do you feel?"]


def test_report_keeps_display_faces_and_grounded_quotes_but_speaks_only_words():
    data = finding()
    data["summary"] = "I'm happy for you! 😊 :)"
    data["findings"][0]["explanation"] += " 👍🏽"
    feedback = llm.validate_feedback(json.dumps(data), ["Yesterday I go to the park."])
    text = llm.format_feedback(feedback)
    assert text.startswith("I'm happy for you! 😊 :)\n\nGrammar:")
    assert text.endswith("Use the past tense for yesterday.")
    assert spoken_text(text).startswith("I'm happy for you!\n\nGrammar:")
    assert spoken_text(text).endswith("Use the past tense for yesterday.")
    assert "Yesterday I go to the park." in text
    assert "Yesterday I went to the park." in text


def test_spoken_cleanup_preserves_words_punctuation_and_paragraphs():
    assert spoken_text("Café at 8:30 costs $5.50 (really!).\n\nYou’re welcome — keep going!") == (
        "Café at 8:30 costs $5.50 (really!).\n\nYou’re welcome — keep going!")
    assert spoken_text("Good job :-) 😉 👩🏽‍💻 🇬🇧 1️⃣!") == "Good job!"


def test_emoji_only_reply_is_not_a_success(monkeypatch):
    async def chat(*args, **kwargs):
        return "😊 :)"

    monkeypatch.setattr(llm, "chat", chat)
    with pytest.raises(llm.ModelError, match="no speakable reply"):
        asyncio.run(llm.reply([], True))


@pytest.mark.parametrize("text,expected", [
    ("Hi! How's your day? 😊", "Hi! How's your day?"),
    ("That sounds nice! Do you walk there often? 🌳", "That sounds nice! Do you walk there often?"),
    ("I'm happy to help. 😊", "I'm happy to help."),
    ("Congratulations on passing your exam! 🎉", "Congratulations on passing your exam! 🎉"),
    ("I'm sorry to hear that. 😔", "I'm sorry to hear that. 😔"),
])
def test_only_clear_emotional_reactions_keep_decorative_emojis(text, expected):
    assert display_text(text) == expected
