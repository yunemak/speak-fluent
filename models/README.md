# Local models and speech software

Weights are downloaded during setup and excluded from Git. Runtime has no
download fallback: Whisper uses `local_files_only=True`, Hugging Face offline mode
is set in Python, and browser inference assets are served from the local frontend.

| Component | Tested selection | Source / license |
| --- | --- | --- |
| Conversation | `qwen3:4b-q4_K_M`, Ollama digest prefix `2bfd38a7daaf`, approximately 2.6 GB download | [Ollama tag](https://ollama.com/library/qwen3:4b-q4_K_M); Qwen3 weights Apache-2.0 |
| Feedback | `qwen3:8b`, Ollama digest prefix `500a1f067a9f`, approximately 5.2 GB download | [Ollama tag](https://ollama.com/library/qwen3:8b); Qwen3 weights Apache-2.0 |
| Recognition | `Systran/faster-whisper-small.en`, approximately 484 MB model weights | [Repository](https://huggingface.co/Systran/faster-whisper-small.en), MIT model card; faster-whisper 1.2.1 is MIT |
| Voice | Kokoro `af_heart` (default) and other `voices-v1.0.bin` voices, 24 kHz | [Kokoro-82M](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX), Apache-2.0; each voice has its own character and terms |
| Voice (fallback) | Piper `en_US-lessac-medium`, 22,050 Hz, approximately 63 MB weights | [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD); dataset/voice terms linked below |
| Speech synthesis | kokoro-onnx 0.6.1 with the full-precision model (approximately 311 MB) and `voices-v1.0.bin` (approximately 28 MB); an existing int8 model (approximately 92 MB) is still accepted as a fallback | [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), Apache-2.0; espeak-ng supplies the phonemes |
| Voice (fallback) | piper-tts 1.8.0 | [Piper](https://github.com/OHF-Voice/piper1-gpl), GPL-3.0; voice terms are separate |
| Speech detection | Silero VAD v5 distributed with `@ricky0123/vad-web` 0.0.31 | [Silero](https://github.com/snakers4/silero-vad), MIT; [vad-web](https://github.com/ricky0123/vad), ISC |
| Browser inference | onnxruntime-web 1.22.0 | [ONNX Runtime](https://github.com/microsoft/onnxruntime), MIT |
| Local model runner | Ollama 0.40.7 | [Ollama](https://github.com/ollama/ollama), MIT |

The original Qwen3 4B tag is deliberate. The moving `qwen3:4b` alias resolved to
Thinking 2507 in the first integration check, and generated reasoning rather than
a short answer with `think: false`. The 4B model handles live conversation; the 8B
model is used only for the two feedback passes after practice ends. The 8B model
has better collocation judgment, and its 6.2 GB loaded footprint means it replaces
the 4B model in GPU memory until the learner starts another conversation.

Pinned Hugging Face repository revisions in `scripts/download_models.py`:

- Whisper: `d1d751a5f8271d482d14ca55d9e2deeebbae577f`
- Piper voices: `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd`

Whisper files go into `models/whisper-small.en/`. Piper `.onnx`, `.onnx.json`, and
`MODEL_CARD` go into `models/piper/`. The Kokoro model and voice pack go into
`models/kokoro/`. The downloaded Lessac card refers to the
[Blizzard 2013 Lessac dataset license](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html)
for its source data; the card does not label the voice as MIT or GPL. Each additional
voice downloaded with `scripts/download_voice.py` brings its own model card and terms.
Preserve those separate terms when considering model distribution. This repository does
not bundle model weights. Speak Fluent's original application code is licensed
under [GPL-3.0-only](../LICENSE); that does not change these third-party terms.

Kokoro's voice pack contains many named voices (`af_heart`, `af_nicole`, `am_michael`,
`bf_emma`, and others). Each one is a trained character with its own review history;
`models/voice-samples/` renders them locally so a choice can be made by listening.
At runtime `backend/voice.py` also applies a 9 kHz linear-phase low-pass before
mastering, which removes Kokoro's hot 9–12 kHz band heard as static while keeping
the 4–9 kHz speech band. The filter is part of the app, not the model files.

`models/sources.json` records the successful setup's revisions. Ollama keeps its
weights in its own local model store (normally `~/.ollama/models`). The initial
thinking-only model downloaded during investigation can coexist with the selected
tags; the app explicitly requests only `qwen3:4b-q4_K_M` and `qwen3:8b`.

The first microphone review exposed misrecognition of “web3” and “interview” with
`base.en`. The next review uses `small.en`, still CPU int8 and fully local. On five
short synthesized examples, base.en took 0.20–0.23 s and small.en 0.58–0.73 s;
both recognized the examples, so accuracy improvement on the learner's actual
voice remains to be verified. The old ignored `models/whisper-base.en/` directory
is retained for comparison but is no longer the active model.
