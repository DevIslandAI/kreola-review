"""Word search: instant dictionary matches, and Claude for meanings, translations and spellings the lists don't have."""
import json
import time
import unicodedata

import anthropic

from . import store
from .config import CLAUDE_MAX_USD, CLAUDE_MODEL, PRICES, ROOT, env

DICT = json.loads((ROOT / "data" / "dictionary.json").read_text(encoding="utf-8"))
RULES = (ROOT / "data" / "rules.md").read_text(encoding="utf-8")
LANGS = {"mfe": "Mauritian Kreol", "fr": "French", "en": "English"}


def fold(s):
    s = unicodedata.normalize("NFD", (s or "").lower().replace("’", "'"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def words(s):
    return [w for w in fold(s).replace("/", " ").replace(",", " ").replace("(", " ").replace(")", " ").split() if w]


def kreol_hits(query, limit):
    n = fold(query)

    def score(e):
        w, alt, mean = fold(e["w"]), words(e["alt"]), words(e["en"] + " " + e["fr"])
        if w == n:
            return 0
        if n in alt:
            return 1
        if w.startswith(n):
            return 2
        if all(t in mean for t in n.split()):
            return 3  # search by meaning: "with" -> avek, ek
        return 9
    hits = sorted((s, i) for i, e in enumerate(DICT["mfe"]) if (s := score(e)) < 9)
    return [{**DICT["mfe"][i], "lang": "mfe"} for _, i in hits[:limit]]


def search(query, lang, limit=8):
    """Instant matches in one language: Kreol by spelling, variant or meaning; French/English by spelling (most common first)."""
    if not fold(query):
        return []
    if lang == "mfe":
        return kreol_hits(query, limit)
    n = fold(query)
    exact = [w for w in DICT[lang] if fold(w) == n]
    pref = [w for w in DICT[lang] if fold(w).startswith(n) and w not in exact]
    return [{"w": w, "lang": lang, "src": "word list"} for w in (exact + pref)[:limit]]


SYSTEM = f"""You help a reviewer correct transcripts of Mauritian speech (Kreol Morisien, French, English, often mixed).
The reviewer gives a word or phrase, in any language or as a rough sound or a meaning, and the language they want it in.
Return up to 4 options in the wanted language, most likely first, each with a short note (meaning, or when it is used).
Kreol must follow the official Lortograf 2011 spelling and the project's rules below. French and English must be
spelled correctly with accents. If the input looks like a misheard word (sounds alike), include what it probably was.
Use the sentence context when given. Never invent: if unsure, say so in the note.

PROJECT SPELLING RULES
{RULES}"""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["options"],
          "properties": {"options": {"type": "array", "items": {
              "type": "object", "additionalProperties": False, "required": ["text", "lang", "note"],
              "properties": {"text": {"type": "string"}, "lang": {"type": "string", "enum": ["mfe", "fr", "en"]},
                             "note": {"type": "string"}}}}}}


class BudgetReached(Exception):
    pass


def ask(query, target, context="", clip_id=""):
    """Claude search. Returns (lookup_id, options). Refuses once CLAUDE_MAX_USD has been spent."""
    if store.spent() >= CLAUDE_MAX_USD:
        raise BudgetReached(f"Claude budget of ${CLAUDE_MAX_USD:.2f} reached")
    seen = kreol_hits(query, 6) + [e for t in words(query) for e in kreol_hits(t, 3)]
    known = "\n".join(f"- {e['w']} ({e['kind']}): {e['en']} / {e['fr']}" for e in {e["w"]: e for e in seen}.values())
    prompt = (f"Wanted language: {LANGS[target]}\nInput: {query}\n"
              + (f"Sentence it comes from: {context}\n" if context else "")
              + (f"Matching entries from our Kreol vocabulary sheet:\n{known}\n" if known else ""))
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    r = client.beta.messages.create(
        model=CLAUDE_MODEL, max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",  # a policy decline is retried on another model
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    pin, pout = PRICES.get(r.model, PRICES["claude-opus-5-5"])
    u = r.usage  # cache writes cost 1.25x input, cache reads at most 0.1x: counted on the safe (high) side
    usd = (u.input_tokens * pin + (u.cache_creation_input_tokens or 0) * pin * 1.25
           + (u.cache_read_input_tokens or 0) * pin * .1 + u.output_tokens * pout) / 1e6
    store.q("insert into spend(kind, model, input_tokens, output_tokens, usd, created_at) values('lookup',?,?,?,?,?)",
            (r.model, r.usage.input_tokens, r.usage.output_tokens, usd, time.time()))
    if r.stop_reason == "refusal":
        return None, []
    options = json.loads(next(b.text for b in r.content if b.type == "text"))["options"][:4]
    store.q("insert into lookups(clip_id, query, target, options, created_at) values(?,?,?,?,?)",
            (clip_id, query, target, json.dumps(options, ensure_ascii=False), time.time()))
    lid = store.q("select max(id) id from lookups", one=True)["id"]
    return lid, options
