# Kreola Review

The web app where 10 hours of Kreola clips are listened to and corrected by hand. Those hours become the
golden dataset, and they teach Claude how to correct the other ~90 hours the same way.

Works on a laptop and on a phone. Three screens:

- **Overview**: progress out of 10 h, the share of each recording type, and every recording with its status.
- **Review**: the clip plays and its words light up as they are spoken.
  - Click a word to hear only that word.
  - Double-click a word to open its card:
    1. **Correct word**: type the right word(s), or remove a word that was never said.
    2. **Find a word**: choose Kreol, French or English, then type a word, a meaning or what you hear.
       Dictionary matches appear instantly; **Ask** sends it to Claude for spellings, translations and misheard words.
    3. **Comment**: quick reasons, a typed comment, or a voice note (transcribed automatically).
  - Each clip also has a comment, a *before and after* view, and *Clip is correct* / *Save & next clip*.
- **Learning**: why words were fixed, the most common fixes, rules proposed from repeated fixes, and Claude spending.

Every change is saved on the server as you go.

## What is where

| Path | What |
|---|---|
| `app/main.py` | the web server (FastAPI): pages, saving, audio, search, voice notes, export |
| `app/lookup.py` | word search: dictionary + Claude (Opus 5.5, spelling rules in the prompt, spending stop) |
| `app/voice.py` | voice notes: stored, then transcribed with myt ASR |
| `app/store.py` | the SQLite database: clips, voice notes, Claude searches, rules, spending |
| `app/static/` | the interface (plain HTML/CSS/JS, no build step) |
| `app/data/dictionary.json` | 447 Kreol entries (vocabulary sheet, Lortograf 2011) + 40,000 French + 40,000 English words |
| `app/data/rules.md` | the project spelling rules v1.0 (given to Claude with every search) |
| `tools/build_review_set.py` | chooses the 10 h and cuts their audio (run once, on the PC with the dataset) |
| `tools/build_dictionary.py` | rebuilds the dictionary from the vocabulary sheet |

**Review data never goes to git.** It lives in `DATA_DIR`: `review_set.json`, `audio/` (~210 MB), and `reviews.db` +
`voice/` (your work). On the laptop that is `../kreola-data/00_review/platform/data`; on the server, the `/data` volume.

## Run on the laptop

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8770
```

Then open http://localhost:8770. Keys are read from the Windows user environment variables `ANTHROPIC_API_KEY`,
`MYT_API_KEY` and `MYT_BASE_URL`. No password is asked locally unless `REVIEW_PASSWORD` is set.

## Host on EasyPanel

1. **Create the app** in EasyPanel → *App* → source *GitHub* (this repository) → build *Dockerfile*.
2. **Environment:** add the variables listed in `.env.example`. `REVIEW_PASSWORD` and `SESSION_SECRET` are
   required: the app refuses to start without them, because otherwise anyone could hear the audio and spend the
   Claude credit.
3. **Storage:** add a volume mounted at `/data`. Copy into it once:
   - `review_set.json`;
   - the `audio/` folder from `kreola-data/00_review/platform/data/`.

   EasyPanel's file browser works, or `scp`.
4. **Domain:** set the domain with HTTPS on, pointing to port `8000`.
5. **Backup:** `reviews.db` and `voice/` in `/data` are your work. Back them up; `GET /api/export` also gives all
   reviews as JSON lines.

## Costs

A Claude search with Claude Opus 5.5 costs about $0.02 for the first search, and less for searches made within the next 5
minutes, because the spelling rules are then read from Claude's cache. The app stops searching at `CLAUDE_MAX_USD` (default $9),
and the Learning screen shows what has been spent. `CLAUDE_MODEL=claude-sonnet-5-5` halves the cost.

## Credits

French and English word lists: [wordfreq](https://github.com/rspeer/wordfreq) (CC BY-SA 4.0). Kreol spellings: Lortograf
Kreol Morisien (2011) and the Kreola vocabulary sheet.
