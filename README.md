# Speak Fluent

An English conversation partner that runs on your Linux computer. Speak naturally,
interrupt when you need to, and say goodbye to hear useful wording feedback.

**Build status:** the speech loop, saved history, offline run, and recovery paths are
tested with real local models; the learner's final disconnected review is what is left.
Completed conversations are saved locally after feedback playback and can be reopened
from the sidebar after restarting the app. Long conversations are reviewed in batches, so
every spoken turn is covered by the feedback report.

## Requirements

- Linux, a current Chromium-based browser, microphone, and **headphones**.
- Node.js 22.12+ (tested 24.18.0) and Python 3.12 (tested 3.12.15).
- Ollama (tested 0.40.7). Initial downloads require internet and several GB of disk.
- Tested on an RTX 5070 Laptop GPU with 8 GB VRAM and 32 GB system RAM.
  Ollama runs Qwen3 on the GPU; Whisper `small.en` recognition and Kokoro voice
  synthesis use the CPU. The recognizer moved to `small.en` after `base.en`
  misheard words in the first microphone review; it adds roughly half a second on
  short synthetic examples, with accuracy on the learner's own voice still to be
  compared.

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
ollama pull qwen3:8b
.venv/bin/python scripts/download_models.py
```

Use the **explicit 4B model tag above**. The shorter `qwen3:4b` alias now points at a
thinking-only model that did not respect `think: false` in the integration check.
The 4B model keeps spoken conversation fast; the 8B model runs only the two feedback
passes after practice ends, where its stronger collocation judgment matters.
The download script pins tested Whisper/Piper revisions, fetches the full-precision
Kokoro model and voice pack, can be rerun, and records sources in `models/sources.json`. npm's postinstall copies the browser VAD model,
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
at the end of a turn. Speak over a reply to interrupt it; the browser waits for a
short, sustained burst of probable speech so brief noises do not count, and keeps
buffered audio so your first word is not lost. If a cough or other noise does stop
a reply, the same reply resumes where it stopped instead of disappearing.
Quiet speech is level-normalized before recognition. Recognition is primed with
a common everyday phrase so fast, casual greetings are less likely to be
misheard.
Hide/show text whenever you want. Emojis are reserved for clear emotional replies
and are skipped by voice output. The live transcript follows the newest message
automatically; if you scroll up to reread, it resumes following when you return
to the bottom. Say **“Goodbye”** or **“End the conversation”** to
finish and hear feedback. Brief speech candidates are checked for a closing phrase
without stopping playback unless the phrase is recognized; a confident short phrase
heard while the app is listening becomes a normal turn. Input is stopped during
the report; after playback, the transcript and report are saved and Start returns.

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
Reloading clears unfinished sessions; successfully saved sessions remain in history.

## Saved conversations

Finish a conversation and wait for the feedback to finish playing. The app writes
one readable Markdown file under **`data/conversations/`**, named with its UTC
completion timestamp and session UUID, then refreshes the sidebar. Click a dated
entry to read its full transcript and separate feedback report. Hidden live text,
visible emojis, and interruption notes are preserved. History selection is available
after the current session finishes.

You can open the `.md` file directly in a text editor. Its small JSON metadata header
records the format version, session ID and timestamps; the rest is ordinary Markdown.
Each new practice gets its own file, and retrying a save cannot create duplicates.
Open an entry and use **Delete this conversation** to remove it; the app asks for
confirmation, deletes only that one Markdown file, and keeps the other entries.

For the hands-on check: finish and open one session, inspect its file, restart Python
and Vite with the commands above, and reopen it. Then finish another session and
confirm both entries remain available.

If saving fails, keep the page open, fix disk space or folder permissions, and press
**Retry save**. The app retains the transcript/report in memory and retries saving
without replaying feedback. Unreadable or malformed history files show warnings
while other entries remain available; the app leaves those files unchanged.

## Comparing voices

The default voice is Kokoro's `af_heart`, a local neural voice that sounds far more
natural than the older Piper voices. Setup downloads the full-precision Kokoro model;
an existing int8 model still works as a fallback. Kokoro output is peak-normalized
to 0.9 with short fades at the edges, so the voice is clear without turning the
speaker up into the playback chain's noise floor. Every local voice can be rendered
for a listening comparison:

```bash
.venv/bin/python scripts/compare_voices.py     # writes models/voice-samples/*.wav
```

Play the samples, then start Python with the voice you prefer:

```bash
SPEAK_FLUENT_VOICE=af_nicole .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Kokoro voice names are two-letter codes: `af` American female, `am` American male,
`bf` British female, `bm` British male, plus other accents. If the Kokoro files are
missing, the app falls back to a local Piper voice automatically. Voices are
downloaded once and stay offline; see
[model sources and licenses](models/README.md) for the terms that apply to each.

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
  ONNX Runtime versions paired; changing only one can break voice detection. The
  readiness check names this when the local browser assets are absent.
- **Microphone disconnected mid-session:** the app offers **Retry microphone**, which
  reopens the microphone and keeps the turns already recognized.
- **The AI stopped answering:** the app keeps the words it already generated and
  retries the voice instead of asking the model for new ones.

Runtime logs contain stage timings rather than conversation text. Audio stays
transient. Model weights, `.venv`, local tools, and generated vendor assets are
ignored by Git. Completed Markdown files live under ignored `data/conversations/`.
Verification can use an isolated directory by setting `SPEAK_FLUENT_HISTORY_DIR`
before starting Python; normal startup uses the repository's `data/conversations/`.

## Verification

```bash
npm --prefix frontend run build
node --test tests/conversation.test.js
.venv/bin/python -m pytest tests
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
confirm both voices are audible while using headphones. Final offline review and
submission preparation come in later build steps.
