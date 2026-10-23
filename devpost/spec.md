---
doc: spec
status: approved
---

# Speak Fluent — Technical Spec

## How This Works, In Plain Language

You open a React app in your browser on your Linux computer and put on your headphones. Python runs alongside it on the same computer. The browser and Python communicate through local addresses; this does not require internet access.

Pressing Start asks the local conversation model to greet you. Piper turns its written reply into audio. While you speak, Silero detects speech and pauses, and faster-whisper turns your recorded words into text. Ollama runs the model that reads that text and writes the next reply. The browser stops playing the AI's voice as soon as it detects your interruption.

Saying goodbye switches from conversation to feedback. The model reviews your actual words, and Kokoro reads the report aloud. A completed session is saved as a readable Markdown file on your computer. The sidebar reads those files when you return.

The interface uses your familiar React, JavaScript, Vite, and plain CSS through CSS Modules. Python connects the speech tools. Initial downloads need internet; the finished practice loop does not.

## The Core Journey Through the System

Implements `prd.md > The Core Journey`.

1. **Open:** React requests saved-session titles from Python. The main view shows Start, the robot, and the text-visibility control.
2. **Start:** the browser unlocks audio playback, requests microphone permission, starts local speech detection, and checks model readiness. Python asks Ollama for an everyday opening, then synthesizes it with Piper. The browser displays the reply and plays its audio.
3. **Talk:** Silero detects the end of an utterance. The browser sends a small WAV recording to Python. faster-whisper returns the recognized English words. Python sends conversation context to Ollama; its reply passes through Piper and returns as audio.
4. **Interrupt:** speech detection in the browser stops current playback immediately and invalidates any obsolete reply. Recording continues so the interrupting words become the next user turn.
5. **Hide text:** React changes only live AI-text visibility. Playback and the underlying transcript continue.
6. **Say goodbye:** a clear closing utterance triggers feedback. Python asks the same model to review the user turns. The browser plays the report, following the same text-visibility setting and speaking animation.
7. **Finish:** after successful report playback, Python writes the transcript and report to a Markdown file. React refreshes history and restores Start. Opening an old entry displays its transcript and separate report.

```text
Headphone microphone
        |
        v
React + browser Silero VAD ---- speech starts ----> stop browser audio
        |
        | utterance WAV (localhost)
        v
Python / faster-whisper --> recognized words --> Ollama / Qwen3
        ^                                           |
        |                                           v
        +-------- Python / Piper <-------------- reply text
                         |
                         v
                  browser plays WAV

Farewell --> feedback text + audio --> Markdown file --> history sidebar
```

## Stack

The learner agreed to React/Vite, CSS Modules with plain CSS, Python, Ollama, faster-whisper, Piper, and Silero VAD. Specific packages, model defaults, and storage details below are implementation recommendations presented for review.

| Piece | Choice and rationale | Documentation |
| --- | --- | --- |
| UI | React with JavaScript/JSX and Vite; builds on existing experience | [React](https://react.dev/learn), [Vite](https://vite.dev/guide/) |
| Styling | Component `.module.css` files; global plain CSS for resets and variables | [Vite CSS Modules](https://vite.dev/guide/features.html#css-modules) |
| Python HTTP backend | FastAPI, Uvicorn, Pydantic request validation, HTTPX for Ollama calls | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic](https://docs.pydantic.dev/latest/), [HTTPX](https://www.python-httpx.org/) |
| Conversation | Ollama, `qwen3:4b-q4_K_M`, `think: false`; explicit original 4B variant with GPU headroom | [Ollama API](https://docs.ollama.com/api/chat), [model](https://ollama.com/library/qwen3:4b-q4_K_M) |
| Feedback | Ollama, `qwen3:8b`, `think: false`; natural rewrite plus original/rewrite comparison after practice ends | [Ollama API](https://docs.ollama.com/api/chat), [model](https://ollama.com/library/qwen3:8b) |
| Recognition | faster-whisper `small.en`, CPU `int8`, English transcription; upgraded from `base.en` for the learner's recognition retry | [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [model](https://huggingface.co/Systran/faster-whisper-small.en) |
| Voice | Kokoro `voices-v1.0.bin` (`af_heart` default), CPU ONNX Runtime full-precision model, peak-normalized with short fades; Piper `en_US-lessac-medium` remains the small fallback | [Kokoro-82M ONNX](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX), [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) |
| Turn detection | Silero VAD in the browser through `@ricky0123/vad-web`, initially model `v5`; detects interruptions without a server round trip | [Silero](https://github.com/snakers4/silero-vad), [browser integration](https://docs.vad.ricky0123.com/user-guide/browser/), [callbacks](https://docs.vad.ricky0123.com/user-guide/api/) |
| Browser inference | Compatible `onnxruntime-web`; serve its WASM and JavaScript assets locally | [ONNX Runtime Web](https://onnxruntime.ai/docs/get-started/with-javascript/web.html) |
| Audio | Browser getUserMedia and Web Audio; Python standard-library `wave` and NumPy for PCM input | [getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [Web Audio](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API), [wave](https://docs.python.org/3/library/wave.html), [NumPy](https://numpy.org/doc/stable/) |
| Persistence | Python standard-library file operations; one Markdown file per completed session | [pathlib](https://docs.python.org/3/library/pathlib.html) |

Target Node.js 22.12+ or a newer supported LTS, and Python 3.12 in a virtual environment. Verify available versions and compatible binary wheels during setup; do not modify the system Python. Pin tested Python dependencies in `requirements.txt` and commit `package-lock.json`. VAD and ONNX Runtime versions must be compatible; do not independently upgrade them without checking the speech loop.

Research on 2026-10-20 confirmed documented local operation and Ollama's RTX 5070 support. `nvidia-smi` on this machine reported **RTX 5070 Laptop GPU, driver 615.78.08, 8151 MiB VRAM**. Qwen3 4B's listed quantized download is approximately 2.5 GB; runtime memory also includes context and inference overhead. No models have been installed or benchmarked yet. Speech recognition stays on CPU initially to avoid additional CUDA/cuDNN setup and GPU contention. Piper's current repository has recent project activity but is seeking maintainers; record the tested release.

## Where It Runs and How Someone Tries It

Implements `prd.md > States and Boundaries` and `prd.md > What We're Building`.

- CachyOS Linux, the learner's GPU and 32 GB RAM, headphones, and a working microphone.
- A current Chromium-based browser is the first verification target. Microphone access works on localhost; a desktop wrapper is unnecessary.
- Three local processes: Ollama on `127.0.0.1:11434`, Python on `127.0.0.1:8000`, and Vite on `127.0.0.1:5173`. Vite proxies `/api` to Python. Bind to loopback.
- No paid services, accounts, or API keys. No deployment is planned.

These commands describe the app to be built; its files do not exist yet. From the repository root, after installing Node, compatible Python, and Ollama:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

Start `ollama serve` in a terminal, unless an existing local service already runs it. While online, download the conversation model and run the planned setup script:

```bash
ollama pull qwen3:4b-q4_K_M
ollama pull qwen3:8b
.venv/bin/python scripts/download_models.py
```

The Python script downloads the complete faster-whisper model/tokenizer files, the Piper fallback voice, and the full-precision Kokoro model plus voice pack into `models/`. Frontend `postinstall` copies VAD model, worklet, WASM, and required `.mjs` files from installed packages into `frontend/public/vendor/`. Setup records model sources and versions. Missing assets must fail readiness checks rather than trigger runtime downloads.

Run the backend in a second terminal:

```bash
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Run the frontend in a third terminal:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**, allow the microphone, and press Start. For the demo, disconnect external networking after setup, reload the app, and run the journey under Verification. Keep localhost available.

Submission requires a short demo video and public GitHub repository. Record browser audio and microphone so both sides can be heard even while using headphones. The README must include setup, exact tested versions, startup, model-download requirements, saved-file location, and recording instructions. Model weights and personal conversations stay out of Git.

## Look and Feel

Implements `prd.md > Screens and Layout`, `prd.md > Look and Feel`, and `prd.md > Speech Text and Speaking Animation`.

- Roughly 10% sidebar / 90% main area at the target desktop size. Use a small minimum sidebar width to keep history labels usable.
- Keep the history sidebar pinned to the viewport during long-conversation scrolling, with its own overflow. On narrow screens use a bounded-height sticky history strip so practice content stays accessible.
- Keep the live transcript following the newest turn as messages, interruption notes, and the report are added, with a visible gap between the newest message and the bottom of the viewport. Pause following when the learner scrolls up to reread, and resume once the view returns near the bottom.
- Draw the simple 2D robot as a local SVG React component. Its balloon-like CSS background changes color only during actual audible playback, including feedback.
- CSS Modules for components; global CSS variables for colors and spacing. Use system fonts so nothing loads from a font service.
- Starting visual defaults for review: light neutral background, dark readable text, cool blue idle balloon, warm peach speaking balloon. These are implementation defaults, not previously chosen learner colors.
- Clear Start, Hide text / Show text, and status labels: Listening, Thinking, Speaking, Preparing feedback, Saving. Warnings describe what failed and how to retry.

## Components

### App Shell and History View

Implements `prd.md > Screens and Layout` and `prd.md > Old Conversations`.

`App.jsx` arranges `HistorySidebar`, `ConversationView`, and `HistoryView`. Fetch history on startup and after successful saving. Show an empty-history message on first use. History displays the same chat-style transcript as live practice through the shared `Transcript` component: user and assistant turns use aligned bubbles, interruption notes remain visible, and the feedback report has its own styled bubble. The saved Markdown stays the canonical file; the detail API also parses it into structured `turns` and `report_text` so the history view never renders raw Markdown.

During an active practice/report, keep history selection disabled with a short “Available after this session” hint so opening a file cannot accidentally replace the active conversation. Selecting history afterward keeps Start available for a new session.

### Browser Audio and Turn Detection

Implements `prd.md > Start and Spoken Conversation`.

`audio.js` owns microphone capture, Silero lifecycle, WAV encoding, and playback. Create/resume AudioContext inside the Start click before asynchronous work, request mono audio with echo cancellation and noise suppression, and release media tracks on completion, failure exit, or unmount. The user's normal listening setup is headphones.

Use `MicVAD` with explicit local asset paths. After the learner reported breathing/cough false interruptions, stop playback synchronously and invalidate pending AI audio only after 320 ms of speech-positive frames inside a 700 ms sliding window, and only when the current positive run is at least 192 ms. The sliding window keeps old sound from counting, and the current-run requirement stops separate bursts (for example a cough plus a breath) from adding up to an interruption. The initial `onSpeechStart` candidate must leave playback, pending replies, and UI state untouched; `onVADMisfire` only resets the local confirmation counter. Use positive/negative speech-probability thresholds of 0.65/0.4. Capture segments with at least 128 ms positive speech so a brief “goodbye” is not discarded. Segments below the confirmation threshold are transcribed in order as farewell-only candidates: leave playback unchanged, end practice if recognition confirms a whole closing phrase, and otherwise accept a confident non-closing phrase as a normal turn only when the app is listening (not while a reply is playing or being generated). Longer confirmed utterances follow the normal turn path. If a confirmed segment turns out to be noise rather than speech, resume the stopped reply from its saved audio offset instead of losing it and do not add a user turn. `onSpeechEnd` supplies a 16 kHz Float32Array; encode 16-bit mono WAV for recognition. Use about 1,000 ms of end-of-turn silence and 500 ms pre-speech padding so the beginning of a confirmed interruption is retained. These are detection settings, not agreed response-time targets. Tune against real breathing, coughing, quiet speech, and short utterances: speech confirmation reduces false triggers but is not a dedicated cough classifier, so the resume path is the safety net.

Speech detection stays active during conversation thinking and playback. Short utterances are queued for recognition in capture order. Do not cancel recognition of real user speech just because another utterance starts. Only generate a response when captured utterances have been transcribed and the user is no longer speaking.

### Conversation Controller and Speaking UI

Implements `prd.md > Start and Spoken Conversation`, `prd.md > Speech Text and Speaking Animation`, and `prd.md > States and Boundaries`.

`useConversation.js` connects React to a framework-independent `Conversation` controller in `lib/conversation.js`, which owns the active session and phases: idle, starting, listening, transcribing, thinking, speaking, preparing-feedback, feedback-speaking, saving, complete, error. Track whether the user is currently speaking separately from the phase. Keeping the controller independent allows race tests to exercise the actual orchestration code.

Use an incrementing response generation ID and AbortController. Speech start invalidates pending generation/synthesis; late responses cannot play or add assistant turns. Browser audio stops without waiting for server cancellation. Recognition results remain ordered. Back-end model work runs off the HTTP event loop; serialize each CPU model's inference. Watch for client disconnection while awaiting Ollama and cancel the outbound HTTP task. Check disconnection before entering and after acquiring CPU inference locks so abandoned synthesis requests leave the queue without running. An already-running CPU operation may finish; its result is discarded. Keep the lock until that underlying operation actually finishes, even if its request was canceled: the worker task owns the lock, not the HTTP request, so a canceled client cannot release it while an uninterruptible thread still runs.

A canceled or disconnected client raises an internal abandonment signal instead of a model error, so an abandoned request never surfaces as a user-visible failure. Retry reuses the generated words and any already-synthesized audio: a synthesis retry must not ask the model for a new reply, and a blocked-playback retry must not add a turn to the transcript unless playback actually started. A disconnected microphone is reported with a Retry microphone action that reopens the microphone and keeps earlier turns.

Store assistant text when its playback starts. Mark a cut-off reply “Interrupted — generated reply shown; not all words were spoken,” rather than pretending the full reply was heard. If playback never started, do not add it as a spoken turn. When a confirmed sound is recognized as noise, clear that mark and resume the same reply from the captured playback offset; the resumed turn is not duplicated and no user turn appears. Include interruption status in model context. The text-visibility toggle changes presentation only and defaults to visible for a fresh page load. The robot speaking state follows audio start/end/stop events, not generation activity.

### Python API and Recognition

Implements `prd.md > Start and Spoken Conversation` and `prd.md > States and Boundaries`.

`app.py` validates requests, exposes readiness/history endpoints, and delegates to small service modules. `speech.py` loads faster-whisper and Piper once per process. Use `WhisperModel(local_path, device="cpu", compute_type="int8", local_files_only=True)`, supply 16 kHz samples, English language, and `condition_on_previous_text=False`. Prime common everyday phrases with faster-whisper's `hotwords` (currently “I'm doing well, how are you?”) so fast, casual speech is less likely to become “Dean Well” or “Dingwell”; tests confirmed nearby wording such as “doing good” and a name followed by “well” stays unchanged. Peak-normalize quiet microphone audio toward 0.9 before recognition; clipped or quiet speech is otherwise easy to lose. Consume the segments iterator to perform recognition. Return a duration-weighted `no_speech_prob` with the text so the browser can distinguish a cough from a short real phrase. Do not ask recognition to fix grammar: the report needs the user's actual wording.

Empty/silent results return to listening with “I didn't catch that—please try again.” Errors are distinct from an empty recognition. Audio is transient and is not saved as history.

### Local Conversation Model

Implements `prd.md > Start and Spoken Conversation`.

`llm.py` calls Ollama through HTTPX. `prompts.py` holds separate opening, conversation, and feedback instructions. The opening is AI-generated everyday conversation; subsequent replies relate to the user and normally include a relevant follow-up. Ask for short, natural replies (typically 1–3 sentences) and defer corrections until feedback.

Use Qwen3 4B without thinking output for live conversation, with an 8,192-token context and bounded output. Use Qwen3 8B for feedback after practice ends: first rewrite each user turn into natural English, then compare the original and rewrite to produce grounded findings. The full transcript stays in the browser; normal replies use recent context within the model budget. Bound both reply context and feedback input by measured UTF-8 bytes (`llm.INPUT_BYTES`), not character counts, so multi-byte text cannot overflow the context window. An oversized newest turn keeps its final characters and marks earlier text as omitted from reply context.

Feedback must cover all user turns: split user turns into bounded batches (`llm.feedback_batches`), review every batch, collect quoted findings, and combine them into one report. Never silently claim to have reviewed omitted turns. A failure in any batch fails the whole report rather than returning a partial one. The combined report states how many user turns were reviewed when more than one batch was needed.

### Farewell and Feedback

Implements `prd.md > Farewell and Feedback Report`.

`farewell.py` matches whole closing utterances such as “goodbye,” “bye,” “bye for now,” “see you later,” “that's all for today,” “end the conversation,” and “stop this conversation,” with optional polite prefixes and endings. It also recognizes clear decisions to end practice such as “let's call it a day,” “I need to go now,” “I should get going,” “I have to run,” “I'm off,” and “I'll let you go.” These action phrases end practice only when they finish the turn (up to four polite sign-off words may follow) and are not negated, reported as someone else's words, or asked about. A farewell at the end of a longer turn also ends practice, with up to two courtesy words after it, provided the earlier words do not narrate, negate, or question the goodbye. This covers “I have some business to take care of, so let's call it a day. Goodbye.” without ending practice for “I have to go to the store,” “I have to go to work tomorrow,” or “I call it a day when I finish work.” A closing spoken first with short trailing words still ends practice, because the learner may say goodbye over the AI's voice and the recogniser then hears both. Words that show the learner is describing or questioning a goodbye block the match. Keep this deterministic for the POC rather than adding a separate intent model. The transcription endpoint returns `is_farewell` alongside recognized text. The controller checks it in utterance order before requesting another reply; when true, it closes practice input and ignores any subsequently captured utterances.

After a farewell, finish the final user transcription, stop accepting practice turns, and generate feedback. Pause microphone detection during the report: practice has ended. Feedback includes grammar, word choices, understandable wording, and simplification where there is useful evidence; pronunciation and accent are excluded.

Request structured findings `{category, quote, suggestion, explanation}` plus a brief summary. Each quote must occur in an actual user turn; reject unsupported quotes and retry once with explicit grounding instructions. Empty findings are valid: explain that no clear wording issues were found rather than inventing mistakes. Format the same accepted report for visible text, spoken synthesis, and storage. Quote checking prevents fabricated source examples but does not prove a correction is linguistically sound; check that manually in the early milestone.

A finding whose suggestion repeats its quote, or differs only by optional contraction style ('I am' versus 'I'm'), carries no advice: drop that single finding rather than losing the whole report. Ungrounded quotes always fail the batch. The report prompt must state that contractions, article use, and register choices are never mistakes. Word-choice findings need a real reason: unusual wording that would confuse a listener, not a more elegant synonym. The two-pass prompt asks the model to rewrite naturally first and then report real differences, with explicit collocation checks such as traffic increasing rather than getting longer. The comparison prompt must also check the original independently because the rewrite may remove an awkward phrase instead of replacing it.

### Local Voice Output

Implements `prd.md > Start and Spoken Conversation`, `prd.md > Speech Text and Speaking Animation`, and `prd.md > Farewell and Feedback Report`.

Use `PiperVoice.load(local_voice_path)` once and `synthesize_wav(text, wave_file)` to produce in-memory WAV bytes. The voice's configured sample rate is carried by the WAV; do not assume it is the microphone's 16 kHz rate. Browser playback receives WAV bytes and remains immediately stoppable. Start with complete short replies rather than a token/audio streaming pipeline. A longer report may take more time; show Preparing feedback until speech begins.

The learner heard the Piper voices as robotic, so voice output now runs on Kokoro, a local neural voice, with Piper kept as the automatic fallback when the Kokoro files are absent. Kokoro synthesizes 24 kHz audio through ONNX Runtime on the CPU and its own espeak-ng phonemizer; `backend/voice.py` owns engine selection, the voice name, and WAV encoding. `SPEAK_FLUENT_VOICE` selects a voice at startup and `scripts/compare_voices.py` renders every local voice for a listening comparison, so the learner can choose without an in-app picker.

Preserve decorative Unicode emojis and ASCII emoticons in generated replies and the formatted feedback report for display and storage. Remove them only from the derived text passed to Piper synthesis. Keep ordinary wording, punctuation, and validated source quotes intact; an emoji-only reply is an error rather than successful empty speech. The learner clarified during hands-on review that emojis should remain visible but never be pronounced by the voice.

The learner further limited displayed emojis to emotional answers. Default prompts to no emojis for routine conversation; use a conservative phrase-based presentation filter to retain generated decoration only for clear emotional reactions such as congratulations or sympathy. Routine feedback has no hard-coded emoji. Apply the filter to the generated report summary and remove decoration from instructional suggestions/explanations, preserving source quotes. This is a simple POC presentation heuristic, not a general sentiment classifier.

Speak long feedback in chunks so one request never exceeds a comfortable synthesis length: split the accepted report text at paragraph or word boundaries, synthesize and play each chunk in order, and keep speech continuous by requesting the next chunk while the current one plays. Do not pause between chunks in normal operation; a failed chunk retries with the same generated words rather than regenerating the report. The voice now uses Kokoro by default with Piper as the fallback, selected at startup by `SPEAK_FLUENT_VOICE`; `scripts/compare_voices.py` renders all local voices for a listening comparison without adding an in-app model picker.

### Markdown Conversation Store

Implements `prd.md > Old Conversations`.

`history.py` writes one UTF-8 file under `data/conversations/<UTC-timestamp>-<UUID>.md`. The file contains a title, format version, ID, creation/completion timestamps, `## Transcript`, role-labeled turns with interruption notes, and `## Feedback Report`. Use timestamp-based titles rather than another model call.

Write to a temporary file in the same directory and atomically rename after successful report playback. A failed save preserves the current session in browser memory and offers Retry save. Repeating a save with the same session ID is idempotent and cannot create another conversation or overwrite a different one. A small metadata header is enough to list files. On detail read, parse the body into structured turns and report text while keeping the raw `markdown` in the response for compatibility; the Markdown file remains canonical and readable on its own. Constrain IDs to generated UUIDs and resolve files only inside the history directory.

Deleting one saved conversation is an explicit, confirmed action from the history view: the browser asks for confirmation, the backend removes only the matching file inside the history directory, and the sidebar refreshes. A missing file returns 404, a file outside the store is refused, and other entries stay untouched.

## Data Model

| Data | Location and updates | Return/reload behavior |
| --- | --- | --- |
| Active session | React memory: UUID, timestamps, ordered turns, phase, report, response generation ID | Unfinished sessions do not survive reload; completed-history persistence is the POC requirement |
| Turn | `{id, role: user|assistant, text, interrupted}`; user text added after recognition, assistant text when playback starts | Written to Markdown only when the session completes |
| Feedback | `{summary, findings[]}` validated by Python; browser also keeps formatted report text | Stored separately from practice turns in the completed Markdown file |
| Microphone and output audio | Browser memory and transient Python buffers | Released after use; no audio replay/history |
| Visibility and selected history | React memory | Reset on reload; hidden live text remains in transcript |
| Completed sessions | `data/conversations/*.md`, owned by Python | Read on startup, retained across app restarts; no database/index needed |
| Model assets | `models/`, Ollama's model store, frontend local vendor assets | Downloaded once during setup; reused offline |

No login, cloud storage, Redux, or hosted database is needed for this single-user local app.

## Local API and Dependency Contracts

### Browser to Python

All routes are local, under `/api`, using Vite's proxy. JSON requests carry a `request_id` where appropriate; responses echo it. The browser owns active conversation state, so stale server responses cannot mutate a session. API errors return `{error: {code, message, retryable}}` with a non-success HTTP status.

| Route | Request | Successful response |
| --- | --- | --- |
| `GET /api/health` | None | `{ready, checks: {ollama, chat_model, feedback_model, stt, tts, history_writable, vad_assets}, problems[]}` |
| `POST /api/transcribe` | `audio/wav`, mono PCM16 at 16 kHz | `{text, is_farewell, no_speech_prob}`; empty text means no usable speech; `no_speech_prob` is the duration-weighted model estimate that the capture was not speech |
| `POST /api/reply` | `{request_id, opening, turns[]}` | `{request_id, text}` |
| `POST /api/report` | `{request_id, turns[]}` | `{request_id, summary, findings[], report_text}` |
| `POST /api/speech` | `{request_id, text}` | `audio/wav` bytes; browser retains originating request ID |
| `POST /api/conversations` | `{id, created_at, completed_at, turns[], report_text}` | `{id, title, filename}` after atomic save |
| `GET /api/conversations` | None | `{sessions: [{id, title, completed_at}], warnings: [{filename, message}]}`; sessions newest first, per-file warnings displayed in the sidebar |
| `GET /api/conversations/{id}` | Generated UUID | `{id, title, markdown, turns: [{id, role, text, interrupted}], report_text}` or 404 |
| `DELETE /api/conversations/{id}` | Generated UUID | `{id, deleted, filename}`; removes only that one file inside the history directory |

Check request formats and bounded sizes before inference. Reasonable initial transport bounds are 10 MiB per audio upload and 2 MiB per session JSON; report excess clearly rather than truncating. Long-context handling operates within these generous POC transport bounds. Do not log conversation contents by default. Validation errors must not echo the submitted text back. Readiness also confirms the browser's local VAD/ONNX assets exist, so a missing `frontend/public/vendor/` copy is reported before practice starts rather than failing mid-session.

### Python to Ollama

`POST http://127.0.0.1:11434/api/chat`, no authentication for this loopback-only local service:

```json
{
  "model": "qwen3:4b-q4_K_M",
  "messages": [{"role": "system", "content": "task instructions"}, {"role": "user", "content": "conversation input"}],
  "stream": false,
  "think": false,
  "keep_alive": "10m",
  "options": {"num_ctx": 8192, "num_predict": 256, "temperature": 0.6}
}
```

Read `message.content`; require successful completion and nonempty output. For feedback, add the JSON Schema through `format`, lower temperature, and allow a larger output budget. Parse and validate structured output before use. Treat length-truncated/invalid results as incomplete, not a successful report; retry once or offer a visible retry. Check installed models with [`GET /api/tags`](https://docs.ollama.com/api/tags). Use a finite timeout (initially 90 seconds) and cancellation on obsolete requests where supported; immediate browser playback stopping never depends on Ollama cancellation.

### Downloads and Offline Assets

Runtime dependencies are local libraries and Ollama, not cloud APIs; there are no hosted inference charges or service quotas. Initial downloads come from npm/PyPI, Ollama's registry, and Hugging Face. They can fail or be throttled; setup must be rerunnable and verify complete files.

Use explicit local paths for faster-whisper and Piper. Set Hugging Face offline mode during runtime, and disable Ollama cloud features using its documented local configuration if supported by the installed version. Bundle VAD/ONNX model, worklet, WASM, and `.mjs` assets: the VAD integration otherwise defaults to CDN URLs. All runtime UI assets, including the robot and fonts, must resolve locally.

Piper is GPL-3.0; its voice models have separate model cards. Record model/software licenses and download sources in `models/README.md` when selecting tested versions. This spec does not choose a license for the learner's app or bundle third-party model weights into its public repository.

## File Structure

```text
speak-fluent/
├── README.md                         # Setup, startup, offline demo, history location
├── .gitignore                        # Exclude envs, weights, vendor copies, personal history
├── devpost/
│   ├── learner-profile.md            # Learning context (already locally ignored)
│   ├── scope.md                      # Approved product boundary
│   ├── prd.md                        # Approved behaviors
│   └── spec.md                       # This blueprint
├── frontend/
│   ├── package.json                  # dev/build scripts; postinstall copies VAD assets
│   ├── package-lock.json             # Tested dependency versions
│   ├── index.html                    # Local app entry
│   ├── vite.config.js                # React setup and /api loopback proxy
│   ├── scripts/copy-vad-assets.mjs    # Copy matching ONNX/WASM/worklet assets
│   ├── public/vendor/                # Generated local inference assets, ignored
│   └── src/
│       ├── main.jsx                  # React entry
│       ├── App.jsx                   # Layout and selected view
│       ├── App.module.css            # Sidebar/main layout
│       ├── global.css                # Reset, variables, system fonts
│       ├── components/
│       │   ├── ConversationView.jsx  # Start, live text, warnings, status
│       │   ├── ConversationView.module.css
│       │   ├── Robot.jsx             # Inline SVG and playback-driven balloon
│       │   ├── Robot.module.css
│       │   ├── HistorySidebar.jsx    # Completed session list
│       │   ├── HistorySidebar.module.css
│       │   ├── HistoryView.jsx       # Saved transcript and report using shared chat bubbles
│       │   ├── HistoryView.module.css
│       │   ├── Transcript.jsx        # Shared live/history bubbles and feedback report
│       │   └── Transcript.module.css
│       ├── hooks/useConversation.js # React binding for session orchestration
│       └── lib/
│           ├── api.js                # Local HTTP calls and typed-by-convention errors
│           ├── audio.js              # Silero capture, PCM WAV encoding, stoppable playback
│           └── conversation.js       # Testable session controller, ordering, cancellation
├── backend/
│   ├── __init__.py                    # Python package
│   ├── requirements.txt              # Pinned runtime and focused verification dependencies
│   ├── app.py                        # FastAPI endpoints and lifecycle
│   ├── schemas.py                    # Input, feedback, and response validation
│   ├── config.py                     # Repo-relative paths and model defaults
│   ├── speech.py                     # Persistent Whisper/Piper instances
│   ├── llm.py                        # Ollama requests, context budget, grounded reports
│   ├── prompts.py                    # Opening, practice, report prompts
│   ├── farewell.py                   # Clear closing-utterance matching
│   ├── spoken_text.py                # Emoji/emoticon handling for display and voice
│   └── history.py                    # Atomic Markdown save and read/list
├── scripts/download_models.py        # Online, rerunnable model setup only
├── scripts/download_voice.py         # Optional extra local voice for comparison
├── scripts/compare_voices.py         # Render one sentence per local voice
├── scripts/verify_speech.py          # Real-model API smoke check
├── models/
│   ├── README.md                     # Exact tested models, sources, licenses, sizes
│   ├── whisper-small.en/             # Downloaded model/tokenizer, ignored
│   └── piper/                        # Downloaded voice .onnx and .json, ignored
├── data/conversations/               # Personal Markdown files, ignored
└── tests/
    ├── test_farewell.py               # Closing intent versus incidental mention
    ├── test_history.py                # Restart persistence, idempotency, failed-write behavior
    ├── test_feedback.py               # Grounding, batching, incomplete-output rejection
    ├── test_runtime.py                # Cancellation, request bounds, service failures
    └── conversation.test.js           # Race, ordering, retry, and report-chunk checks
```

Existing learning/agent configuration folders are repository tooling, outside the application architecture. Generated dependency directories and the future build checklist are omitted from this planned app tree.

## Important Failure Modes

1. **Microphone or audio playback:** “Microphone unavailable. Allow microphone access in this browser and check your Linux input device, then retry.” If playback is blocked, offer an explicit Play/Retry action. Clear speaking animation whenever audio stops. Preserve active text while the page stays open. A microphone that disappears mid-session reports “Microphone disconnected” with a Retry microphone action.
2. **Missing, slow, or failed AI:** readiness names the missing model/service and the setup command. During runtime show “Local AI could not finish this reply/report. Check that Ollama is running, then retry.” Keep recognized turns; do not invent output or mark a failed report complete. Synthesis failures offer retry for the same generated text.
3. **History save/read failure:** “Your session is still open, but could not be saved. Check free disk space and data/conversations permissions, then retry.” A malformed/unreadable history file produces a visible per-file warning while other entries still load. Do not erase or replace it. An unwritable history folder fails readiness with that guidance instead of a session that looks finished.
4. **Browser assets missing:** readiness reports that the local VAD/ONNX copies are absent and names `npm --prefix frontend ci`. Practice must not start on a half-installed frontend.

## Verification and First Build Checkpoint

Implements every acceptance criterion in `prd.md > Features and Behavior`; addresses `prd.md > Open Questions`.

**First checkpoint: a real vertical speech loop before visual polish.** Download models, confirm Ollama GPU use with `ollama ps`, and connect Start → generated opening → voice → actual microphone recognition → relevant response. Then interrupt it using headphones. Include one deliberately imperfect sentence and check that an actual local report offers a sound correction. This proves the kernel; prerecorded/sample responses cannot substitute for it.

Record first/cached response delay, recognition delay, synthesis delay, interruption stop behavior, and whether the learner's pauses are cut off. The learner judges whether this supports natural practice; no numerical latency target was agreed. If base.en changes the learner's grammar or misses too much, try a larger local recognition model and measure again. If CPU speed or setup blocks the experience, revisit model placement and the time budget with the learner.

The combined offline audio, turn handling, and history requirements are ambitious for the scope's 2–4 active hours. Timebox the first integration investigation to roughly an hour of active work, excluding unattended downloads. This is a suggested build checkpoint, not a completion guarantee. If the kernel still fails or the total effort is clearly beyond budget, return to the learner for a scope/time decision; do not silently remove hands-free turns or interruption handling.

**Final live verification:**

- Reload with external internet disconnected; all model and browser assets load locally.
- Start without speaking and hear the AI opening.
- Complete several hands-free exchanges, including a relevant follow-up.
- Interrupt audible speech; it stops promptly, the interrupted turn is labeled, and the interrupting words drive the next reply. Also speak while a reply is still being generated; stale output must not play.
- Cough or make a brief noise over the AI voice; the reply must not be lost. If it pauses, it continues from the same point and no fake user turn appears.
- Say a short phrase such as “I’m doing well” quietly and at normal volume; each becomes a turn rather than being silently ignored.
- Hide/reveal AI text without affecting audio or saved transcript; animation follows actual playback, including the report.
- Say a clear farewell; hear feedback containing a real quote and useful correction. Check a clean sentence does not force a fabricated mistake.
- Finish, open history, inspect its Markdown file directly, and restart the app to confirm persistence.
- Start a second session; it gets its own file.
- Deny microphone permission, stop Ollama, and simulate an unwritable history folder in a test environment; failures must be visible and must not look completed.

Use focused automated tests for cancellation races, false-interruption resume, short-candidate acceptance, farewell false positives, feedback grounding, and durable/idempotent history. Browser microphone and actual model quality require manual verification. Build checks: `npm --prefix frontend run build`, `node --test tests/conversation.test.js`, and `.venv/bin/python -m pytest tests`. See [Node test runner](https://nodejs.org/api/test.html) and [pytest](https://docs.pytest.org/en/stable/).

## What Was Simplified and Why

- Familiar browser UI plus local Python services; one Linux machine and headphones are the agreed target setup.
- A 4B model serves live dialogue; an 8B model runs the two feedback passes after practice ends. One downloaded voice, with no model-picker interface.
- Completed sessions use readable files, fulfilling the PRD without database setup.
- Stop on detected interruption; situation-dependent decisions remain deferred per the PRD.
- Short whole-reply audio and request/response HTTP first; no continuous token/audio transport is needed to prove the loop, provided the latency check passes.
- No audio replay, account system, pronunciation grading, Android build, or deployment, following the approved POC boundary.

## Decisions and Open Issues

### Learner Decisions

- Familiar with HTML, CSS, Tailwind, JavaScript, Vite, React, and Python basics; no local AI or speech software installed.
- Agreed to React/Vite and Python, explicitly selected CSS Modules and plain CSS over Tailwind.
- Approved Ollama, faster-whisper, Piper, and Silero, and the proposed early speech-loop check.
- Always uses headphones for speaking practice.
- Review remains Markdown; no HTML companion is needed.

### Useful Learning Question

The profile asks how local apps run and “how AI can speak.” The planning conversation explained three separate steps: recognition converts voice to text, the language model writes a reply, and speech synthesis converts that reply into audio. This blueprint connects those steps to actual local processes. The agreed early speech-loop check will let the learner observe each stage and its delay; no comprehension quiz is required.

### Implementation Recommendations for This Review

FastAPI/HTTPX, browser-side Silero, the specific starting models/voice, Markdown file organization, active-session memory behavior, and the visual defaults are derived recommendations, not previously stated learner preferences. Approving this draft accepts these starting choices. Routine model settings can be tuned against the acceptance criteria; a consequential architecture or product-boundary change must return to the learner.

### Unverified Build Evidence

- GPU/driver identity and upstream compatibility documentation were checked; actual Ollama GPU execution, available runtime memory, CPU recognition speed, browser VAD bundling, voice quality, and end-to-end timing remain untested.
- Final compatible package versions and voice/model artifacts must be pinned after setup succeeds. No paid service or runtime network fallback is permitted.
- Feedback correctness and recognition fidelity need actual spoken examples. Exact quote validation is useful but insufficient on its own.
- The 2–4-hour goal remains uncertain. The early checkpoint must produce evidence and surface any necessary scope/time decision before the build expands.

There are no further interview questions needed for a draft review. Approval establishes a build plan with explicit feasibility checks, not a claim that those checks have already passed.
