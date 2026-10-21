import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
WHISPER_PATH = MODELS / "whisper-small.en"
# Kokoro is the natural-sounding engine; Piper stays as the small local fallback.
KOKORO_MODEL = MODELS / "kokoro" / "kokoro-v1.0.int8.onnx"
KOKORO_VOICES = MODELS / "kokoro" / "voices-v1.0.bin"
VOICE_NAME = os.environ.get("SPEAK_FLUENT_VOICE", "af_heart")
PIPER_VOICE_NAME = os.environ.get("SPEAK_FLUENT_PIPER_VOICE", "en_US-lessac-medium")
PIPER_VOICE_PATH = MODELS / "piper" / f"{PIPER_VOICE_NAME}.onnx"
OLLAMA_URL = os.environ.get("SPEAK_FLUENT_OLLAMA_URL", "http://127.0.0.1:11434")
CHAT_MODEL = "qwen3:4b-q4_K_M"
HISTORY_PATH = Path(os.environ.get("SPEAK_FLUENT_HISTORY_DIR", ROOT / "data" / "conversations"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
