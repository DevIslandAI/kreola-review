"""Build app/data/lexicon.json: the spelling pairs behind the review site's spelling check.

  python tools/build_lexicon.py

Two lists:
  km: a French (or wrong) spelling -> the Kreol spelling. Used on words tagged Kreol: "avec" in Kreol speech -> "avek".
  fr: a Kreol spelling -> the French spelling. Used on words tagged French: "avek" inside a French phrase -> "avec".
Sources: the alternative spellings of the Lortograf entries in app/data/dictionary.json, the Lortograf short forms
(rules.md, section C), and CURATED below. Words that are themselves correct Kreol are never flagged: other headwords,
and the long verb forms (manze, koze, rode...) that Kreol uses at the end of a sentence.
"""
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "app" / "data" / "lexicon.json"

# correct Kreol words that the dictionary lists as variants of another word: never flag them
KREOL_OK = {"konn", "fin", "kote", "vini", "ape", "koze", "manze", "rode", "avoye", "gete", "tande", "pe", "zordi",
            "lapey", "kot", "lot", "byen"}
# short forms the Lortograf writes with an apostrophe (rules.md, section C); not "pann", which is also a noun
CURATED_KM = {"monn": "mo'nn", "linn": "li'nn", "tonn": "to'nn", "nounn": "nou'nn", "kinn": "ki'nn"}
# words where Kreol fuses the French article (police -> lapolis, l'ecole -> lekol) or that are too short or ambiguous
NO_KM = {"police", "vente", "education", "equipe", "gov", "fair", "get"}
NO_FR = {"lapolis", "lavant", "ledikasion", "lekip", "lekol", "pa", "me", "ki", "dan", "lor", "sa", "to", "mo", "ti"}
CURATED_FR = {"travay": "travail", "kliyan": "client", "biznes": "business", "ankor": "encore",
              "deza": "déjà", "zis": "juste", "mem": "même", "plis": "plus", "tou": "tout"}


def fold(s):
    s = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    return re.sub(r"^[^\w']+|[^\w']+$", "", s)


def bare(s):  # without accents, to compare "equipe" with "équipe"
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def main():
    d = json.loads((HERE / "app" / "data" / "dictionary.json").read_text(encoding="utf-8"))
    entries = [e for e in d["mfe"] if e["src"] == "Lortograf 2011" and e["kind"] not in ("number", "greeting", "interjection")]
    heads = {fold(e["w"]) for e in d["mfe"]}
    km, fr = {}, {}
    for e in entries:
        w = fold(e["w"])
        gloss = {fold(g): g.strip() for g in re.split(r"[/,()]|\.\.\.", e.get("fr") or "") if g.strip()}
        gloss_bare = {bare(k): v for k, v in gloss.items()}
        for alt in re.split(r",", e.get("alt") or ""):
            a = fold(alt.strip())
            if not a or a.startswith("'") or " " in a or not re.fullmatch(r"[\w'-]+", a) or a.isdigit() or len(a) < 3 or "(" in alt:
                continue
            if a != w and a not in heads and a not in KREOL_OK:
                km.setdefault(a, e["w"])
            if bare(a) in gloss_bare and a != w:  # the variant is the French word itself: "avec" for "avek"
                fr.setdefault(w, gloss_bare[bare(a)])
    km.update(CURATED_KM)
    for k, v in CURATED_FR.items():
        fr.setdefault(k, v)
    km = {k: v for k, v in km.items() if k not in NO_KM}
    fr = {k: v for k, v in fr.items() if k not in NO_FR}
    OUT.write_text(json.dumps({"km": dict(sorted(km.items())), "fr": dict(sorted(fr.items()))}, ensure_ascii=False, indent=0),
                   encoding="utf-8")
    print(f"{len(km)} French or wrong spellings -> Kreol; {len(fr)} Kreol -> French. Written {OUT}")


if __name__ == "__main__":
    main()
