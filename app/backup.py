"""Backups of the reviewer's work to the private Hugging Face dataset: every night at 03:00 Mauritius time, and a few
minutes after each (re)start. Skipped when nothing changed since the last one.

Each backup is a dated folder 05_review/platform/backups/<YYYY-MM-DD_HHMM>/ with
  reviews.db      a consistent snapshot of the database (SQLite backup API, safe while the app is writing)
  reviews.jsonl   the same work as readable JSON lines (what GET /api/export returns)
and the voice notes are kept in 05_review/platform/backups/voice/ (each note is uploaded once, never changes).
Restore: stop the app, put a reviews.db (and the voice/ files) back in DATA_DIR, start it again. See README.
"""
import hashlib
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import DATA_DIR, env

REPO = env("HF_DATASET", "devislandai/kreola-speech")
ROOT = env("HF_BACKUP_PATH", "05_review/platform/backups")
MU = timezone(timedelta(hours=4))  # Mauritius, no daylight saving
HOUR = int(env("BACKUP_HOUR", "3"))
STATE = DATA_DIR / ".last_backup"
_lock = threading.Lock()


def token():
    return env("HF_BACKUP_TOKEN") or env("HF_TOKEN")  # needs write access to the dataset


def snapshot(dest):
    src = sqlite3.connect(DATA_DIR / "reviews.db")
    out = sqlite3.connect(dest)
    with out:
        src.backup(out)
    src.close()
    out.close()


def run(reason, export_lines=None, force=False):
    """One backup. Returns a short status string (also printed to the server log)."""
    if not token():
        return "backup skipped: no HF_BACKUP_TOKEN / HF_TOKEN"
    with _lock:
        tmp = DATA_DIR / "_backup"
        tmp.mkdir(exist_ok=True)
        snapshot(tmp / "reviews.db")
        if export_lines is not None:
            (tmp / "reviews.jsonl").write_text(export_lines(), encoding="utf-8")
        voice = sorted((DATA_DIR / "voice").glob("*")) if (DATA_DIR / "voice").exists() else []
        digest = hashlib.sha256((tmp / "reviews.db").read_bytes() + "".join(f.name for f in voice).encode()).hexdigest()
        if not force and STATE.exists() and STATE.read_text() == digest:
            return f"backup skipped ({reason}): nothing changed"
        from huggingface_hub import CommitOperationAdd, HfApi
        api = HfApi(token=token())
        stamp = datetime.now(MU).strftime("%Y-%m-%d_%H%M")
        have = {f for f in api.list_repo_files(REPO, repo_type="dataset") if f.startswith(f"{ROOT}/voice/")}
        ops = [CommitOperationAdd(f"{ROOT}/{stamp}/{f.name}", str(f)) for f in sorted(tmp.iterdir())]
        ops += [CommitOperationAdd(f"{ROOT}/voice/{f.name}", str(f)) for f in voice if f"{ROOT}/voice/{f.name}" not in have]
        api.create_commit(REPO, repo_type="dataset", operations=ops, commit_message=f"Review backup {stamp} ({reason})")
        STATE.write_text(digest)
        for f in tmp.iterdir():
            f.unlink()
        return f"backup done ({reason}): {ROOT}/{stamp}, {len(ops)} files"


def _loop(export_lines):
    time.sleep(int(env("BACKUP_FIRST_DELAY", "300")))  # after a (re)start: let the app settle, then back up
    while True:
        try:
            print(run("after start" if not _loop.ran else "nightly", export_lines), flush=True)
        except Exception as e:  # a failed backup must never stop the app; it is retried next time
            print(f"backup FAILED: {e!r}"[:300], flush=True)
        _loop.ran = True
        now = datetime.now(MU)
        nxt = now.replace(hour=HOUR, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        time.sleep((nxt - now).total_seconds())


_loop.ran = False


def start(export_lines):
    if token():
        threading.Thread(target=_loop, args=(export_lines,), daemon=True, name="backup").start()
