"""First start on a new server: fetch the review set and its audio from the private Hugging Face dataset.

Only runs when DATA_DIR is missing review_set.json or some of the audio; your reviews (reviews.db, voice/) are never touched.
Needs HF_TOKEN (read access to the dataset). The files were uploaded from kreola-data/00_review/platform/data on 29 Oct 2026.
"""
import json
import shutil

from .config import DATA_DIR, env

REPO = env("HF_DATASET", "devislandai/kreola-speech")
PATH = env("HF_REVIEW_PATH", "05_review/platform")


def missing():
    s = DATA_DIR / "review_set.json"
    if not s.exists():
        return True
    want = {e["id"] for e in json.loads(s.read_text(encoding="utf-8"))["excerpts"]}
    have = {f.stem for f in (DATA_DIR / "audio").glob("*.mp3")} if (DATA_DIR / "audio").exists() else set()
    return bool(want - have)


def ensure_data():
    if not missing():
        return
    token = env("HF_TOKEN")
    if not token:
        raise SystemExit(f"{DATA_DIR} has no review set (or misses audio) and HF_TOKEN is not set to download it from {REPO}")
    from huggingface_hub import snapshot_download
    print(f"Downloading the review set and audio from {REPO}/{PATH} …", flush=True)
    tmp = DATA_DIR / "_download"
    snapshot_download(REPO, repo_type="dataset", token=token, local_dir=tmp,
                      allow_patterns=[f"{PATH}/review_set.json", f"{PATH}/audio/*.mp3"])
    (DATA_DIR / "audio").mkdir(parents=True, exist_ok=True)
    for f in (tmp / PATH / "audio").glob("*.mp3"):
        f.replace(DATA_DIR / "audio" / f.name)
    (tmp / PATH / "review_set.json").replace(DATA_DIR / "review_set.json")
    shutil.rmtree(tmp, ignore_errors=True)
    print("Review data ready.", flush=True)
