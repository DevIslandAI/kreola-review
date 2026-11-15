"""Tag the language of every word of the review set: K = Kreol (mfe), F = French, E = English, N = proper noun / acronym.

  python tools/tag_languages.py               -> rules on every clip, then Claude on the mixed clips -> app/data/word_tags.json
  python tools/tag_languages.py --sample 30   -> Claude on 30 mixed clips only, prints the cost (check before the full run)
  python tools/tag_languages.py --rules-only  -> no Claude

1. Rules, from our own data: each of the 18,962 clips has a language label, so a word seen almost only in Kreol clips
   is Kreol, almost only in French clips is French, etc. Accents and French contractions (c', l', qu') mean French;
   Kreol short forms (mo'nn, pa'le) mean Kreol; all-caps words and vocabulary-sheet names mean proper noun.
   Words shared by the languages (la, de, pa) take the language of the words around them.
2. Claude (claude-opus-5-5) re-tags only the clips the rules find mixed or unsure, a few at a time, with the project's
   rule E (a borrowed word in Kreol spelling is Kreol; a whole French/English phrase is French/English).
The reviewer has the last word in the review site (KM / FR / EN / NE buttons). Output: {clip_id: "KKKFFN..."},
one letter per token of the clip, in token order.
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from app.config import env  # noqa: E402

STAGE = Path(os.environ.get("KREOLA_STAGE", HERE.parent / "kreola-data" / "staging" / "kreola-speech"))
DATA = Path(os.environ.get("DATA_DIR", HERE.parent / "kreola-data" / "00_review" / "platform" / "data"))
OUT = HERE / "app" / "data" / "word_tags.json"
LANG = {"mfe_Latn": "K", "fra_Latn": "F", "eng_Latn": "E"}
SHARE = .85            # a word is that language when at least 85% of its uses are in clips of that language
MIN_SEEN = 4
KM_SHORT = re.compile(r"^(mo|to|li|nou|zot|pa|ti|ki|sa|la)'(nn|n|le|a|ti)$")
FR_CONTRACT = re.compile(r"^(c|l|d|j|n|m|t|s|qu|jusqu|lorsqu|puisqu)'\w+")
ACCENT = re.compile(r"[éèêëàâçùûôîïœæ]")
KM_LOOK = re.compile(r"(enn|ann|onn|inn)$|^z|[kw]")


def fold(s):
    s = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    return re.sub(r"^[^\w']+|[^\w']+$", "", s)


def word_stats():
    """Share of each word's uses that fall in Kreol / French / English clips (counts per language are normalised)."""
    per = {k: Counter() for k in LANG.values()}
    for f in sorted((STAGE / "04_synchronized").glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            r = json.loads(line)
            k = LANG.get(r["language"])
            if k:
                per[k].update(fold(w) for w in r["draft_text"].split())
    tot = {k: sum(c.values()) or 1 for k, c in per.items()}
    stats = {}
    for w in set().union(*per.values()):
        n = sum(per[k][w] for k in per)
        if n >= MIN_SEEN and w:
            rel = {k: per[k][w] / tot[k] for k in per}
            s = sum(rel.values())
            stats[w] = {k: v / s for k, v in rel.items()}
    return stats


def names():
    """Places, organisations, brands and acronyms of the vocabulary sheet (its code-switch terms are not names)."""
    d = json.loads((HERE / "app" / "data" / "dictionary.json").read_text(encoding="utf-8"))
    return {fold(e["w"]) for e in d["mfe"] if e["src"] == "Vocabulary sheet" and not e["kind"].startswith("from")}


def rule_tags(words, clip_lang, stats, nameset):
    tags, prev_end = [], True
    for raw in words:
        w = fold(raw)
        t = "?"
        if not w:
            t = "?"
        elif (raw.isupper() and len(w) >= 2) or w in nameset or (raw[:1].isupper() and not prev_end and raw.lower() != "i"):
            t = "N"
        elif KM_SHORT.match(w):
            t = "K"
        elif ACCENT.search(w) or FR_CONTRACT.match(w):
            t = "F"
        elif w in stats:
            k, v = max(stats[w].items(), key=lambda kv: kv[1])
            t = k if v >= SHARE else "?"
        elif KM_LOOK.search(w):
            t = "K"
        tags.append(t)
        prev_end = raw.endswith((".", "?", "!"))
    # shared or unknown words take the language around them (nearest known neighbour on each side, else the clip's)
    known = [t if t in "KFE" else None for t in tags]
    default = LANG.get(clip_lang, "K")
    for i, t in enumerate(tags):
        if t == "?":
            left = next((known[j] for j in range(i - 1, -1, -1) if known[j]), None)
            right = next((known[j] for j in range(i + 1, len(tags)) if known[j]), None)
            tags[i] = left if left and (left == right or not right) else right if right and not left else default
    return "".join(tags)


def is_mixed(tags, unsure):
    langs = {t for t in tags if t in "KFE"}
    return len(langs) > 1 or unsure / max(1, len(tags)) > .25


SYSTEM = """You tag the language of every word in transcripts of Mauritian speech (Kreol Morisien, French, English).
Letters: K = Kreol Morisien, F = French, E = English, N = proper noun or acronym (people, places, brands, institutions).
Tag the language the speaker is speaking at that word, not the spelling the recogniser used:
- A French-origin word inside Kreol speech is K, even when the transcript writes it the French way ("question",
  "comment", "client" in a Kreol sentence are K; Kreol spells them kestion, koman, klian). Most Kreol words come from French.
- A single English word used inside a Kreol sentence ("meeting", "business", "self employ") is E.
- A whole French phrase or sentence (several French words together, French grammar: "pendant deux ans et ensuite",
  "à la disposition de") is F for every word of it; the same for English phrases with E.
- Short words shared by the languages (la, de, pa, en, sa, so, ok) take the language of the phrase they belong to.
- The transcripts come from a speech recogniser and contain errors; tag what is written.
Each word is shown as number:word/guess, where guess is a first automatic tag. Return only the words whose tag
should change, as their number and the right letter; return an empty list for a clip whose guesses are all right."""
CHANGE = {"type": "object", "additionalProperties": False, "required": ["n", "tag"],
          "properties": {"n": {"type": "integer"}, "tag": {"type": "string", "enum": ["K", "F", "E", "N"]}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["clips"],
          "properties": {"clips": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                               "required": ["id", "changes"],
                                                               "properties": {"id": {"type": "string"},
                                                                              "changes": {"type": "array", "items": CHANGE}}}}}}
PRICE_IN, PRICE_OUT = 4.0, 20.0  # claude-opus-5-5, USD per million tokens


def claude_tags(batch, client):
    lines = []
    for cid, words, guess in batch:
        # multi-word tokens ("de-mil vennde") are joined with _ so each numbered item stays one word
        lines.append(f"CLIP {cid}\n" + " ".join(f"{i + 1}:{w.replace(' ', '_')}/{g}" for i, (w, g) in enumerate(zip(words, guess))))
    r = client.beta.messages.create(
        model="claude-opus-5-5", max_tokens=8000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "\n\n".join(lines)}])
    u = r.usage
    usd = (u.input_tokens * PRICE_IN + (u.cache_creation_input_tokens or 0) * PRICE_IN * 1.25
           + (u.cache_read_input_tokens or 0) * PRICE_IN * .1 + u.output_tokens * PRICE_OUT) / 1e6
    if r.stop_reason == "refusal":
        return {}, usd
    out = {c["id"]: c["changes"] for c in json.loads(next(b.text for b in r.content if b.type == "text"))["clips"]}
    res = {}
    for cid, words, guess in batch:  # the rule guess with Claude's changes applied (numbers out of range are ignored)
        if cid in out:
            t = list(guess)
            for c in out[cid]:
                if 1 <= c["n"] <= len(t):
                    t[c["n"] - 1] = c["tag"]
            res[cid] = "".join(t)
    return res, usd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--batch", type=int, default=12)
    a = ap.parse_args()
    s = json.loads((DATA / "review_set.json").read_text(encoding="utf-8"))
    stats, nameset = word_stats(), names()
    print(f"word statistics: {len(stats)} words seen at least {MIN_SEEN} times; {len(nameset)} names from the vocabulary sheet", flush=True)
    tags, mixed = {}, []
    for e in s["excerpts"]:
        for c in e["clips"]:
            words = [t.get("auto") or t["t"] for t in c["tokens"]]
            unsure = sum(1 for w in words if fold(w) not in stats and not KM_SHORT.match(fold(w)))
            tags[c["clip_id"]] = rule_tags(words, c["language"], stats, nameset)
            if is_mixed(tags[c["clip_id"]], unsure):
                mixed.append((c["clip_id"], words))
    letters = Counter("".join(tags.values()))
    print(f"rules: {len(tags)} clips, letters {dict(letters)}; mixed or unsure clips: {len(mixed)}", flush=True)
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    by_claude = set(done.get("_claude", []))
    if not a.rules_only:
        import anthropic
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
        todo = [m for m in mixed if m[0] not in by_claude][: a.sample or None]
        spent, fixed, changed = 0.0, 0, 0
        for i in range(0, len(todo), a.batch):
            batch = [(cid, words, tags[cid]) for cid, words in todo[i:i + a.batch]]
            try:
                got, usd = claude_tags(batch, client)
            except Exception as ex:  # a failed batch keeps the rule tags; it is retried on the next run
                print(f"  batch {i // a.batch + 1} failed: {ex!r}"[:200], flush=True)
                continue
            spent += usd
            for cid, words, guess in batch:
                t = re.sub(r"[^KFEN]", "", got.get(cid, ""))
                if len(t) == len(words):
                    changed += sum(x != y for x, y in zip(t, guess))
                    tags[cid] = t
                    by_claude.add(cid)
                    fixed += 1
            print(f"  {min(i + a.batch, len(todo))}/{len(todo)} clips, ${spent:.3f} so far", flush=True)
        estimate = f" (≈ ${spent / max(1, len(todo)) * len(mixed):.2f} for all {len(mixed)} mixed clips)" if a.sample else ""
        print(f"Claude: {fixed} clips re-tagged, {changed} word tags changed, ${spent:.2f}{estimate}", flush=True)
    if a.sample:
        return  # a sample run only measures; it does not write the file
    for cid, t in done.items():  # keep earlier Claude tags of clips not re-run
        if cid in by_claude and cid != "_claude" and cid not in [m[0] for m in mixed]:
            tags[cid] = t
    OUT.write_text(json.dumps({**tags, "_claude": sorted(by_claude)}, separators=(",", ":")), encoding="utf-8")
    print(f"written {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
