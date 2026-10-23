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


def test_a_finding_without_a_real_change_is_dropped_not_fatal():
    raw = json.dumps({"summary": "One clear fix.", "findings": [
        {"category": "grammar", "quote": "I like swimming.", "suggestion": "I like swimming.",
         "explanation": "No change."},
        {"category": "grammar", "quote": "Yesterday I go to the park.", "suggestion": "Yesterday I went to the park.",
         "explanation": "Use the past tense."},
    ]})
    feedback = llm.validate_feedback(raw, ["I like swimming.", "Yesterday I go to the park."])
    assert len(feedback.findings) == 1
    assert feedback.findings[0].suggestion == "Yesterday I went to the park."


def test_a_comma_inside_a_time_expression_is_repaired():
    raw = json.dumps({"summary": "One clear fix.", "findings": [{
        "category": "grammar", "quote": "I have went to many meetings last week.",
        "suggestion": "I went to many meetings last, week.",
        "explanation": "Use the simple past with 'last, week'.",
    }]})
    feedback = llm.validate_feedback(raw, ["I have went to many meetings last week."])
    assert feedback.findings[0].suggestion == "I went to many meetings last week."
    assert feedback.findings[0].explanation == "Use the simple past with 'last week'."


def test_a_comma_inside_goodbye_is_repaired():
    raw = json.dumps({"summary": "One clear fix.", "findings": [{
        "category": "grammar", "quote": "I have to go. Goodbye.",
        "suggestion": "I have to go now. Good,bye.",
        "explanation": "'Good,bye' is the natural closing.",
    }]})
    feedback = llm.validate_feedback(raw, ["I have to go. Goodbye."])
    assert feedback.findings[0].suggestion == "I have to go now. Goodbye."
    assert feedback.findings[0].explanation == "'Goodbye' is the natural closing."


def test_punctuation_cleanup_cannot_turn_a_no_op_into_a_finding():
    raw = json.dumps({"summary": "One clear fix.", "findings": [{
        "category": "grammar", "quote": "I have to go. Goodbye.",
        "suggestion": "I have to go. Good,bye.",
        "explanation": "The same closing.",
    }]})
    feedback = llm.validate_feedback(raw, ["I have to go. Goodbye."])
    assert feedback.findings == []


def test_a_contraction_suggestion_is_never_reported():
    raw = json.dumps({"summary": "All good.", "findings": [{
        "category": "grammar", "quote": "I am doing well", "suggestion": "I'm doing well",
        "explanation": "Use the contraction in informal speech.",
    }]})
    feedback = llm.validate_feedback(raw, ["I am doing well"])
    assert feedback.findings == []
    assert "No clear wording issues" in llm.format_feedback(feedback)


@pytest.mark.parametrize("data", [
    {"done": False, "message": {"content": "unfinished"}},
    {"done": True, "done_reason": "length", "message": {"content": "partial"}},
    {"done": True, "done_reason": "stop", "message": {"content": " "}},
])
def test_incomplete_output_is_never_a_success(data):
    with pytest.raises(llm.ModelError):
        llm.completed_content(data)


def rewrite_reply(messages):
    return json.dumps({"rewrites": json.loads(messages[-1]["content"])})


def test_report_retries_grounding_once_and_fails_without_fake_report(monkeypatch):
    calls = []

    async def chat(messages, **kwargs):
        if kwargs["schema"]["title"] == "Rewrites":
            return rewrite_reply(messages)
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

    async def chat(messages, **kwargs):
        if kwargs["schema"]["title"] == "Rewrites":
            return rewrite_reply(messages)
        calls.append(kwargs)
        if len(calls) == 1:
            raise llm.ModelError("truncated")
        return json.dumps(finding())

    monkeypatch.setattr(llm, "chat", chat)
    result = asyncio.run(llm.report([Turn(id=uuid4(), role="user", text="Yesterday I go to the park.")]))
    assert len(calls) == 2
    assert "went" in result["report_text"]


def test_report_compares_originals_when_rewrite_fails(monkeypatch):
    compared = []

    async def chat(messages, **kwargs):
        if kwargs["schema"]["title"] == "Rewrites":
            raise llm.ModelError("truncated")
        compared.append(json.loads(messages[-1]["content"]))
        return json.dumps(finding())

    monkeypatch.setattr(llm, "chat", chat)
    result = asyncio.run(llm.report([Turn(id=uuid4(), role="user", text="Yesterday I go to the park.")]))
    assert compared == [{"original": ["Yesterday I go to the park."],
                         "natural_rewrite": ["Yesterday I go to the park."]}]
    assert "went" in result["report_text"]


def test_reply_keeps_faces_for_display_but_synthesis_skips_them(monkeypatch):
    async def chat(*args, **kwargs):
        return "Congratulations! 🎉 How do you feel? :)"

    monkeypatch.setattr(llm, "chat", chat)
    text = asyncio.run(llm.reply([], True))
    assert text == "Congratulations! 🎉 How do you feel? :)"

    class RecordingVoice:
        def synthesize_wav(self, text, wav):
            spoken.append(text)
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0")

    speech = Speech()

    class RecordingVoice:
        def __init__(self):
            self.spoken = []

        def synthesize(self, text):
            self.spoken.append(spoken_text(text))
            return b"RIFF" + b"\0" * 40

    recording = RecordingVoice()
    speech.voice = recording
    assert speech.synthesize(text).startswith(b"RIFF")
    assert recording.spoken == ["Congratulations! How do you feel?"]


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


def test_long_report_reviews_every_user_character_and_keeps_all_batch_findings(monkeypatch):
    turns = [Turn(id=uuid4(), role="user", text=f"Turn {i}: Yesterday I go to the park. " + "I enjoy walking. " * 160)
             for i in range(24)]
    seen, quotes = [], []

    async def chat(messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        if kwargs["schema"]["title"] == "Rewrites":
            return json.dumps({"rewrites": data})
        batch = data["original"]
        assert llm.size(batch) <= llm.REPORT_INPUT_BYTES
        seen.extend(batch)
        quote = batch[0][:40]
        quotes.append(quote)
        return json.dumps(finding(quote))

    monkeypatch.setattr(llm, "chat", chat)
    result = asyncio.run(llm.report(turns + [Turn(id=uuid4(), role="assistant", text="Not learner wording.")]))
    assert "".join(seen) == "".join(turn.text for turn in turns)
    assert len(seen) > 1
    assert len(result["findings"]) == len(set(quotes))
    assert len(result["findings"]) > 12
    assert all(quote in result["report_text"] for quote in quotes)


def test_large_unicode_turn_splits_without_omitting_or_corrupting_text():
    original = ('I said “café” 😊.\n' + '\\"') * 1500
    batches = list(llm.feedback_batches([original]))
    assert len(batches) > 1
    assert all(llm.size(batch) <= llm.REPORT_INPUT_BYTES for batch in batches)
    assert "".join(part for batch in batches for part in batch) == original


def test_failure_in_later_batch_never_returns_partial_success(monkeypatch):
    feedback_calls = 0

    async def chat(messages, **kwargs):
        nonlocal feedback_calls
        data = json.loads(messages[-1]["content"])
        if kwargs["schema"]["title"] == "Rewrites":
            return json.dumps({"rewrites": data})
        feedback_calls += 1
        if feedback_calls == 1:
            return '{"summary":"Clear wording.","findings":[]}'
        raise llm.ModelError("Incomplete output")

    monkeypatch.setattr(llm, "chat", chat)
    turns = [Turn(id=uuid4(), role="user", text="I like reading. " * 1000)]
    with pytest.raises(llm.ModelError):
        asyncio.run(llm.report(turns))
    assert feedback_calls == 3


def test_bounded_reply_context_keeps_end_of_newest_oversized_turn():
    latest = Turn(id=uuid4(), role="user", text="A long story. " * 1500 + "My final question is about swimming.")
    messages = llm.recent_messages([Turn(id=uuid4(), role="assistant", text="Old answer."), latest])
    assert llm.size(messages) <= llm.INPUT_BYTES
    assert messages[-1]["content"].endswith("My final question is about swimming.")
    assert "Earlier text omitted" in messages[-1]["content"]
