# Local models and speech software

Weights are downloaded during setup and excluded from Git. Runtime has no
download fallback: Whisper uses `local_files_only=True`, Hugging Face offline mode
is set in Python, and browser inference assets are served from the local frontend.

| Component | Tested selection | Source / license |
| --- | --- | --- |
| Conversation and feedback | `qwen3:4b-q4_K_M`, Ollama digest prefix `2bfd38a7daaf`, approximately 2.6 GB download | [Ollama tag](https://ollama.com/library/qwen3:4b-q4_K_M); Qwen3 weights Apache-2.0 |
| Recognition | `Systran/faster-whisper-small.en`, approximately 484 MB model weights | [Repository](https://huggingface.co/Systran/faster-whisper-small.en), MIT model card; faster-whisper 1.2.1 is MIT |
| Voice | `en_US-lessac-medium`, 22,050 Hz, approximately 63 MB weights | [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD); dataset/voice terms linked below |
| Voice synthesis | piper-tts 1.8.0 | [Piper](https://github.com/OHF-Voice/piper1-gpl), GPL-3.0; voice terms are separate |
| Speech detection | Silero VAD v5 distributed with `@ricky0123/vad-web` 0.0.31 | [Silero](https://github.com/snakers4/silero-vad), MIT; [vad-web](https://github.com/ricky0123/vad), ISC |
| Browser inference | onnxruntime-web 1.22.0 | [ONNX Runtime](https://github.com/microsoft/onnxruntime), MIT |
| Local model runner | Ollama 0.40.7 | [Ollama](https://github.com/ollama/ollama), MIT |

The original Qwen3 4B tag is deliberate. The moving `qwen3:4b` alias resolved to
Thinking 2507 in the first integration check, and generated reasoning rather than
a short answer with `think: false`.

Pinned Hugging Face repository revisions in `scripts/download_models.py`:

- Whisper: `d1d751a5f8271d482d14ca55d9e2deeebbae577f`
- Piper voices: `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd`

Whisper files go into `models/whisper-small.en/`. Piper `.onnx`, `.onnx.json`, and
`MODEL_CARD` go into `models/piper/`. The downloaded Lessac card refers to the
[Blizzard 2013 Lessac dataset license](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html)
for its source data; the card does not label the voice as MIT or GPL. Preserve those
separate terms when considering model distribution. This repository does not
bundle model weights or establish a license for the learner's own application.

`models/sources.json` records the successful setup's revisions. Ollama keeps its
weights in its own local model store (normally `~/.ollama/models`). The initial
thinking-only model downloaded during investigation can coexist with the selected
tag; the app explicitly requests only `qwen3:4b-q4_K_M`.

The first microphone review exposed misrecognition of “web3” and “interview” with
`base.en`. The next review uses `small.en`, still CPU int8 and fully local. On five
short synthesized examples, base.en took 0.20–0.23 s and small.en 0.58–0.73 s;
both recognized the examples, so accuracy improvement on the learner's actual
voice remains to be verified. The old ignored `models/whisper-base.en/` directory
is retained for comparison but is no longer the active model.
