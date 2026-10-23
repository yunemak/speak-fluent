"""Real local-model smoke check, using synthetic speech, not a human mic check.

Run with the backend and Ollama started: .venv/bin/python scripts/verify_speech.py
No transcript or audio is saved. Prints only the artificial test conversation.
"""
import io
import time
import wave
from uuid import uuid4

import httpx
import numpy as np


def microphone_wav(audio):
    with wave.open(io.BytesIO(audio), "rb") as wav:
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    resampled = np.interp(np.arange(0, len(samples), rate / 16000), np.arange(len(samples)), samples)
    result = io.BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(resampled.astype("<i2").tobytes())
    return result.getvalue()


def main():
    with httpx.Client(base_url="http://127.0.0.1:8000/api", timeout=120, trust_env=False) as client:
        health = client.get("/health").json()
        print("Readiness:", health)
        assert health["ready"]

        def post(path, data=None, audio=None):
            start = time.monotonic()
            response = (client.post(path, content=audio, headers={"Content-Type": "audio/wav"})
                        if audio is not None else client.post(path, json={"request_id": str(uuid4()), **data}))
            print(f"{path}: {response.status_code}, {time.monotonic() - start:.2f}s")
            response.raise_for_status()
            return response.content if path == "/speech" else response.json()

        opening = post("/reply", {"opening": True, "turns": []})["text"]
        print("Opening:", opening)
        spoken = post("/speech", {"text": opening})
        assert spoken[:4] == b"RIFF"
        turns = [{"id": str(uuid4()), "role": "assistant", "text": opening, "interrupted": False}]
        sample = post("/speech", {"text": "Yesterday I go to the park. I like walking there."})
        recognized = post("/transcribe", audio=microphone_wav(sample))
        print("Synthetic utterance recognized as:", recognized)
        assert recognized["text"] and not recognized["is_farewell"]
        turns.append({"id": str(uuid4()), "role": "user", "text": recognized["text"], "interrupted": False})
        reply = post("/reply", {"opening": False, "turns": turns})["text"]
        print("Follow-up:", reply)
        turns.append({"id": str(uuid4()), "role": "assistant", "text": reply, "interrupted": False})
        farewell = post("/transcribe", audio=microphone_wav(post("/speech", {"text": "Goodbye."})))
        assert farewell["is_farewell"], farewell
        turns.append({"id": str(uuid4()), "role": "user", "text": farewell["text"], "interrupted": False})
        report = post("/report", {"turns": turns})
        print("Report:", report["report_text"])
        assert report["findings"], "Inspect recognition fidelity and the deliberately imperfect example."
        assert post("/speech", {"text": report["report_text"]})[:4] == b"RIFF"
        clean = post("/report", {"turns": [{"id": str(uuid4()), "role": "user", "text": "I like walking in the park.", "interrupted": False}]})
        print("Clean-sentence report:", clean["report_text"])
        if clean["findings"]:
            print("Clean-sentence findings (not enforced yet):", clean["findings"])
        print("Real-model API smoke check passed. Human microphone quality and comfort remain a separate learner check.")


if __name__ == "__main__":
    main()
