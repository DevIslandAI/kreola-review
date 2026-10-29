"""Choose the 10 hours to review and cut their audio (run once, on the PC that has the Kreola dataset).

  python tools/build_review_set.py            -> DATA_DIR/review_set.json + DATA_DIR/audio/<excerpt>.mp3

Rules (PLATFORM_PLAN.md):
  - units are excerpts of 1.5-3 min of consecutive usable clips from one recording (whole video when it is short);
  - same mix of recording types (families) as the dataset; language Kreol 8 h, French 1.5 h, English 0.5 h;
  - difficulty hard 4 h, typical 4 h, easy 2 h (hard = poor audio-text match, guessed numbers, music,
    language switching, suspected translation, myt repetition loops);
  - exam = 2 h from whole recordings that never appear in the 8 teaching hours.
Inputs: KREOLA_STAGE (default ../kreola-data/staging/kreola-speech). Output: DATA_DIR (default ../kreola-data/00_review/platform/data).
"""
import json
import os
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
STAGE = Path(os.environ.get("KREOLA_STAGE", HERE.parent / "kreola-data" / "staging" / "kreola-speech"))
DATA = Path(os.environ.get("DATA_DIR", HERE.parent / "kreola-data" / "00_review" / "platform" / "data"))
TOTAL, EXAM = 36000.0, 7200.0
LANG_T = {"mfe_Latn": 8 / 10, "fra_Latn": 1.5 / 10, "eng_Latn": 0.5 / 10}
DIFF_T = {"hard": .4, "typ": .4, "easy": .2}
MIN_S, PREF_S, MAX_S = 75.0, 120.0, 180.0
SEED = 29
LOOP = re.compile(r"\b((?:\w+\s+){1,4}?)\1{3,}", re.I)


def load():
    clean = {r["clip_id"]: r for r in map(json.loads, (STAGE / "03_asr_drafts" / "myt_drafts_clean.jsonl").open(encoding="utf-8"))}
    sources = {r["source_id"]: r for r in map(json.loads, filter(str.strip, (STAGE / "sources.jsonl").read_text(encoding="utf-8").split("\n")))}
    recs = defaultdict(list)
    for f in sorted((STAGE / "04_synchronized").glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                recs[r["source_id"]].append(r)
    return clean, sources, recs


def excerpts(rows):
    """Consecutive usable clips cut into excerpts of about 2 minutes."""
    out, cur = [], []
    def close():
        if cur and (sum(dur(r) for r in cur) >= MIN_S or (not out and len(rows) == len(cur))):
            out.append(list(cur))
        cur.clear()
    for r in sorted(rows, key=lambda r: r["sequence"]):
        ok = r["alignment_status"] == "pending_review" and r["language"] != "empty" and r["words"]
        if not ok or (cur and r["source_start_seconds"] - cur[-1]["source_end_seconds"] > 2.0):
            close()
            if not ok:
                continue
        cur.append(r)
        if sum(dur(x) for x in cur) >= PREF_S or len(cur) >= 8:
            close()
    close()
    return [e for e in out if sum(dur(r) for r in e) <= MAX_S + 30]


def dur(r):
    return r["source_end_seconds"] - r["source_start_seconds"]


def weak(w, low):
    """A word the aligner placed poorly, or could not score at all: worth a second listen."""
    return w["score"] is None or w["score"] <= low


def features(ex, clean, low):
    d = sum(map(dur, ex))
    words = [w for r in ex for w in r["words"]]
    by_lang = defaultdict(float)
    for r in ex:
        by_lang[r["language"]] += dur(r)
    lang = max(by_lang, key=by_lang.get)
    flags = [f for r in ex for f in r["quality_flags"] + clean.get(r["clip_id"], {}).get("flags", [])]
    text = " ".join(r["draft_text"] for r in ex)
    score = (2.0 * sum(weak(w, low) for w in words) / max(1, len(words))
             + .25 * sum(f.startswith("numbers") for f in flags) / len(ex)
             + .25 * flags.count("music_bg") / len(ex)
             + .3 * (len(by_lang) > 1)
             + .5 * ("suspect_translation" in flags)
             + .5 * bool(LOOP.search(text)))
    return d, lang, sorted(by_lang), score


def pick(cands, target, used_sources, per_source, fam_share):
    """Greedy fill under three quotas at once (family, language, difficulty), loosening the slack if short."""
    got, fill = [], defaultdict(float)
    quota = {**{("fam", f): s * target for f, s in fam_share.items()},
             **{("lang", l): s * target for l, s in LANG_T.items()},
             **{("diff", k): s * target for k, s in DIFF_T.items()}}
    per = defaultdict(int)
    cands = sorted(cands, key=lambda c: c["language"] == "mfe_Latn")  # French/English are rarer: they choose first
    for slack in (1.0, 1.1, 1.25):
        for c in cands:
            if c["id"] in {g["id"] for g in got} or c["source_id"] in used_sources or per[c["source_id"]] >= per_source:
                continue
            keys = [("fam", c["family"]), ("lang", c["language"]), ("diff", c["difficulty"])]
            if all(fill[k] + c["duration"] <= quota.get(k, 0) * slack for k in keys):
                got.append(c)
                per[c["source_id"]] += 1
                for k in keys:
                    fill[k] += c["duration"]
            if sum(g["duration"] for g in got) >= target:
                return got
    return got


def main():
    clean, sources, recs = load()
    scores = np.array([w["score"] for rows in recs.values() for r in rows for w in r["words"] if w["score"] is not None])
    low = float(np.percentile(scores, 10))
    cands = []
    for sid, rows in recs.items():
        for k, ex in enumerate(excerpts(rows)):
            d, lang, langs, score = features(ex, clean, low)
            cands.append({"id": f"{sid}__{k:02d}", "source_id": sid, "family": ex[0]["family"], "category": ex[0]["category"],
                          "platform": ex[0]["platform"], "language": lang, "languages": langs, "duration": round(d, 2),
                          "score": score, "clips": ex})
    sc = np.array([c["score"] for c in cands])
    hi, lo = np.percentile(sc, 70), np.percentile(sc, 30)
    for c in cands:
        c["difficulty"] = "hard" if c["score"] >= hi else "easy" if c["score"] <= lo else "typ"
    fam = defaultdict(float)
    for rows in recs.values():
        for r in rows:
            if r["alignment_status"] == "pending_review":
                fam[r["family"]] += dur(r)
    fam_share = {f: h / sum(fam.values()) for f, h in fam.items()}

    rnd = random.Random(SEED)
    rnd.shuffle(cands)
    exam = pick(cands, EXAM, set(), 4, fam_share)
    exam_src = {c["source_id"] for c in exam}
    teach = pick(cands, TOTAL - EXAM, exam_src, 2, fam_share)
    for c in exam:
        c["split"] = "exam"
    for c in teach:
        c["split"] = "teach"

    # mixed order: hard, typical, hard, typical, easy... so every session has all three; exam items fall where they land
    pools = {d: [c for c in teach + exam if c["difficulty"] == d] for d in DIFF_T}
    for p in pools.values():
        rnd.shuffle(p)
    order = []
    while any(pools.values()):
        for d in ("hard", "typ", "hard", "typ", "easy"):
            if pools[d]:
                order.append(pools[d].pop())
    out = []
    (DATA / "audio").mkdir(parents=True, exist_ok=True)
    for n, c in enumerate(order, 1):
        ex = c.pop("clips")
        t0 = ex[0]["source_start_seconds"]
        clips = []
        for r in ex:
            cl = clean.get(r["clip_id"], {})
            toks = [{"t": w["text"], "s": round(w["start_seconds"], 3), "e": round(w["end_seconds"], 3), "low": weak(w, low)} for w in r["words"]]
            k = 0
            for ch in cl.get("changes", []):  # the clean-up's automatic fixes, applied in place (as in the prototype)
                for j in range(k, len(toks)):
                    if toks[j]["t"] == ch["from"]:
                        toks[j]["auto"] = ch["to"]
                        k = j + 1
                        break
            clips.append({"clip_id": r["clip_id"], "offset": round(r["source_start_seconds"] - t0, 3), "dur": round(dur(r), 3),
                          "language": r["language"], "flags": sorted(set(r["quality_flags"] + cl.get("flags", []))), "tokens": toks})
        src = sources.get(c["source_id"], {})
        c.update(n=n, title=src.get("title", c["source_id"]), publisher=src.get("publisher", ""), clips=clips, score=round(c["score"], 3))
        out.append(c)
        mp3 = DATA / "audio" / f"{c['id']}.mp3"
        if not mp3.exists() and not os.environ.get("DRY"):  # DRY=1: check the selection without cutting audio
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(ex[-1]["source_end_seconds"] - t0),
                            "-i", str(STAGE / src["original_file"]), "-ac", "1", "-b:a", "48k", str(mp3)], check=True)
        if n % 25 == 0:
            print(f"  audio {n}/{len(order)}", flush=True)
    summary = {"excerpts": len(out), "hours": round(sum(c["duration"] for c in out) / 3600, 2), "low_word_score": low,
               **{f"{k}_{v}": round(sum(c["duration"] for c in out if c[k] == v) / 3600, 2)
                  for k in ("split", "language", "difficulty", "family") for v in sorted({c[k] for c in out})}}
    (DATA / "review_set.json").write_text(json.dumps({"summary": summary, "excerpts": out}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
