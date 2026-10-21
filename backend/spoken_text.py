"""Remove decorative faces for voice synthesis; keep display text unchanged."""
import re

CONTRACTIONS = {
    "i'm": "i am", "im": "i am", "i've": "i have", "iv": "i have", "i'll": "i will",
    "i'd": "i would", "don't": "do not", "dont": "do not", "doesn't": "does not",
    "didn't": "did not", "can't": "cannot", "cant": "cannot", "won't": "will not",
    "it's": "it is", "its": "it is", "that's": "that is", "thats": "that is",
    "you're": "you are", "youre": "you are", "they're": "they are", "theyre": "they are",
    "we're": "we are", "were": "we are", "she's": "she is", "shes": "she is",
    "he's": "he is", "hes": "he is", "isn't": "is not", "isnt": "is not",
    "aren't": "are not", "arent": "are not", "wasn't": "was not", "wasnt": "was not",
    "weren't": "were not", "werent": "were not", "haven't": "have not",
    "havent": "have not", "hasn't": "has not", "hasnt": "has not", "hadn't": "had not",
    "hadnt": "had not", "wouldn't": "would not", "wouldnt": "would not",
    "shouldn't": "should not", "shouldnt": "should not", "couldn't": "could not",
    "couldnt": "could not", "let's": "let us", "lets": "let us", "gonna": "going to",
    "gotta": "got to", "wanna": "want to", "y'all": "you all", "yall": "you all",
}

KEYCAP = re.compile(r"[0-9#*]\ufe0f?\u20e3")
PICTOGRAPHS = re.compile(
    "[\U0001f000-\U0001faff\u2600-\u27bf"
    "\u200d\ufe0e\ufe0f\U000e0020-\U000e007f]+"
)
EMOTICONS = re.compile(r"[:;=][\-^']?[()]|(?<!\w)(?:[:;=8][\-^']?[DPp]|<3)(?!\w)")
EMOTIONAL_REACTION = re.compile(
    r"\b(?:congratulations|congrats|condolences|heartbreaking|devastating|"
    r"(?:happy|excited|thrilled|proud) for you|proud of you|"
    r"sorry to hear|sorry (?:that |you(?:'re| are) |for your loss)|"
    r"(?:sounds|must (?:be|feel)) (?:really |so |very )?"
    r"(?:exciting|upsetting|frustrating|painful|wonderful|disappointing))\b",
    re.IGNORECASE,
)


def spoken_text(text: str) -> str:
    text = KEYCAP.sub(" ", text)
    text = PICTOGRAPHS.sub(" ", text)
    text = EMOTICONS.sub(" ", text)
    # Keep paragraph breaks and ordinary Unicode words, quotes and punctuation.
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" +([,.!?;:])", r"\1", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def display_text(text: str) -> str:
    # Conservative presentation rule, not sentiment analysis: ordinary replies
    # lose decorative faces; clear celebration/sympathy may retain them.
    return text if EMOTIONAL_REACTION.search(text) else spoken_text(text)


def expand_contractions(text: str) -> str:
    """Normalize spelling so two versions of the same sentence can be compared."""
    normalized = text.lower().replace("’", "'")
    normalized = re.sub(r"[^a-z'\s]", " ", normalized)
    words = normalized.split()
    expanded = []
    for word in words:
        expanded.extend(CONTRACTIONS.get(word, word).split())
    return " ".join(expanded)


def is_contraction_only_change(quote: str, suggestion: str) -> bool:
    """True when the only difference is optional contraction style."""
    return expand_contractions(quote) == expand_contractions(suggestion)
