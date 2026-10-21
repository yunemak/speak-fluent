"""Deterministic closing-utterance matching for the practice session.

A closing is recognised when the learner's words contain a known closing
phrase. Two extra rules keep ordinary sentences from ending practice:

* the words around the phrase must be ordinary filler or courtesy, or
* the phrase must start the utterance and nothing around it suggests the
  learner is merely talking about saying goodbye.

The second rule matters when a closing word is spoken over the AI's voice: the
recogniser then hears both, for example "Goodbye. How was your day?".
"""
import re

# Whole closing phrases a learner may say to end practice.
CLOSING_PHRASES = {
    ("goodbye",), ("good", "bye"), ("bye",), ("bye", "bye"), ("goodby",),
    ("goodbye", "for", "now"), ("bye", "for", "now"), ("goodbye", "for", "today"),
    ("see", "you"), ("see", "ya"), ("see", "you", "later"), ("see", "you", "soon"),
    ("see", "you", "tomorrow"), ("see", "you", "next", "time"), ("catch", "you", "later"),
    ("talk", "later"), ("talk", "to", "you", "later"),
    ("thats", "all"), ("that", "is", "all"), ("thats", "all", "for", "today"),
    ("that", "is", "all", "for", "today"), ("lets", "stop", "here"),
    ("end", "the", "conversation"), ("end", "this", "conversation"),
    ("stop", "the", "conversation"), ("stop", "this", "conversation"),
    ("end", "the", "session"), ("end", "this", "session"),
    ("lets", "end", "the", "conversation"), ("let", "us", "end", "the", "conversation"),
    ("i", "am", "done"), ("im", "done"), ("we", "are", "done"), ("were", "done"),
    ("i", "am", "finished"), ("im", "finished"), ("i", "am", "done", "for", "today"),
    ("i", "am", "saying", "goodbye"), ("saying", "goodbye"), ("i", "am", "leaving"),
    ("have", "a", "nice", "day"), ("take", "care"),
}

# Ordinary words that may appear around a closing phrase without changing it.
ALLOWED_EXTRA_WORDS = {
    "okay", "ok", "well", "uh", "um", "so", "right", "alright", "thanks", "thank",
    "you", "please", "and", "then", "now", "i", "im", "we", "am", "are", "was",
    "be", "that", "this", "it", "m", "my", "just", "really", "very", "dear",
    "have", "a", "nice", "day", "take", "care", "bye", "goodbye", "for", "to",
    "say", "going", "will", "everyone", "everybody", "all", "guys",
    "folks", "friend", "friends", "sir", "madam", "sorry", "see", "later", "soon",
    "tomorrow", "no", "problem", "again", "next", "time", "team",
}

# Words that show the learner is talking about a goodbye rather than saying one.
NARRATION_WORDS = {
    "said", "say", "says", "saying", "told", "tell", "asked", "ask", "mention",
    "mentioned", "talked", "talk", "explained", "explain", "wrote", "write",
    "heard", "hear", "mean", "means", "meant", "wanted", "want", "hope", "thought",
    "think", "because", "dont", "doesnt", "didnt", "wont", "cant", "would",
    "should", "never", "yesterday", "morning", "afternoon", "week", "month", "ago",
}

MAX_TOKENS = 14
MAX_WORDS_AROUND = 6


def normalize(text: str):
    normalized = text.lower().replace("’", "'").replace("'", "")
    normalized = re.sub(r"[^a-z\s]", " ", normalized)
    return normalized.split()


def closing_spans(tokens):
    """Every contiguous span of tokens that is a known closing phrase."""
    spans = []
    for size in range(1, 6):
        for start in range(0, len(tokens) - size + 1):
            if tuple(tokens[start:start + size]) in CLOSING_PHRASES:
                spans.append((start, start + size))
    return spans


def is_farewell(text: str) -> bool:
    """True only for a closing utterance, never for an incidental mention."""
    tokens = normalize(text)
    if not tokens or len(tokens) > MAX_TOKENS:
        return False
    for start, end in closing_spans(tokens):
        outside = tokens[:start] + tokens[end:]
        if all(word in ALLOWED_EXTRA_WORDS for word in outside):
            return True
        # The closing word was spoken first, and the rest does not read like
        # the learner describing or questioning a goodbye.
        if start <= 1 and len(outside) <= MAX_WORDS_AROUND and not (
                any(word in NARRATION_WORDS for word in outside)):
            return True
    return False
