import re

CLOSINGS = {
    "goodbye", "good bye", "bye", "bye bye", "bye for now", "see you", "see you later",
    "see you soon", "that's all for today", "that is all for today", "let's stop here",
    "end the conversation", "end this conversation", "stop the conversation",
    "stop this conversation", "end the session", "end this session",
    "let's end the conversation", "let us end the conversation",
}


def is_farewell(text: str) -> bool:
    normalized = text.lower().replace("’", "'")
    normalized = re.sub(r"[^a-z'\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"^(?:(?:okay|ok|well|please|thank you|thanks) )+", "", normalized)
    normalized = re.sub(r"(?: (?:please|thank you|thanks|take care|have a nice day))+$", "", normalized)
    return normalized in CLOSINGS
