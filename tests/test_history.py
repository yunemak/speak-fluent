import errno
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.history import ConversationStore, HistoryError
from backend.schemas import CompletedSession


def session(**updates):
    start = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
    return CompletedSession.model_validate({
        "id": str(uuid4()), "created_at": start, "completed_at": start + timedelta(minutes=3),
        "turns": [
            {"id": str(uuid4()), "role": "assistant", "text": "How was your day? 😊", "interrupted": True},
            {"id": str(uuid4()), "role": "user", "text": "Yesterday I go to the park."},
            {"id": str(uuid4()), "role": "user", "text": "Goodbye."},
        ],
        "report_text": 'Grammar: Try “Yesterday I went to the park.”',
        **updates,
    })


def test_readable_markdown_survives_new_store_and_preserves_interrupted_hidden_text(tmp_path):
    data = session()
    saved = ConversationStore(tmp_path).save(data)
    body = (tmp_path / saved["filename"]).read_text()
    assert body.startswith("---\n")
    assert "\n## Transcript\n" in body
    assert "### You\n" in body and "### AI\n" in body
    assert "How was your day? 😊" in body
    assert "Interrupted — generated reply shown; not all words were spoken." in body
    assert "\n## Feedback Report\n" in body and data.report_text in body
    restarted = ConversationStore(tmp_path)
    entry = restarted.get(data.id)
    assert entry["markdown"] == body
    assert [turn["role"] for turn in entry["turns"]] == ["assistant", "user", "user"]
    assert entry["turns"][0]["text"] == "How was your day? 😊"
    assert entry["turns"][0]["interrupted"] is True
    assert entry["turns"][1] == {"id": f"{data.id}:1", "role": "user",
                                 "text": "Yesterday I go to the park.", "interrupted": False}
    assert entry["report_text"] == data.report_text
    assert restarted.list()["sessions"][0]["id"] == str(data.id)


def test_saved_title_replaces_the_date_heading_and_can_be_retitled(tmp_path):
    store = ConversationStore(tmp_path)
    data = session(title="Differential Equations Chat")
    saved = store.save(data)
    body = (tmp_path / saved["filename"]).read_text()
    assert saved["title"] == "Differential Equations Chat"
    assert '# Differential Equations Chat\n' in body
    assert store.get(data.id)["title"] == "Differential Equations Chat"
    assert store.get(data.id)["completed_at"] == "2026-10-21T09:03:00Z"

    changed = store.retitle(data.id, "Math and Calculus Chat")
    assert changed["title"] == "Math and Calculus Chat"
    updated = (tmp_path / saved["filename"]).read_text()
    assert '# Math and Calculus Chat\n' in updated
    assert 'Differential Equations Chat' not in updated
    assert '## Transcript' in updated and data.report_text in updated
    assert store.get(data.id)["turns"][1]["text"] == "Yesterday I go to the park."


def test_retitle_rejects_invalid_titles_and_unknown_sessions(tmp_path):
    store = ConversationStore(tmp_path)
    data = session(title="A Good Title")
    store.save(data)
    for title in ["", "   ", "x" * 81]:
        with pytest.raises(HistoryError) as error:
            store.retitle(data.id, title)
        assert error.value.status == 400
    with pytest.raises(HistoryError) as error:
        store.retitle(uuid4(), "Missing Chat")
    assert error.value.status == 404


def test_blank_title_keeps_the_date_fallback(tmp_path):
    data = session(title="   ")
    saved = ConversationStore(tmp_path).save(data)
    assert saved["title"].startswith("Practice · 2026-10-21 09:03:00 UTC")


def test_two_sessions_newest_first_and_same_id_retry_is_idempotent(tmp_path):
    store = ConversationStore(tmp_path)
    first = session()
    later = session(completed_at=first.completed_at + timedelta(minutes=4))
    a, b = store.save(first), store.save(later)
    assert store.save(first) == a
    assert [row["id"] for row in store.list()["sessions"]] == [b["id"], a["id"]]
    assert len(list(tmp_path.glob("*.md"))) == 2


def test_same_id_with_changed_body_or_timestamp_never_overwrites_existing(tmp_path):
    store = ConversationStore(tmp_path)
    data = session()
    saved = store.save(data)
    before = (tmp_path / saved["filename"]).read_bytes()
    for changed in [data.model_copy(update={"report_text": "Different report"}),
                    data.model_copy(update={"completed_at": data.completed_at + timedelta(seconds=1)})]:
        with pytest.raises(HistoryError) as error:
            store.save(changed)
        assert error.value.status == 409
        assert (tmp_path / saved["filename"]).read_bytes() == before
    assert len(list(tmp_path.glob("*.md"))) == 1


def test_concurrent_retry_uses_one_atomic_file(tmp_path):
    data = session()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: ConversationStore(tmp_path).save(data), range(8)))
    assert all(result == results[0] for result in results)
    assert len(list(tmp_path.glob("*.md"))) == 1
    assert not list(tmp_path.glob(".saving-*.tmp"))


def test_failed_atomic_write_preserves_prior_files_and_retry_succeeds(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path)
    previous = store.save(session())
    before = (tmp_path / previous["filename"]).read_bytes()
    data = session()
    replace = os.replace

    def fail_replace(source, destination):
        raise OSError(errno.ENOSPC, "Test disk full")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(HistoryError, match="session is still open"):
        store.save(data)
    assert (tmp_path / previous["filename"]).read_bytes() == before
    assert len(list(tmp_path.glob("*.md"))) == 1
    assert not list(tmp_path.glob(".saving-*.tmp"))
    monkeypatch.setattr(os, "replace", replace)
    store.save(data)
    assert len(list(tmp_path.glob("*.md"))) == 2


def test_malformed_and_unreadable_files_warn_without_hiding_good_entries(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path)
    good = store.save(session())
    bad = tmp_path / "damaged.md"
    bad.write_text("not a valid saved conversation")
    unreadable = tmp_path / "unreadable.md"
    unreadable.write_text("private contents")
    original = Path.open

    def open_file(path, *args, **kwargs):
        if path == unreadable:
            raise PermissionError("test unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)
    result = store.list()
    assert [row["id"] for row in result["sessions"]] == [good["id"]]
    assert {row["filename"] for row in result["warnings"]} == {bad.name, unreadable.name}
    assert bad.read_text() == "not a valid saved conversation"
    assert "private contents" not in str(result)


def test_link_outside_history_is_neither_read_nor_overwritten(tmp_path):
    directory = tmp_path / "history"
    directory.mkdir()
    external = tmp_path / "outside.md"
    external.write_text("outside data")
    data = session()
    (directory / f"existing-{data.id}.md").symlink_to(external)
    store = ConversationStore(directory)
    assert len(store.list()["warnings"]) == 1
    with pytest.raises(HistoryError):
        store.get(data.id)
    with pytest.raises(HistoryError):
        store.save(data)
    assert external.read_text() == "outside data"


def test_delete_removes_only_the_requested_file(tmp_path):
    store = ConversationStore(tmp_path)
    first, second = session(), session()
    a, b = store.save(first), store.save(second)
    result = store.delete(first.id)
    assert result["deleted"] is True
    assert not (tmp_path / a["filename"]).exists()
    assert (tmp_path / b["filename"]).exists()
    assert [row["id"] for row in store.list()["sessions"]] == [str(second.id)]
    with pytest.raises(HistoryError) as error:
        store.delete(first.id)
    assert error.value.status == 404


def test_delete_rejects_unknown_ids_and_links_outside_the_store(tmp_path):
    directory = tmp_path / "history"
    directory.mkdir()
    external = tmp_path / "outside.md"
    external.write_text("outside data")
    data = session()
    (directory / f"existing-{data.id}.md").symlink_to(external)
    store = ConversationStore(directory)
    with pytest.raises(HistoryError):
        store.delete(data.id)
    assert external.read_text() == "outside data"
    with pytest.raises(HistoryError) as error:
        store.delete(uuid4())
    assert error.value.status == 404


def test_api_delete_removes_the_session_and_keeps_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "history", ConversationStore(tmp_path))
    data, other = session(), session()
    with TestClient(app_module.app) as client:
        for item in [data, other]:
            client.post("/api/conversations", json=item.model_dump(mode="json"))
        assert client.delete(f"/api/conversations/{data.id}").status_code == 200
        assert client.get(f"/api/conversations/{data.id}").status_code == 404
        assert client.get(f"/api/conversations/{other.id}").status_code == 200
        assert client.delete(f"/api/conversations/{data.id}").status_code == 404
        assert client.delete("/api/conversations/not-a-uuid").status_code == 422
        assert len(list(tmp_path.glob("*.md"))) == 1


def test_api_reload_lists_reads_and_retries_saved_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "history", ConversationStore(tmp_path))
    data, other = session(), session()
    with TestClient(app_module.app) as client:
        assert client.get("/api/conversations").json() == {"sessions": [], "warnings": []}
        for item in [data, other]:
            saved = client.post("/api/conversations", json=item.model_dump(mode="json"))
            assert saved.status_code == 200
    monkeypatch.setattr(app_module, "history", ConversationStore(tmp_path))
    with TestClient(app_module.app) as restarted:
        assert len(restarted.get("/api/conversations").json()["sessions"]) == 2
        response = restarted.get(f"/api/conversations/{data.id}")
        assert response.status_code == 200
        assert data.report_text in response.json()["markdown"]
        assert response.json()["report_text"] == data.report_text
        assert [turn["role"] for turn in response.json()["turns"]] == ["assistant", "user", "user"]
        assert restarted.post("/api/conversations", json=data.model_dump(mode="json")).status_code == 200
        assert len(list(tmp_path.glob("*.md"))) == 2
        assert restarted.get(f"/api/conversations/{uuid4()}").status_code == 404
        assert restarted.get("/api/conversations/not-a-uuid").status_code == 422
        payload = data.model_dump(mode="json")
        payload["id"] = "../../outside"
        assert restarted.post("/api/conversations", json=payload).status_code == 422


def test_api_save_failure_is_not_success(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path)
    monkeypatch.setattr(app_module, "history", store)

    def denied(_data):
        raise HistoryError("Your session is still open, but could not be saved.", "history_save_failed")

    monkeypatch.setattr(store, "save", denied)
    with TestClient(app_module.app) as client:
        response = client.post("/api/conversations", json=session().model_dump(mode="json"))
    assert response.status_code == 503
    assert response.json()["error"]["retryable"]
    assert not list(tmp_path.glob("*.md"))


def test_unwritable_history_probe_fails(tmp_path):
    directory = tmp_path / "history"
    directory.mkdir()
    directory.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            ConversationStore(directory).check_writable()
        with pytest.raises(HistoryError):
            ConversationStore(directory).save(session())
    finally:
        directory.chmod(0o700)
