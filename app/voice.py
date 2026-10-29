"""Voice notes: keep the recording, and transcribe it with myt ASR (handles English and French) so Claude can read it."""
import subprocess
import time
import uuid

import httpx

from . import store
from .config import DATA_DIR, MYT_BASE, MYT_KEY

VOICE = DATA_DIR / "voice"


def save(raw, clip_id, word):
    VOICE.mkdir(parents=True, exist_ok=True)
    name = f"{clip_id}_{uuid.uuid4().hex[:8]}"
    src = VOICE / f"{name}.webm"
    src.write_bytes(raw)
    playable(src)
    transcript = transcribe(src)
    store.q("insert into voice(clip_id, word, file, transcript, created_at) values(?,?,?,?,?)",
            (clip_id, word, src.name, transcript, time.time()))
    return store.q("select * from voice where file=?", (src.name,), one=True)


def playable(path):
    """An MP3 copy next to the recording: Chrome records WebM, iPhones record MP4, and not every browser plays both."""
    mp3 = path.with_suffix(".mp3")
    if not mp3.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-b:a", "64k", str(mp3)], check=True)
    return mp3


def transcribe(path):
    if not (MYT_KEY and MYT_BASE):
        return ""
    # to a real file, not a pipe: piped FLAC has no length in its header and myt then reads it as hours long
    tmp = path.with_suffix(".flac")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", str(tmp)], check=True)
    flac = tmp.read_bytes()
    tmp.unlink()
    try:
        r = httpx.post(f"{MYT_BASE}/audio/transcriptions", headers={"Authorization": f"Bearer {MYT_KEY}"},
                       files={"file": ("note.flac", flac, "audio/flac")},
                       data={"model": "myt/myt_asr", "response_format": "json"}, timeout=httpx.Timeout(120, connect=10))
        return r.json().get("text", "").strip() if r.status_code == 200 else ""
    except httpx.HTTPError:
        return ""  # the recording is kept either way; only the transcript is missing
