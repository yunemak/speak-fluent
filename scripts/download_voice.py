"""Download one extra Piper voice for comparison. Online setup only.

Usage: .venv/bin/python scripts/download_voice.py en_US-amy-medium
"""
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

MODELS = Path(__file__).resolve().parent.parent / "models" / "piper"
REPOSITORY = "rhasspy/piper-voices"
REVISION = "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd"
LOCALE = {"en_US": "en/en_US", "en_GB": "en/en_GB"}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: download_voice.py <locale-voice-quality> (for example en_US-amy-medium)")
    name = sys.argv[1]
    locale, voice, quality = name.split("-", 2)
    prefix = f"{LOCALE[locale]}/{voice}/{quality}/"
    MODELS.mkdir(parents=True, exist_ok=True)
    for filename in [f"{name}.onnx", f"{name}.onnx.json", "MODEL_CARD"]:
        source = Path(hf_hub_download(REPOSITORY, prefix + filename, revision=REVISION))
        target = MODELS / filename
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(source.read_bytes())
        temporary.replace(target)
    print(f"Downloaded {name} into {MODELS}.")


if __name__ == "__main__":
    main()
