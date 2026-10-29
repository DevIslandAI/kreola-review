"""Kreola Review: the web app where the 10 golden hours are reviewed.

  uvicorn app.main:app --port 8765        (from the repository folder)
"""
import hmac
import json
from collections import Counter, defaultdict

import anthropic
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import lookup, store, voice
from .config import CLAUDE_MAX_USD, DATA_DIR, HOSTED, PASSWORD, REVIEWER, ROOT, SESSION_SECRET

SET = json.loads((DATA_DIR / "review_set.json").read_text(encoding="utf-8"))
EXCERPTS = {e["id"]: e for e in SET["excerpts"]}
CLIPS = {c["clip_id"]: (e, c) for e in SET["excerpts"] for c in e["clips"]}

app = FastAPI(title="Kreola Review", docs_url=None, redoc_url=None)


@app.middleware("http")
async def login_required(request: Request, call_next):
    p = request.url.path
    if PASSWORD and p.startswith("/api/") and p not in ("/api/login", "/api/me") and not request.session.get("ok"):
        return JSONResponse({"detail": "login"}, status_code=401)
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 30, same_site="lax", https_only=HOSTED)


class Login(BaseModel):
    password: str


@app.get("/api/me")
def me(request: Request):
    return {"ok": not PASSWORD or bool(request.session.get("ok")), "name": REVIEWER}


@app.post("/api/login")
def login(body: Login, request: Request):
    if not PASSWORD or hmac.compare_digest(body.password, PASSWORD):
        request.session["ok"] = True
        return {"ok": True}
    raise HTTPException(401, "Wrong password")


def final_words(clip, state):
    """The clip's text as the reviewer left it: their edits, else the clean-up's fix, else myt's word."""
    edits = (state or {}).get("edits", {})
    out = []
    for i, t in enumerate(clip["tokens"]):
        e = edits.get(str(i), {})
        if not e.get("gone"):
            out.append(e.get("show") or t.get("auto") or t["t"])
    return out


@app.get("/api/overview")
def overview():
    states = store.clip_states()
    hours = defaultdict(float)
    items = []
    for e in SET["excerpts"]:
        done = sum(1 for c in e["clips"] if (states.get(c["clip_id"]) or {}).get("verdict"))
        touched = any(c["clip_id"] in states for c in e["clips"])
        for c in e["clips"]:
            if (states.get(c["clip_id"]) or {}).get("verdict"):
                hours["all"] += c["dur"]
                hours[e["language"]] += c["dur"]
                hours[e["difficulty"]] += c["dur"]
        items.append({k: e[k] for k in ("id", "n", "title", "category", "family", "language", "languages", "difficulty", "duration")}
                     | {"clips": len(e["clips"]), "done": done,
                        "status": "done" if done == len(e["clips"]) else "half" if touched else "todo"})
    total = defaultdict(float)
    for e in SET["excerpts"]:
        for k in ("family", "language", "difficulty"):
            total[e[k]] += e["duration"]
    fixed = sum(len(s["edits"]) for s in states.values())
    notes = store.q("select count(*) n from voice", one=True)["n"]
    return {"name": REVIEWER, "hours_done": hours["all"] / 3600, "hours_total": sum(e["duration"] for e in SET["excerpts"]) / 3600,
            "done_hours": {k: v / 3600 for k, v in hours.items()}, "total_hours": {k: v / 3600 for k, v in total.items()},
            "words_fixed": fixed, "voice_notes": notes, "excerpts": items}


@app.get("/api/excerpt/{eid}")
def excerpt(eid: str):
    e = EXCERPTS.get(eid)
    if not e:
        raise HTTPException(404)
    states = store.clip_states(eid)
    notes = defaultdict(list)
    for v in store.q("select id, clip_id, word, transcript from voice where clip_id in (%s)" % ",".join("?" * len(e["clips"])),
                     [c["clip_id"] for c in e["clips"]]):
        notes[v["clip_id"]].append(v)
    return {**{k: v for k, v in e.items() if k != "clips"},
            "clips": [{**c, "state": states.get(c["clip_id"]), "voice": notes[c["clip_id"]]} for c in e["clips"]]}


@app.get("/api/audio/{eid}")
def audio(eid: str):
    f = DATA_DIR / "audio" / f"{eid}.mp3"
    if eid not in EXCERPTS or not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="audio/mpeg")


class ClipState(BaseModel):
    verdict: str | None = None  # ok | fixed | skip
    edits: dict = {}            # word position -> {show, gone, why[], note}
    why: list = []              # reasons for the whole clip
    note: str = ""
    seconds: float = 0


@app.put("/api/clip/{clip_id}")
def put_clip(clip_id: str, s: ClipState):
    if clip_id not in CLIPS:
        raise HTTPException(404)
    store.save_clip(clip_id, CLIPS[clip_id][0]["id"], s.verdict, s.edits, s.why, s.note, max(0, min(s.seconds, 3600)))
    return {"ok": True}


@app.get("/api/translate")
def translate(q: str, src: str = "fr", lang: str = "mfe"):
    """Instant translations from the dictionary (free); Claude is only called by POST /api/ask."""
    if src not in lookup.LANGS or lang not in lookup.LANGS:
        raise HTTPException(400)
    own = lookup.kreol_hits(q, 1) if src == "mfe" else []
    return {"source_definition": own[0]["en"] if own and lookup.fold(own[0]["w"]) == lookup.fold(q) else "",
            "options": lookup.translate_local(q, src, lang)}


class Ask(BaseModel):
    q: str
    src: str = "fr"
    lang: str
    context: str = ""
    clip_id: str = ""


@app.post("/api/ask")
def ask(a: Ask):
    if a.lang not in lookup.LANGS or a.src not in lookup.LANGS or not a.q.strip():
        raise HTTPException(400)
    try:
        lid, sdef, options = lookup.ask(a.q.strip()[:200], a.src, a.lang, a.context[:600], a.clip_id)
    except lookup.BudgetReached as e:
        raise HTTPException(402, str(e))
    except anthropic.RateLimitError:
        raise HTTPException(429, "Claude is busy, try again in a minute")
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        raise HTTPException(502, f"Claude is unavailable ({getattr(e, 'status_code', 'network')})")
    return {"id": lid, "source_definition": sdef, "options": options, "spent": store.spent(), "budget": CLAUDE_MAX_USD}


class Choose(BaseModel):
    id: int
    text: str


@app.post("/api/ask/choose")
def choose(c: Choose):
    store.q("update lookups set chosen=? where id=?", (c.text, c.id))
    return {"ok": True}


@app.post("/api/voice")
async def add_voice(file: UploadFile = File(...), clip_id: str = Form(...), word: int | None = Form(None)):
    if clip_id not in CLIPS:
        raise HTTPException(404)
    raw = await file.read()
    if len(raw) > 20_000_000:
        raise HTTPException(413)
    return voice.save(raw, clip_id, word)


@app.get("/api/voice/{vid}")
def get_voice(vid: int):
    v = store.q("select file from voice where id=?", (vid,), one=True)
    if not v:
        raise HTTPException(404)
    return FileResponse(voice.VOICE / v["file"], media_type="audio/webm")


@app.get("/api/learning")
def learning():
    states = store.clip_states()
    pairs, reasons = Counter(), Counter()
    for cid, s in states.items():
        clip = CLIPS[cid][1]
        for i, e in s["edits"].items():
            t = clip["tokens"][int(i)]
            reasons.update(e.get("why", []))
            if e.get("gone"):
                pairs[(t["t"], "(removed)")] += 1
            elif e.get("show") and e["show"] != (t.get("auto") or t["t"]):
                pairs[(t["t"], e["show"])] += 1
        reasons.update(s["why"])
    decided = {r["key"]: r["decision"] for r in store.q("select * from rules")}
    rules = [{"key": f"{a}→{b}", "from": a, "to": b, "seen": n, "decision": decided.get(f"{a}→{b}")}
             for (a, b), n in pairs.most_common() if n >= 3]
    return {"fixes": sum(pairs.values()), "reasons": reasons.most_common(), "top": [[a, b, n] for (a, b), n in pairs.most_common(12)],
            "rules": rules, "spent": store.spent(), "budget": CLAUDE_MAX_USD,
            "lookups": store.q("select count(*) n from lookups", one=True)["n"],
            "chosen": store.q("select count(*) n from lookups where chosen is not null", one=True)["n"]}


class Rule(BaseModel):
    key: str
    decision: str  # yes | no


@app.post("/api/rules")
def decide(r: Rule):
    store.q("insert into rules(key, decision, updated_at) values(?,?,strftime('%s','now')) "
            "on conflict(key) do update set decision=excluded.decision, updated_at=excluded.updated_at", (r.key, r.decision))
    return {"ok": True}


@app.get("/api/export", response_class=PlainTextResponse)
def export():
    """One JSON line per reviewed clip: final text, verdict, reasons, comments, voice-note transcripts, teach/exam."""
    states, lines = store.clip_states(), []
    notes = defaultdict(list)
    for v in store.q("select clip_id, word, transcript from voice"):
        notes[v["clip_id"]].append(v)
    for cid, s in states.items():
        e, c = CLIPS[cid]
        lines.append(json.dumps({"clip_id": cid, "excerpt_id": e["id"], "split": e["split"], "verdict": s["verdict"],
                                 "text": " ".join(final_words(c, s)), "myt_text": " ".join(t["t"] for t in c["tokens"]),
                                 "edits": s["edits"], "clip_reasons": s["why"], "clip_note": s["note"],
                                 "voice_notes": notes[cid], "seconds": s["seconds"], "updated_at": s["updated_at"]}, ensure_ascii=False))
    return "\n".join(lines) + "\n"


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
