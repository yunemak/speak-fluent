import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
WHISPER_PATH = MODELS / "whisper-small.en"
VOICE_PATH = MODELS / "piper" / "en_US-lessac-medium.onnx"
OLLAMA_URL = "http://127.0.0.1:11434"
CHAT_MODEL = "qwen3:4b-q4_K_M"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
