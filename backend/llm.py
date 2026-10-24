import json
import re

import httpx
from pydantic import ValidationError

from .config import CHAT_MODEL, FEEDBACK_MODEL, OLLAMA_URL
from .prompts import CONVERSATION, FEEDBACK, OPENING, REWRITE, TITLE
from .schemas import ConversationTitle, Feedback, ReportFeedback, Rewrites
from .spoken_text import display_text, is_contraction_only_change, spoken_text


class ModelError(Exception):
    pass


class UngroundedFeedback(ValueError):
    """The model returned no finding that quoted the learner's exact words."""


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


def clean_title(title):
    title = re.sub(r"^title\s*:\s*", "", title.strip(), flags=re.IGNORECASE)
    title = title.strip().strip("\"'“”‘’").strip()
    title = title.rstrip(".").strip("\"'“”‘’").strip()
    title = re.sub(r"\s+", " ", title)[:80].rstrip()
    if title.casefold() in {"goodbye chat", "goodbyes chat", "greeting chat", "hello chat"}:
        return "Everyday Greetings Chat"
    for short, proper in {"Sql": "SQL", "Ui": "UI", "Stp": "STP", "Api": "API",
                          "Html": "HTML", "Css": "CSS", "Http": "HTTP", "Tcp": "TCP",
                          "Dns": "DNS", "Cpu": "CPU", "Gpu": "GPU"}.items():
        title = re.sub(rf"\b{short}\b", proper, title)
    return title


async def title(turns):
    """A short topic title from the learner's messages; empty means use the date."""
    texts = [turn.text if hasattr(turn, "text") else turn["text"]
             for turn in turns
             if (turn.role if hasattr(turn, "role") else turn["role"]) == "user" and
             (turn.text if hasattr(turn, "text") else turn["text"]).strip()]
    if not texts:
        return ""
    # Topic comes from the conversation as a whole; keep the prompt bounded.
    content = encoded({"conversation": texts})
    if len(content.encode("utf-8")) > INPUT_BYTES:
        joined = "\n".join(texts)
        content = encoded({"conversation": list(text_parts(joined, INPUT_BYTES))})
    messages = [{"role": "system", "content": TITLE},
                {"role": "user", "content": content}]
    for attempt in range(2):
        try:
            raw = await chat(messages, schema=ConversationTitle.model_json_schema(),
                             temperature=0.2,
                             retry_hint=("Previous output was invalid. Return one short title "
                                         "as JSON." if attempt else ""))
            title_text = clean_title(ConversationTitle.model_validate_json(raw).title)
            if title_text:
                return title_text
            raise ValueError("Empty title.")
        except (ValidationError, ValueError, ModelError):
            if attempt:
                return ""
    return ""


TIME_COMMA = re.compile(r"\b(last|next|this)\s*,\s*(week|month|year|weekend|night|morning|afternoon|evening)\b",
                        re.IGNORECASE)
GOODBYE_COMMA = re.compile(r"\bgood\s*,\s*bye\b", re.IGNORECASE)
UNVERIFIED_SUMMARY = ("I reviewed your conversation, but I could not verify the model's specific "
                      "corrections, so I left them out rather than show something wrong. "
                      "Your conversation is saved.")


def clean_punctuation(text):
    """Repair commas the local model sometimes inserts inside common phrases."""
    text = TIME_COMMA.sub(r"\1 \2", text)
    return GOODBYE_COMMA.sub(
        lambda match: "Goodbye" if match.group(0)[0].isupper() else "goodbye", text)


def validate_feedback(raw, user_texts):
    """Ground every quote in the learner's words.

    Findings with an invented quote are dropped so one bad model suggestion
    cannot lose an otherwise useful report. If no finding is grounded, raise so
    the caller can retry rather than showing fabricated corrections.
    """
    feedback = Feedback.model_validate_json(raw)
    grounded = []
    ungrounded = False
    for finding in feedback.findings:
        if not any(finding.quote in text for text in user_texts):
            ungrounded = True
            continue
        suggestion = clean_punctuation(finding.suggestion)
        if finding.quote.strip() == suggestion.strip():
            # A no-op is weak advice, not a fabrication. Keep the useful items.
            continue
        if is_contraction_only_change(finding.quote, suggestion):
            continue
        grounded.append(finding.model_copy(update={
            "suggestion": suggestion,
            "explanation": clean_punctuation(finding.explanation),
        }))
    if ungrounded and not grounded:
        raise UngroundedFeedback("No feedback quote matched the learner's exact words.")
    return feedback.model_copy(update={"findings": grounded})


def clean_summary(summary):
    """Keep model meta-commentary about rewriting out of the learner's report."""
    lowered = summary.lower()
    if any(phrase in lowered for phrase in ("rewrite", "original text", "review process")):
        return "Here are some useful changes to make your English sound more natural."
    return summary


def format_feedback(feedback):
    if not feedback.findings:
        if feedback.summary == UNVERIFIED_SUMMARY:
            return display_text(feedback.summary)
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
                                         "exact supplied user text. Omit any finding whose quote is not an "
                                         "exact substring." if attempt else ""))
            feedback = validate_feedback(raw, user_texts)
            summary = (clean_summary(feedback.summary) if feedback.findings else
                       "No clear wording issues were found in this conversation. Keep practicing!")
            return feedback.model_copy(update={"summary": summary})
        except UngroundedFeedback:
            if attempt:
                # Keep the transcript and the save flow even when the model
                # cannot support a finding with the learner's exact words.
                return Feedback(summary=UNVERIFIED_SUMMARY, findings=[])
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
    unverified_batches = 0
    for batch in batches:
        feedback = await review_batch(batch)
        if feedback.summary == UNVERIFIED_SUMMARY:
            unverified_batches += 1
        if not first_summary:
            first_summary = feedback.summary
        for finding in feedback.findings:
            key = (finding.category, finding.quote, finding.suggestion, finding.explanation)
            if key not in seen:
                findings.append(finding)
                seen.add(key)
    # Combine accepted findings without another model pass that could omit them.
    if not findings and unverified_batches == len(batches):
        summary = UNVERIFIED_SUMMARY
    elif len(batches) == 1:
        summary = first_summary
    else:
        summary = (f"I reviewed all {len(user_texts)} of your spoken turns. "
                   "Here are useful wording suggestions from your conversation.")
    feedback = ReportFeedback(summary=summary, findings=findings)
    report_text = format_feedback(feedback)
    if len(report_text) > 100000:
        raise ModelError("The feedback report exceeds the local file limit. No partial report was marked complete; your transcript is still open.")
    return {**feedback.model_dump(), "report_text": report_text}
