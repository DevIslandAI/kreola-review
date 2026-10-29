"""Build app/data/dictionary.json: the word lists behind the spelling search (run when the vocabulary sheet changes).

  python tools/build_dictionary.py

  mfe: KREOLA_VOCABULARY.xlsx (Lortograf 2011 spellings, places, names, code-switch terms) + Lortograf numbers 0-100
  fr / en: the 40,000 most frequent words of each language (wordfreq, CC BY-SA 4.0)
Also copies the spelling rules (TRANSCRIPTION_RULES_v1.0.md) to app/data/rules.md for the Claude search.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

import openpyxl
from wordfreq import top_n_list

HERE = Path(__file__).resolve().parent.parent
KREOLA = Path(os.environ.get("KREOLA_ROOT", HERE.parent))
VOCAB = KREOLA / "vocabulary" / "KREOLA_VOCABULARY.xlsx"
RULES = KREOLA / "kreola-data" / "staging" / "kreola-speech" / "policy" / "TRANSCRIPTION_RULES_v1.0.md"
OUT = HERE / "app" / "data"
N = 40000


def kreol():
    wb = openpyxl.load_workbook(VOCAB, read_only=True)
    rows = lambda name: list(wb[name].iter_rows(values_only=True))[1:]
    out = []
    for r in rows("kreol_words"):
        if r[0]:
            out.append({"w": r[0], "kind": r[1] or "", "en": r[2] or "", "fr": r[3] or "",
                        "alt": re.sub(r"\s*\(\d+\)", "", r[6] or ""), "src": "Lortograf 2011"})
    for r in rows("places"):
        if r[0]:
            out.append({"w": r[4] or r[0], "kind": "place", "en": r[1] or "", "fr": "", "alt": r[2] or "", "src": "Vocabulary sheet"})
    for r in rows("acronyms_orgs_brands"):
        if r[0]:
            out.append({"w": r[7] or r[0], "kind": r[2] or "name", "en": r[1] or "", "fr": "", "alt": (r[4] or "").replace("'", ""), "src": "Vocabulary sheet"})
    for r in rows("code_switch_terms"):
        if r[0]:
            out.append({"w": r[0], "kind": f"from {r[1] or ''}".strip(), "en": "kept as is in Kreol speech", "fr": "",
                        "alt": r[2] or "", "src": "Vocabulary sheet"})
    sys.path.insert(0, str(KREOLA / "kreola-data" / "scripts"))
    from clean_drafts import KR  # Lortograf Annex 3 numbers
    for n, w in sorted(KR.items()):
        out.append({"w": w, "kind": "number", "en": str(n), "fr": str(n), "alt": str(n), "src": "Lortograf 2011"})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = {"mfe": kreol(), "fr": top_n_list("fr", N), "en": top_n_list("en", N)}
    (OUT / "dictionary.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    shutil.copy(RULES, OUT / "rules.md")
    print({k: len(v) for k, v in d.items()}, f"{(OUT / 'dictionary.json').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
