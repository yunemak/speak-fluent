# Speak Fluent

An English conversation partner that runs on your Linux computer. Speak naturally,
interrupt when you need to, and say goodbye to hear useful wording feedback.

**Build status:** first speech-loop slice tested and reviewed; history is being built.
Completed conversations currently stay in page memory; reloading clears them.
Saved Markdown history is the next slice. This version supports short feedback
inputs (14,000 user-text characters); it reports an error rather than silently
omitting turns from longer sessions.

## Requirements

- Linux, a current Chromium-based browser, microphone, and **headphones**.
- Node.js 22.12+ (tested 24.18.0) and Python 3.12 (tested 3.12.15).
- Ollama (tested 0.40.7). Initial downloads require internet and several GB of disk.
- Tested on an RTX 5070 Laptop GPU with 8 GB VRAM and 32 GB system RAM.
  Ollama runs Qwen3 on the GPU; Whisper `small.en` recognition and voice synthesis
  use the CPU. The larger recognizer is being tried after `base.en` misheard words
  in the first microphone review; it adds roughly half a second on short synthetic
  examples, with actual microphone accuracy still to be compared.

React 19.2.0, Vite 7.3.7, vad-web 0.0.31, and browser ONNX Runtime 1.22.0 are
pinned in `frontend/package.json` / `package-lock.json`. Python versions are pinned
in `backend/requirements.txt`. First browser check: Chromium 154.0.8037.97.

## One-time setup (online)

Run commands from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

On the original development machine, Python 3.12 and Ollama were installed locally
under ignored `.tools/`, leaving system Python alone. The existing `.venv` is ready.
For another machine without Python 3.12, [uv](https://docs.astral.sh/uv/) can install
an isolated interpreter: `uv python install 3.12`, then `uv venv --python 3.12 .venv`
and `uv pip install --python .venv/bin/python -r backend/requirements.txt`.

Start Ollama in one terminal:

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

For this machine's project-local installation, use
`.tools/ollama/bin/ollama` in place of `ollama` in every command.
If Ollama is already running, use that process rather than starting a second one;
configure its environment with `OLLAMA_NO_CLOUD=1` for offline-only use.

In another terminal:

```bash
ollama pull qwen3:4b-q4_K_M
.venv/bin/python scripts/download_models.py
```

Use the **explicit model tag above**. The shorter `qwen3:4b` alias now points at a
thinking-only model that did not respect `think: false` in the integration check.
The download script pins tested Whisper/Piper revisions, can be rerun, and records
sources in `models/sources.json`. npm's postinstall copies the browser VAD model,
worklet, WASM and JavaScript modules into `frontend/public/vendor/` for local use.
See [model sources and licenses](models/README.md).

## Start the app

Keep Ollama running. In a second terminal:

```bash
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

In a third terminal:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**. Use headphones, press **Start a conversation**, and
allow microphone access. Your partner speaks first. Pause for about one second
at the end of a turn. Speak over a reply to interrupt it; the browser now waits for
about 320 ms of probable speech to reduce interruptions from brief noises, with
buffered audio keeping the start of your words. Hide/show text whenever you want.
Emojis are reserved for clear emotional replies and are skipped by voice output.
Say **“Goodbye”** or **“End the conversation”** to finish and hear feedback.
Brief speech candidates are checked for a closing phrase without stopping playback
unless the phrase is recognized; other short candidates are ignored. Input is stopped during
the report; Start returns after playback ends.

The three local processes have separate jobs: Vite serves the interface, Python
coordinates recognition and voice, and Ollama generates replies. Ctrl+C in each
terminal stops that process. With setup complete, runtime uses only local assets;
the full disconnected-network learner check is still pending.

## First hands-on check

1. Hear the opening without speaking first, then complete a few hands-free turns.
2. Interrupt once during speech and once while the status says Thinking.
3. Hide/reveal text and check that the robot's balloon changes during audible speech.
4. Include a deliberate error such as “Yesterday I go to the park,” then say goodbye.
5. Listen for an accurate correction using your actual words. Check your recognized
   transcript too: feedback can only evaluate what recognition captured.

Notice delays, cut-off pauses, recognition mistakes, and whether feedback is useful.
Reloading closes the current session and clears its in-memory transcript in this slice.

## Troubleshooting

- **Microphone unavailable:** allow microphone access for `127.0.0.1:5173`, check the
  Linux input device and microphone mute switch, then Retry.
- **Missing local models:** follow the setup commands named by the warning. Restart
  Python after changing its packages or model configuration.
- **Cannot reach Python:** start the backend on port 8000. Readiness is at
  `http://127.0.0.1:8000/api/health`.
- **Ollama unavailable:** start it on port 11434, then Retry. `ollama ps` during a
  conversation shows GPU use. A first reply can take longer while the model loads.
- **Audio paused:** press Retry to unlock browser playback. Check the output device
  and headphone volume if playback is running but you cannot hear it.
- **VAD assets missing:** rerun `npm --prefix frontend ci`. Keep vad-web and browser
  ONNX Runtime versions paired; changing only one can break voice detection.

Runtime logs contain stage timings rather than conversation text. Audio stays
transient. Model weights, `.venv`, local tools, and generated vendor assets are
ignored by Git. Future completed files will live under ignored `data/conversations/`.

## Verification

```bash
npm --prefix frontend run build
node --test tests/conversation.test.js
.venv/bin/python -m pytest tests/test_farewell.py tests/test_feedback.py
```

With Python and Ollama running, check the real models using an artificial spoken
example (no transcript/audio files are saved):

```bash
.venv/bin/python scripts/verify_speech.py
```

This checks synthesis → recognition → follow-up → farewell → grounded feedback,
including a clean-sentence example. Automated checks cannot judge your microphone
or whether the conversation feels comfortable; try the hands-on check above.

## Recording the eventual demo

Capture the browser window, browser/system audio, and your microphone as separate
audio inputs (for example in OBS). Make a short recording and listen back to
confirm both voices are audible while using headphones. Final offline review,
history persistence, and submission preparation come in later build steps.
