import json

import httpx
from pydantic import ValidationError

from .config import CHAT_MODEL, OLLAMA_URL
from .prompts import CONVERSATION, FEEDBACK, OPENING
from .schemas import Feedback
from .spoken_text import display_text, spoken_text


class ModelError(Exception):
    pass


def completed_content(data):
    content = data.get("message", {}).get("content", "").strip()
    if not data.get("done") or data.get("done_reason") != "stop" or not content:
        raise ModelError("Local AI returned an incomplete answer. Please retry.")
    return content


async def chat(messages, *, schema=None, retry_hint=""):
    payload = {
        "model": CHAT_MODEL, "messages": messages, "stream": False,
        "think": False, "keep_alive": "10m",
        "options": {"num_ctx": 8192, "num_predict": 1800 if schema else 256,
                    "temperature": 0.15 if schema else 0.6},
    }
    if schema:
        payload["format"] = schema
    if retry_hint:
        payload["messages"] = messages + [{"role": "system", "content": retry_hint}]
    try:
        async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
            result = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            result.raise_for_status()
            return completed_content(result.json())
    except (httpx.HTTPError, ValueError) as error:
        raise ModelError("Local AI could not finish. Check that Ollama is running, then retry.") from error


async def reply(turns, opening):
    # Bound normal conversation context while preserving the full UI transcript.
    recent, used = [], 0
    for turn in reversed(turns):
        if used + len(turn.text) > 14000:
            break
        content = turn.text
        if turn.interrupted:
            content += "\n[Interrupted: the learner did not hear all of this reply.]"
        recent.append({"role": turn.role, "content": content})
        used += len(content)
    messages = [{"role": "system", "content": CONVERSATION}]
    messages += list(reversed(recent))
    if opening:
        messages.append({"role": "user", "content": OPENING})
    text = display_text(await chat(messages))
    if not spoken_text(text):
        raise ModelError("Local AI returned no speakable reply. Please retry.")
    return text


def validate_feedback(raw, user_texts):
    feedback = Feedback.model_validate_json(raw)
    for finding in feedback.findings:
        if not any(finding.quote in text for text in user_texts):
            raise ValueError("Feedback quoted words absent from the learner's turns.")
        if finding.quote.strip() == finding.suggestion.strip():
            raise ValueError("Feedback suggested no change.")
    return feedback


def format_feedback(feedback):
    if not feedback.findings:
        return "No clear wording issues were found in this conversation. Keep practicing!"
    paragraphs = [display_text(feedback.summary)]
    for finding in feedback.findings:
        paragraphs.append(
            f'{finding.category.capitalize()}: You said, “{finding.quote}” '
            f'Try, “{spoken_text(finding.suggestion)}” {spoken_text(finding.explanation)}'
        )
    return "\n\n".join(paragraphs)


async def report(turns):
    user_texts = [turn.text for turn in turns if turn.role == "user"]
    # Slice 3 adds all-turn batching. Until then explicitly reject, never omit.
    if sum(len(text) for text in user_texts) > 14000:
        raise ModelError("This first build supports short reports. Your transcript is still on screen; longer-session review is planned in slice 3.")
    messages = [{"role": "system", "content": FEEDBACK},
                {"role": "user", "content": json.dumps(user_texts, ensure_ascii=False)}]
    for attempt in range(2):
        try:
            raw = await chat(messages, schema=Feedback.model_json_schema(), retry_hint=(
                "Previous output was invalid. Return complete JSON and quote ONLY exact supplied user text."
                if attempt else ""))
            feedback = validate_feedback(raw, user_texts)
            return {**feedback.model_dump(), "report_text": format_feedback(feedback)}
        except (ValidationError, ValueError, ModelError):
            if attempt:
                raise ModelError("Local AI could not produce a complete, grounded report. Please retry.")
