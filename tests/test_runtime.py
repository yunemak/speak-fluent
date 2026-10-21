import asyncio
import threading

import httpx
from fastapi.testclient import TestClient

from backend import app as service, llm


class ConnectedRequest:
    async def is_disconnected(self):
        return False


def test_canceled_cpu_request_holds_lock_until_inference_finishes():
    async def scenario():
        lock = asyncio.Lock()
        started, release, second_started = threading.Event(), threading.Event(), threading.Event()

        def first():
            started.set()
            assert release.wait(5)

        def second():
            second_started.set()
            return "second"

        request = ConnectedRequest()
        running = asyncio.create_task(service.cpu(request, lock, first))
        assert await asyncio.to_thread(started.wait, 2)
        running.cancel()
        try:
            await running
        except asyncio.CancelledError:
            pass
        assert lock.locked()
        next_request = asyncio.create_task(service.cpu(request, lock, second))
        await asyncio.sleep(0)
        assert not second_started.is_set()
        release.set()
        assert await next_request == "second"
        assert not lock.locked()

    asyncio.run(scenario())


def test_canceled_queued_cpu_request_never_runs():
    async def scenario():
        lock = asyncio.Lock()
        await lock.acquire()
        calls = []
        queued = asyncio.create_task(service.cpu(ConnectedRequest(), lock, lambda: calls.append("ran")))
        await asyncio.sleep(0)
        queued.cancel()
        try:
            await queued
        except asyncio.CancelledError:
            pass
        lock.release()
        await asyncio.gather(*service.cpu_tasks, return_exceptions=True)
        assert calls == []

    asyncio.run(scenario())


def test_disconnect_cancels_outbound_operation():
    async def scenario():
        started, canceled = asyncio.Event(), asyncio.Event()

        class Request:
            async def is_disconnected(self):
                return started.is_set()

        async def operation():
            started.set()
            try:
                await asyncio.Future()
            finally:
                canceled.set()

        result = await service.until_disconnect(Request(), operation())
        assert result.status_code == 499
        assert canceled.is_set()

    asyncio.run(scenario())


def test_oversized_and_invalid_inputs_fail_before_inference(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid request reached model inference")

    monkeypatch.setattr(service.speech, "transcribe", unexpected)
    with TestClient(service.app) as client:
        response = client.post('/api/transcribe', content=b'0' * (10 * 1024 * 1024 + 1), headers={'Content-Type':'audio/wav'})
        assert response.status_code == 413
        assert client.post('/api/reply', content=b' ' * (2 * 1024 * 1024 + 1)).status_code == 413
        assert client.post('/api/transcribe', content=b'invalid', headers={'Content-Type':'audio/mpeg'}).status_code == 415
        response = client.post('/api/reply', json={'request_id':'x','turns':[{'text':'PRIVATE TEST TEXT'}]})
        assert response.status_code == 422
        assert 'PRIVATE TEST TEXT' not in response.text


def test_unavailable_ollama_returns_actionable_error(monkeypatch):
    class UnavailableClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError('Connection refused')

    monkeypatch.setattr(llm.httpx, 'AsyncClient', UnavailableClient)
    with TestClient(service.app) as client:
        response = client.post('/api/reply', json={'request_id':'offline-failure','opening':True,'turns':[]})
    assert response.status_code == 503
    assert response.json()['error']['retryable']
    assert 'Ollama' in response.json()['error']['message']
