import asyncio
import contextlib
import logging
import time
import wave
from uuid import UUID

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from . import llm
from .config import CHAT_MODEL, HISTORY_PATH, OLLAMA_URL, VOICE_PATH, WHISPER_PATH
from .farewell import is_farewell
from .schemas import CompletedSession, ReplyRequest, ReportRequest, SpeechRequest
from .speech import Speech
from .history import ConversationStore, HistoryError

app = FastAPI(title="Speak Fluent", docs_url=None, redoc_url=None)
speech = Speech()
history = ConversationStore(HISTORY_PATH)
recognition_lock = asyncio.Lock()
voice_lock = asyncio.Lock()
logger = logging.getLogger("uvicorn.error")


def failure(code, message, status=503, retryable=True):
    return JSONResponse({"error": {"code": code, "message": message, "retryable": retryable}}, status_code=status)


@app.exception_handler(RequestValidationError)
async def validation_error(_request, _error):
    # Do not echo personal transcript/audio back in validation logs or errors.
    return failure("invalid_request", "The request format is invalid. Reload the app and retry.", 422, False)


@app.exception_handler(llm.ModelError)
async def model_error(_request, error):
    return failure("model_failed", str(error))


@app.exception_handler(HistoryError)
async def history_error(_request, error):
    return failure(error.code, str(error), error.status, error.status == 503)


@app.middleware("http")
async def limit_body(request, call_next):
    limit = 10 * 1024 * 1024 if request.url.path == "/api/transcribe" else 2 * 1024 * 1024
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return failure("too_large", "This input is too large. Try a shorter turn or session.", 413, False)
        request._body = bytes(body)
    return await call_next(request)


async def until_disconnect(request, operation):
    """Cancel outgoing HTTP work; CPU work retains its lock until it really ends."""
    task = asyncio.create_task(operation)
    try:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                return Response(status_code=499)
            await asyncio.wait({task}, timeout=0.1)
        return await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def cpu(request, lock, function, *args):
    if await request.is_disconnected():
        raise asyncio.CancelledError
    async with lock:
        if await request.is_disconnected():
            raise asyncio.CancelledError
        work = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            # Shield alone is insufficient: keep the lock while the thread runs.
            with contextlib.suppress(Exception):
                await work
            raise


@app.get("/api/health")
async def health(request: Request):
    checks = {"ollama": False, "chat_model": False, "stt": False, "tts": False, "history_writable": False}
    problems = []
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            result = await client.get(f"{OLLAMA_URL}/api/tags")
            result.raise_for_status()
            checks["ollama"] = True
            checks["chat_model"] = any(model["name"] == CHAT_MODEL for model in result.json()["models"])
        if not checks["chat_model"]:
            problems.append(f"Download the conversation model: ollama pull {CHAT_MODEL}")
    except (httpx.HTTPError, ValueError, KeyError):
        problems.append("Start Ollama: OLLAMA_NO_CLOUD=1 ollama serve")
    for key, path, loader, lock in [
        ("stt", WHISPER_PATH / "model.bin", speech.load_recognizer, recognition_lock),
        ("tts", VOICE_PATH, speech.load_voice, voice_lock),
    ]:
        try:
            if not path.is_file():
                raise FileNotFoundError
            await cpu(request, lock, loader)
            checks[key] = True
        except Exception:
            problems.append(f"Could not load {key} model. Run .venv/bin/python scripts/download_models.py and retry.")
    try:
        await asyncio.to_thread(history.check_writable)
        checks["history_writable"] = True
    except OSError:
        problems.append("History is not writable. Check free disk space and data/conversations permissions, then retry.")
    return {"ready": all(checks.values()), "checks": checks, "problems": problems}


@app.post("/api/conversations")
async def save_conversation(data: CompletedSession):
    return await asyncio.to_thread(history.save, data)


@app.get("/api/conversations")
async def list_conversations():
    return await asyncio.to_thread(history.list)


@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: UUID):
    return await asyncio.to_thread(history.get, session_id)


@app.post("/api/transcribe")
async def transcribe(request: Request):
    if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
        return failure("invalid_audio", "Send audio/wav microphone input.", 415, False)
    audio = await request.body()

    async def operation():
        started = time.monotonic()
        try:
            text = await cpu(request, recognition_lock, speech.transcribe, audio)
        except (ValueError, wave.Error, EOFError):
            return failure("invalid_audio", "Use mono PCM16 WAV audio at 16 kHz.", 422, False)
        except Exception:
            return failure("recognition_failed", "Local speech recognition failed. Check model setup, then retry this turn.")
        logger.info("Recognition completed in %.2fs", time.monotonic() - started)
        return {"text": text, "is_farewell": is_farewell(text)}

    return await until_disconnect(request, operation())


@app.post("/api/reply")
async def reply(data: ReplyRequest, request: Request):
    async def operation():
        started = time.monotonic()
        text = await llm.reply(data.turns, data.opening)
        logger.info("Reply completed in %.2fs", time.monotonic() - started)
        return {"request_id": data.request_id, "text": text}
    return await until_disconnect(request, operation())


@app.post("/api/report")
async def report(data: ReportRequest, request: Request):
    async def operation():
        started = time.monotonic()
        result = await llm.report(data.turns)
        logger.info("Report completed in %.2fs", time.monotonic() - started)
        return {"request_id": data.request_id, **result}
    return await until_disconnect(request, operation())


@app.post("/api/speech")
async def synthesize(data: SpeechRequest, request: Request):
    async def operation():
        started = time.monotonic()
        try:
            audio = await cpu(request, voice_lock, speech.synthesize, data.text)
        except Exception:
            return failure("synthesis_failed", "Local voice could not speak this text. Check the Piper model, then retry.")
        logger.info("Synthesis completed in %.2fs", time.monotonic() - started)
        return Response(audio, media_type="audio/wav")
    return await until_disconnect(request, operation())
