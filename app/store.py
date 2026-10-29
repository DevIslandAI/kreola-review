"""Everything the reviewer produces, in one SQLite file (DATA_DIR/reviews.db).

clips   one row per clip: verdict, the reviewer's edits (by word position), clip comment, time spent
voice   voice notes (file in DATA_DIR/voice/) with their automatic transcript
lookups Claude searches and the option the reviewer picked (teaching material for the 90 h)
rules   rules proposed from repeated fixes, and the reviewer's yes/no
spend   Claude cost per request, so the budget can be enforced
"""
import json
import sqlite3
import threading
import time

from .config import DATA_DIR

_lock = threading.Lock()
SCHEMA = """
create table if not exists clips(clip_id text primary key, excerpt_id text, verdict text, edits text, why text,
  note text, seconds real default 0, updated_at real);
create table if not exists voice(id integer primary key, clip_id text, word integer, file text, transcript text, created_at real);
create table if not exists lookups(id integer primary key, clip_id text, query text, target text, options text, chosen text, created_at real);
create table if not exists rules(key text primary key, decision text, updated_at real);
create table if not exists spend(id integer primary key, kind text, model text, input_tokens int, output_tokens int, usd real, created_at real);
"""


def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DATA_DIR / "reviews.db", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


CONN = db()


def q(sql, args=(), one=False):
    with _lock:
        cur = CONN.execute(sql, args)
        CONN.commit()
        rows = cur.fetchall()
    return (dict(rows[0]) if rows else None) if one else [dict(r) for r in rows]


def save_clip(clip_id, excerpt_id, verdict, edits, why, note, seconds):
    q("""insert into clips(clip_id, excerpt_id, verdict, edits, why, note, seconds, updated_at) values(?,?,?,?,?,?,?,?)
         on conflict(clip_id) do update set verdict=coalesce(excluded.verdict, clips.verdict), edits=excluded.edits,
         why=excluded.why, note=excluded.note, seconds=clips.seconds+excluded.seconds, updated_at=excluded.updated_at""",
      (clip_id, excerpt_id, verdict, json.dumps(edits, ensure_ascii=False), json.dumps(why, ensure_ascii=False), note, seconds, time.time()))


def clip_states(excerpt_id=None):
    rows = q("select * from clips" + (" where excerpt_id=?" if excerpt_id else ""), (excerpt_id,) if excerpt_id else ())
    for r in rows:
        r["edits"], r["why"] = json.loads(r["edits"] or "{}"), json.loads(r["why"] or "[]")
    return {r["clip_id"]: r for r in rows}


def spent():
    return (q("select coalesce(sum(usd),0) s from spend", one=True) or {"s": 0})["s"]
