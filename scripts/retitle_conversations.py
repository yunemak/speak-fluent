"""Give existing saved conversations short topic titles.

Run with Ollama started: .venv/bin/python scripts/retitle_conversations.py
Use --dry-run to print the proposed titles without changing any files.
Only date-style titles are migrated; transcript and feedback content is untouched.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import llm
from backend.config import HISTORY_PATH
from backend.history import ConversationStore

DATE_TITLE = re.compile(r"^Practice · \d{4}-\d{2}-\d{2} ")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print titles without saving them.")
    args = parser.parse_args()

    store = ConversationStore(HISTORY_PATH)
    listing = store.list()
    for warning in listing["warnings"]:
        print(f"Warning: {warning['filename']}: {warning['message']}")
    pending = [session for session in listing["sessions"] if DATE_TITLE.match(session["title"])]
    print(f"{len(pending)} date-titled conversation(s) to summarize.")
    for session in pending:
        try:
            entry = store.get(session["id"])
            title = await llm.title(entry["turns"])
        except Exception as error:
            print(f"Skipped {session['title']}: {error}")
            continue
        if not title:
            print(f"Skipped {session['title']}: the local model returned no title.")
            continue
        print(f"{session['title']}  ->  {title}")
        if not args.dry_run:
            store.retitle(session["id"], title)


if __name__ == "__main__":
    asyncio.run(main())
