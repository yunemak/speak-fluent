"""Online setup only. Runtime uses explicit local paths and never downloads."""
import json
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
SOURCES = {
    "whisper": ("Systran/faster-whisper-small.en", "d1d751a5f8271d482d14ca55d9e2deeebbae577f", MODELS / "whisper-small.en"),
    "piper": ("rhasspy/piper-voices", "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd", MODELS / "piper"),
}


def main():
    manifest = {}
    for name, (repo, revision, destination) in SOURCES.items():
        manifest[name] = {"repo": repo, "revision": revision}
        if name == "whisper":
            snapshot_download(repo, revision=revision, local_dir=destination,
                              allow_patterns=["*.json", "*.bin", "*.txt", "README.md"])
        else:
            destination.mkdir(parents=True, exist_ok=True)
            prefix = "en/en_US/lessac/medium/"
            for filename in ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json", "MODEL_CARD"]:
                source = Path(hf_hub_download(repo, prefix + filename, revision=revision))
                target = destination / filename
                temporary = target.with_suffix(target.suffix + ".part")
                temporary.write_bytes(source.read_bytes())
                temporary.replace(target)
    (MODELS / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Models downloaded. Exact revisions recorded in models/sources.json.")


if __name__ == "__main__":
    main()
