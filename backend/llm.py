import json
import re

import httpx
from pydantic import ValidationError

from .config import CHAT_MODEL, FEEDBACK_MODEL, OLLAMA_URL
from .prompts import CONVERSATION, FEEDBACK, OPENING, REWRITE
from .schemas import Feedback, ReportFeedback, Rewrites
from .spoken_text import display_text, is_contraction_only_change, spoken_text


class ModelError(Exception):
    pass


# UTF-8 byte budgets conservatively bound tokens, including escaped JSON, and
# leave room for instructions/schema plus 1,800 generated tokens in an 8K context.
INPUT_BYTES = 4800
PART_BYTES = 3600
REPORT_INPUT_BYTES = 2200
REPORT_PART_BYTES = 1800


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def size(value):
    return len(encoded(value).encode("utf-8"))


def text_parts(text, limit=PART_BYTES):
    """Split an oversized turn without losing characters or splitting Unicode."""
    while text:
        low, high = 1, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if size(text[:middle]) <= limit:
                low = middle
            else:
                high = middle - 1
        end = low
        if end < len(text):
            boundary = max(text.rfind(" ", 0, end), text.rfind("\n", 0, end))
            if boundary >= end // 2:
                end = boundary + 1
        yield text[:end]
        text = text[end:]


def feedback_batches(texts):
    batch = []
    for text in texts:
        for part in text_parts(text, REPORT_PART_BYTES):
            if batch and size(batch + [part]) > REPORT_INPUT_BYTES:
                yield batch
                batch = []
            batch.append(part)
    if batch:
        yield batch


def recent_messages(turns):
    recent = []
    for turn in reversed(turns):
        content = turn.text
        if turn.interrupted:
            content += "\n[Interrupted: the learner did not hear all of this reply.]"
        message = {"role": turn.role, "content": content}
        if size([message] + recent) > INPUT_BYTES:
            if not recent:
                message["content"] = "[Earlier text omitted from reply context.]\n" + list(text_parts(content))[-1]
                recent.insert(0, message)
            break
        recent.insert(0, message)
    return recent


def completed_content(data):
    content = data.get("message", {}).get("content", "").strip()
    if not data.get("done") or data.get("done_reason") != "stop" or not content:
        raise ModelError("Local AI returned an incomplete answer. Please retry.")
    return content


async def chat(messages, *, schema=None, retry_hint="", model=CHAT_MODEL, temperature=None):
    payload = {
        "model": model, "messages": messages, "stream": False,
        "think": False, "keep_alive": "10m",
        "options": {"num_ctx": 8192, "num_predict": 1800 if schema else 256,
                    "temperature": temperature if temperature is not None else (0.15 if schema else 0.6)},
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
    messages = [{"role": "system", "content": CONVERSATION}]
    messages += recent_messages(turns)
    if opening:
        messages.append({"role": "user", "content": OPENING})
    text = display_text(await chat(messages))
    if not spoken_text(text):
        raise ModelError("Local AI returned no speakable reply. Please retry.")
    return text


TIME_COMMA = re.compile(r"\b(last|next|this)\s*,\s*(week|month|year|weekend|night|morning|afternoon|evening)\b",
                        re.IGNORECASE)


def clean_punctuation(text):
    """Repair a comma the local model sometimes inserts inside time phrases."""
    return TIME_COMMA.sub(r"\1 \2", text)


def validate_feedback(raw, user_texts):
    """Ground every quote in the learner's words.

    An ungrounded quote is a fabrication and always fails. A finding whose
    suggestion repeats its quote, or differs only by optional contraction
    style, carries no advice: it is dropped instead of failing the whole
    report, so one weak item cannot lose the other findings.
    """
    feedback = Feedback.model_validate_json(raw)
    grounded = []
    for finding in feedback.findings:
        if not any(finding.quote in text for text in user_texts):
            raise ValueError("Feedback quoted words absent from the learner's turns.")
        if finding.quote.strip() == finding.suggestion.strip():
            # A no-op is weak advice, not a fabrication. Keep the useful items.
            continue
        if is_contraction_only_change(finding.quote, finding.suggestion):
            continue
        grounded.append(finding.model_copy(update={
            "suggestion": clean_punctuation(finding.suggestion),
            "explanation": clean_punctuation(finding.explanation),
        }))
    return feedback.model_copy(update={"findings": grounded})


def clean_summary(summary):
    """Keep model meta-commentary about rewriting out of the learner's report."""
    lowered = summary.lower()
    if any(phrase in lowered for phrase in ("rewrite", "original text", "review process")):
        return "Here are some useful changes to make your English sound more natural."
    return summary


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


async def rewrite_texts(user_texts):
    """Make a natural version first; it gives the review a concrete target."""
    messages = [{"role": "system", "content": REWRITE},
                {"role": "user", "content": encoded(user_texts)}]
    for attempt in range(2):
        try:
            raw = await chat(messages, schema=Rewrites.model_json_schema(), model=FEEDBACK_MODEL,
                             temperature=0.2,
                             retry_hint=("Previous output was invalid. Return one rewrite for every "
                                         "supplied message, in the same order." if attempt else ""))
            rewrites = Rewrites.model_validate_json(raw).rewrites
            if len(rewrites) != len(user_texts):
                raise ValueError("The rewrite count did not match the messages.")
            return [rewrite.strip() or text for rewrite, text in zip(rewrites, user_texts)]
        except (ValidationError, ValueError, ModelError):
            if attempt:
                # The compare pass can still find problems in the originals.
                return list(user_texts)
    return list(user_texts)


async def compare_feedback(user_texts, rewrites):
    messages = [{"role": "system", "content": FEEDBACK},
                {"role": "user", "content": encoded({"original": user_texts,
                                                     "natural_rewrite": rewrites})}]
    for attempt in range(2):
        try:
            raw = await chat(messages, schema=Feedback.model_json_schema(), model=FEEDBACK_MODEL,
                             temperature=0.1,
                             retry_hint=("Previous output was invalid. Return complete JSON and quote ONLY "
                                         "exact supplied user text." if attempt else ""))
            feedback = validate_feedback(raw, user_texts)
            return feedback.model_copy(update={"summary": clean_summary(feedback.summary)})
        except (ValidationError, ValueError, ModelError):
            if attempt:
                raise ModelError("Local AI could not produce a complete, grounded report. Please retry.")


async def review_batch(user_texts):
    rewrites = await rewrite_texts(user_texts)
    return await compare_feedback(user_texts, rewrites)


async def report(turns):
    user_texts = [turn.text for turn in turns if turn.role == "user"]
    if not user_texts:
        raise ModelError("There are no recognized user turns to review yet.")
    batches = list(feedback_batches(user_texts))
    findings, seen = [], set()
    first_summary = ""
    for batch in batches:
        feedback = await review_batch(batch)
        if not first_summary:
            first_summary = feedback.summary
        for finding in feedback.findings:
            key = (finding.category, finding.quote, finding.suggestion, finding.explanation)
            if key not in seen:
                findings.append(finding)
                seen.add(key)
    # Combine accepted findings without another model pass that could omit them.
    summary = first_summary if len(batches) == 1 else (
        f"I reviewed all {len(user_texts)} of your spoken turns. Here are useful wording suggestions from your conversation."
    )
    feedback = ReportFeedback(summary=summary, findings=findings)
    report_text = format_feedback(feedback)
    if len(report_text) > 100000:
        raise ModelError("The feedback report exceeds the local file limit. No partial report was marked complete; your transcript is still open.")
    return {**feedback.model_dump(), "report_text": report_text}
