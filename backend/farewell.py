"""Deterministic closing-utterance matching for the practice session.

A closing is recognised when the learner's words contain a known closing
phrase, an explicit intention to leave, or a farewell at the end of a longer
turn. Rules keep ordinary sentences from ending practice:

* a farewell word must be surrounded by ordinary filler or courtesy, or
* a farewell at the end of a longer turn must not be narrated, negated, or
  asked about, or
* an action such as "let's call it a day" or "I have to go now" must end the
  turn and must not be negated or reported as someone else's words.

The start-of-turn rule matters when a closing word is spoken over the AI's
voice: the recogniser then hears both, for example "Goodbye. How was your day?".

Clauses are matched separately so a negation in an unrelated clause does not
hide a real closing: "Not specific, let's end the conversation now, goodbye."
still ends practice, while "I don't want to say goodbye" does not.
"""
import re

# Whole closing phrases a learner may say to end practice.
CLOSING_PHRASES = {
    ("goodbye",), ("good", "bye"), ("bye",), ("bye", "bye"), ("goodby",),
    ("goodbye", "for", "now"), ("bye", "for", "now"), ("goodbye", "for", "today"),
    ("see", "you"), ("see", "ya"), ("see", "you", "later"), ("see", "you", "soon"),
    ("see", "you", "tomorrow"), ("see", "you", "next", "time"), ("catch", "you", "later"),
    ("talk", "later"), ("talk", "to", "you", "later"),
    ("thats", "all"), ("that", "is", "all"), ("thats", "it"), ("that", "is", "it"),
    ("thats", "all", "for", "today"), ("that", "is", "all", "for", "today"),
    ("thats", "it", "for", "today"), ("that", "is", "it", "for", "today"),
    ("lets", "stop", "here"), ("end", "the", "conversation"), ("end", "this", "conversation"),
    ("stop", "the", "conversation"), ("stop", "this", "conversation"),
    ("end", "the", "session"), ("end", "this", "session"),
    ("lets", "end", "the", "conversation"), ("let", "us", "end", "the", "conversation"),
    ("i", "am", "done"), ("im", "done"), ("we", "are", "done"), ("were", "done"),
    ("i", "am", "finished"), ("im", "finished"), ("i", "am", "done", "for", "today"),
    ("i", "am", "saying", "goodbye"), ("saying", "goodbye"), ("i", "am", "leaving"),
    ("have", "a", "nice", "day"), ("take", "care"),
}

# Clear decisions or obligations to leave. These are checked at the end of a
# turn so "I call it a day when I finish work" stays ordinary conversation.
ACTION_CLOSINGS = {
    ("call", "it", "a", "day"), ("call", "it", "a", "night"),
    ("wrap", "up"), ("wrap", "things", "up"),
    ("finish", "here"), ("stop", "here"),
    ("end", "the", "conversation"), ("end", "this", "conversation"),
    ("end", "our", "conversation"), ("end", "the", "session"), ("end", "this", "session"),
    ("i", "have", "to", "go"), ("i", "need", "to", "go"), ("i", "should", "go"),
    ("i", "must", "go"),
    ("i", "have", "to", "leave"), ("i", "need", "to", "leave"),
    ("i", "should", "leave"), ("i", "must", "leave"),
    ("i", "have", "to", "run"), ("i", "need", "to", "run"),
    ("i", "have", "to", "head", "out"), ("i", "need", "to", "head", "out"),
    ("i", "should", "get", "going"), ("i", "need", "to", "get", "going"),
    ("i", "have", "to", "get", "going"), ("i", "must", "be", "going"),
    ("we", "have", "to", "go"), ("we", "need", "to", "go"), ("we", "should", "go"),
    ("we", "have", "to", "leave"), ("we", "need", "to", "leave"),
    ("we", "should", "leave"), ("we", "must", "go"),
    ("im", "going", "to", "go"), ("im", "going", "to", "leave"),
    ("im", "heading", "out"), ("im", "off"), ("im", "leaving"),
    ("ive", "got", "to", "go"), ("i", "got", "to", "go"), ("i", "gotta", "go"),
    ("id", "better", "go"), ("i", "had", "better", "go"), ("i", "better", "go"),
    ("time", "to", "go"), ("time", "for", "me", "to", "go"),
    ("ill", "let", "you", "go"), ("i", "will", "let", "you", "go"),
    ("we", "can", "stop"), ("we", "can", "finish"), ("we", "can", "end"),
    ("lets", "stop"), ("lets", "finish"), ("lets", "end"),
    ("lets", "wrap", "up"), ("lets", "call", "it", "a", "day"),
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

# A reported or questioned goodbye is not an intention to leave.
SPEECH_NARRATION = {
    "said", "say", "says", "saying", "told", "tell", "asked", "ask", "mention",
    "mentioned", "talked", "talk", "explained", "explain", "wrote", "write",
    "heard", "hear", "mean", "means", "meant",
}

NEGATIONS = {"not", "dont", "doesnt", "didnt", "wont", "cant", "never", "no"}
QUESTION_WORDS = {"how", "what", "why", "when", "where", "who", "which"}

MAX_TOKENS = 40
MAX_WORDS_AROUND = 6

# Only unmistakable farewells may keep their meaning when unrelated words
# follow them in the same clause (for example, speech heard over the AI voice).
STRONG_FAREWELL_STARTS = {"goodbye", "good", "bye", "goodby", "see", "catch", "talk", "saying"}


def tokenize(text: str):
    """Lowercase tokens plus the clause number for each token.

    Commas and sentence punctuation start a new clause so a negation such as
    "not specific" cannot negate a later, separate "let's end the conversation".
    """
    normalized = text.lower().replace("’", "'").replace("'", "")
    parts = re.split(r"([.!?;:,]+)", normalized)
    tokens, clause_ids = [], []
    for index in range(0, len(parts), 2):
        clause_tokens = re.sub(r"[^a-z\s]", " ", parts[index]).split()
        tokens.extend(clause_tokens)
        clause_ids.extend([index // 2] * len(clause_tokens))
    return tokens, clause_ids


def clause_start(index, clause_ids):
    """First token index of the clause containing `index`."""
    while index > 0 and clause_ids[index - 1] == clause_ids[index]:
        index -= 1
    return index


def closing_spans(tokens):
    """Every contiguous span of tokens that is a known closing phrase."""
    spans = []
    for size in range(1, 6):
        for start in range(0, len(tokens) - size + 1):
            if tuple(tokens[start:start + size]) in CLOSING_PHRASES:
                spans.append((start, start + size))
    return spans


def action_spans(tokens):
    """Every contiguous span that states a clear intention to leave."""
    spans = []
    for phrase in ACTION_CLOSINGS:
        size = len(phrase)
        for start in range(0, len(tokens) - size + 1):
            if tuple(tokens[start:start + size]) == phrase:
                spans.append((start, start + size))
    return spans


def is_farewell(text: str) -> bool:
    """True only for a closing utterance, never for an incidental mention."""
    tokens, clause_ids = tokenize(text)
    if not tokens or len(tokens) > MAX_TOKENS:
        return False
    question = "?" in text

    for start, end in closing_spans(tokens):
        outside = tokens[:start] + tokens[end:]
        if all(word in ALLOWED_EXTRA_WORDS for word in outside):
            return True
        # An unmistakable farewell spoken first still ends practice when
        # unrelated words follow it (for example, a reply heard over the AI
        # voice), unless the learner is describing or questioning it.
        if tokens[start] in STRONG_FAREWELL_STARTS and \
                start - clause_start(start, clause_ids) <= 1 and \
                len(outside) <= MAX_WORDS_AROUND and not (
                    any(word in NARRATION_WORDS for word in outside)):
            return True

    # A farewell at the end of a longer turn still ends practice, even with a
    # short courtesy after it, as long as the learner is not reporting,
    # negating, or asking about the goodbye itself in that clause.
    for start, end in closing_spans(tokens):
        after = tokens[end:]
        before = tokens[clause_start(start, clause_ids):start]
        if len(after) <= 2 and all(word in ALLOWED_EXTRA_WORDS for word in after):
            if not (question or any(word in SPEECH_NARRATION or word in NEGATIONS for word in before)):
                return True

    # "Let's call it a day", "I have to go now", and similar clear decisions.
    # Accept only when the action ends the turn (allowing polite sign-offs).
    for start, end in action_spans(tokens):
        after = tokens[end:]
        before = tokens[clause_start(start, clause_ids):start]
        if question or any(word in QUESTION_WORDS for word in before):
            continue
        if any(word in NEGATIONS for word in before[-3:]):
            continue
        if any(word in SPEECH_NARRATION for word in before):
            continue
        if len(after) <= 4 and all(word in ALLOWED_EXTRA_WORDS for word in after):
            return True
    return False
