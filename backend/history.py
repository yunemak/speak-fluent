"""Readable Markdown files, atomically saved; no database or transcript logs."""
import fcntl
import contextlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from .schemas import CompletedSession

MAX_FILE_BYTES = 4 * 1024 * 1024
SAVE_MESSAGE = "Your session is still open, but could not be saved. Check free disk space and data/conversations permissions, then retry."


class HistoryError(Exception):
    def __init__(self, message, code="history_unavailable", status=503):
        super().__init__(message)
        self.code = code
        self.status = status


TURN_HEADING = re.compile(r"^### (You|AI)\n\n", re.MULTILINE)
INTERRUPTED_MARKER = "*Interrupted — generated reply shown; not all words were spoken.*"


def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_transcript(markdown):
    """Turn the saved readable Markdown back into the chat transcript."""
    transcript_part, separator, report = markdown.rpartition("\n## Feedback Report\n")
    if not separator:
        raise ValueError("Missing feedback section; file left unchanged.")
    _, separator, transcript = transcript_part.partition("\n## Transcript\n")
    if not separator:
        raise ValueError("Missing transcript section; file left unchanged.")
    headings = list(TURN_HEADING.finditer(transcript))
    if not headings:
        raise ValueError("Transcript has no messages; file left unchanged.")
    turns = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(transcript)
        text = transcript[heading.end():end].strip("\n")
        interrupted = text.endswith(INTERRUPTED_MARKER)
        if interrupted:
            text = text[:-len(INTERRUPTED_MARKER)].rstrip("\n")
        turns.append({
            "role": "user" if heading.group(1) == "You" else "assistant",
            "text": text,
            "interrupted": interrupted,
        })
    return turns, report.strip()


def render(session):
    completed = session.completed_at.astimezone(timezone.utc)
    fallback = completed.strftime("Practice · %Y-%m-%d %H:%M:%S UTC")
    title = re.sub(r"\s+", " ", session.title).strip() or fallback
    metadata = {"format_version": 1, "id": str(session.id), "title": title,
                "created_at": utc(session.created_at), "completed_at": utc(session.completed_at)}
    parts = ["---", json.dumps(metadata, ensure_ascii=False), "---", "", f"# {title}", "", "## Transcript", ""]
    for turn in session.turns:
        parts.extend([f"### {'You' if turn.role == 'user' else 'AI'}", "", turn.text, ""])
        if turn.interrupted:
            parts.extend(["*Interrupted — generated reply shown; not all words were spoken.*", ""])
    parts.extend(["## Feedback Report", "", session.report_text, ""])
    return metadata, "\n".join(parts)


class ConversationStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()

    def check_writable(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=self.directory) as file:
            file.write(b"ready")
            file.flush()

    def _read(self, path):
        # Do not follow a history entry linked outside this store.
        if path.is_symlink() or path.resolve().parent != self.directory:
            raise ValueError("Linked history files are not supported; file left unchanged.")
        with path.open("r", encoding="utf-8") as file:
            markdown = file.read(MAX_FILE_BYTES + 1)
        if len(markdown.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("History file is too large; file left unchanged.")
        lines = markdown.split("\n", 3)
        if len(lines) != 4 or lines[0] != "---" or lines[2] != "---":
            raise ValueError("Invalid history header; file left unchanged.")
        try:
            metadata = json.loads(lines[1])
            session_id = str(UUID(metadata["id"]))
            completed = datetime.fromisoformat(metadata["completed_at"].replace("Z", "+00:00"))
            created = datetime.fromisoformat(metadata["created_at"].replace("Z", "+00:00"))
            if (metadata["format_version"] != 1 or not isinstance(metadata["title"], str)
                    or not metadata["title"].strip() or len(metadata["title"]) > 200
                    or completed.tzinfo is None or created.tzinfo is None or completed < created
                    or not path.name.endswith(f"-{session_id}.md")):
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ValueError("Invalid history metadata; file left unchanged.") from error
        if "\n## Transcript\n" not in lines[3] or "\n## Feedback Report\n" not in lines[3]:
            raise ValueError("Missing transcript or feedback section; file left unchanged.")
        metadata["id"] = session_id
        metadata["completed_at"] = utc(completed)
        return metadata, markdown

    def _matches(self, session_id):
        suffix = f"-{UUID(str(session_id))}.md"
        return sorted(path for path in self.directory.iterdir() if path.name.endswith(suffix)) if self.directory.exists() else []

    def save(self, session: CompletedSession):
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            metadata, markdown = render(session)
            stamp = session.completed_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            target = self.directory / f"{stamp}-{session.id}.md"
            # One lock per store serializes both threads and local server processes.
            # The lock is not a conversation and is never shown in the sidebar.
            with (self.directory / ".write.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                existing = self._matches(session.id)
                if existing:
                    if len(existing) != 1:
                        raise HistoryError("Multiple files have this session ID. Files were left unchanged.", "history_conflict", 409)
                    try:
                        saved, content = self._read(existing[0])
                    except (ValueError, UnicodeError) as error:
                        raise HistoryError("An existing session file could not be read. It was left unchanged.", "history_conflict", 409) from error
                    if content != markdown:
                        raise HistoryError("This session ID already belongs to different saved content. The existing file was left unchanged.", "history_conflict", 409)
                    return {"id": saved["id"], "title": saved["title"], "filename": existing[0].name}
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                                 prefix=".saving-", suffix=".tmp", delete=False) as file:
                    temporary = Path(file.name)
                    file.write(markdown)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, target)
                temporary = None
                # Persist the directory entry as well as the file's contents.
                directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            return {"id": str(session.id), "title": metadata["title"], "filename": target.name}
        except OSError as error:
            raise HistoryError(SAVE_MESSAGE, "history_save_failed") from error
        finally:
            if temporary is not None:
                with contextlib.suppress(OSError):
                    temporary.unlink(missing_ok=True)

    def list(self):
        sessions, warnings = [], []
        try:
            paths = sorted(path for path in self.directory.iterdir() if path.name.endswith(".md")) if self.directory.exists() else []
            seen = set()
            for path in paths:
                try:
                    metadata, _ = self._read(path)
                    if metadata["id"] in seen:
                        raise ValueError("Duplicate session ID; files left unchanged.")
                    seen.add(metadata["id"])
                    sessions.append({key: metadata[key] for key in ("id", "title", "completed_at")})
                except (OSError, UnicodeError, ValueError) as error:
                    message = str(error) if isinstance(error, ValueError) and not isinstance(error, UnicodeError) else "Could not read this history file. Check its format and permissions; it was left unchanged."
                    warnings.append({"filename": path.name, "message": message})
        except OSError as error:
            raise HistoryError("Could not list saved conversations. Check data/conversations permissions, then retry.") from error
        sessions.sort(key=lambda item: datetime.fromisoformat(item["completed_at"].replace("Z", "+00:00")), reverse=True)
        return {"sessions": sessions, "warnings": warnings}

    def get(self, session_id):
        try:
            paths = self._matches(session_id)
            if not paths:
                raise HistoryError("This saved conversation was not found.", "history_not_found", 404)
            if len(paths) != 1:
                raise ValueError("Duplicate session ID")
            metadata, markdown = self._read(paths[0])
            turns, report_text = parse_transcript(markdown)
            for index, turn in enumerate(turns):
                turn["id"] = f"{metadata['id']}:{index}"
            return {"id": metadata["id"], "title": metadata["title"], "completed_at": metadata["completed_at"],
                    "markdown": markdown, "turns": turns, "report_text": report_text}
        except (ValueError, OSError, UnicodeError) as error:
            raise HistoryError("Could not open this conversation. Check the file and its permissions; it was left unchanged.", "history_read_failed") from error

    def retitle(self, session_id, title):
        """Update only the readable title in the metadata and heading."""
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) > 80:
            raise HistoryError("A conversation title must be 1–80 characters.", "invalid_title", 400)
        try:
            with (self.directory / ".write.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                paths = self._matches(session_id)
                if not paths:
                    raise HistoryError("This saved conversation was not found.", "history_not_found", 404)
                if len(paths) != 1:
                    raise HistoryError("Several files share this session ID. No title was changed.", "history_conflict", 409)
                path = paths[0]
                if path.is_symlink() or path.resolve().parent != self.directory:
                    raise HistoryError("Linked history files are not supported; no title was changed.", "history_conflict", 409)
                metadata, markdown = self._read(path)
                if metadata["title"] == title:
                    return {"id": metadata["id"], "title": title, "filename": path.name}
                metadata["title"] = title
                lines = markdown.split("\n")
                lines[1] = json.dumps(metadata, ensure_ascii=False)
                for index in range(3, len(lines)):
                    if lines[index].startswith("# "):
                        lines[index] = f"# {title}"
                        break
                content = "\n".join(lines)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                                     prefix=".saving-", suffix=".tmp", delete=False) as file:
                        temporary = Path(file.name)
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                    os.replace(temporary, path)
                    temporary = None
                    directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                finally:
                    if temporary is not None:
                        with contextlib.suppress(OSError):
                            temporary.unlink(missing_ok=True)
                return {"id": metadata["id"], "title": title, "filename": path.name}
        except HistoryError:
            raise
        except (ValueError, OSError, UnicodeError) as error:
            raise HistoryError("Could not update this conversation title. Check the file and its permissions.",
                               "history_read_failed") from error

    def delete(self, session_id):
        """Remove one saved conversation. Only files inside this store are touched."""
        try:
            paths = self._matches(session_id)
            if not paths:
                raise HistoryError("This saved conversation was not found.", "history_not_found", 404)
            if len(paths) != 1:
                raise HistoryError("Several files share this session ID. Nothing was deleted.", "history_conflict", 409)
            path = paths[0]
            if path.is_symlink() or path.resolve().parent != self.directory:
                raise HistoryError("Linked history files are not supported; nothing was deleted.", "history_conflict", 409)
            path.unlink()
            return {"id": str(session_id), "deleted": True, "filename": path.name}
        except HistoryError:
            raise
        except (ValueError, OSError, UnicodeError) as error:
            raise HistoryError("Could not delete this conversation. Check the file and its permissions.", "history_delete_failed") from error
