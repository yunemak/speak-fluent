"""Remove decorative faces for voice synthesis; keep display text unchanged."""
import re

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
