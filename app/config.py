"""Settings, all from environment variables (see .env.example). Secrets are never written to files."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def env(name, default=None):
    v = os.environ.get(name)
    if not v and sys.platform == "win32":  # keys set with setx are in the registry until the next login
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            v = None
    return v or default


DATA_DIR = Path(env("DATA_DIR", str(ROOT.parent.parent / "kreola-data" / "00_review" / "platform" / "data")))
REVIEWER = env("REVIEWER_NAME", "Yukta")
PASSWORD = env("REVIEW_PASSWORD")  # unset = no login (fine on the laptop; always set it when hosted)
SESSION_SECRET = env("SESSION_SECRET", "local-only-change-me")
HOSTED = env("HOSTED") == "1"  # set in the Docker image: https cookies, and a real session secret when there is a password
if HOSTED and PASSWORD and SESSION_SECRET == "local-only-change-me":
    raise SystemExit("REVIEW_PASSWORD is set but SESSION_SECRET is not: set a long random SESSION_SECRET")
if HOSTED and not PASSWORD:  # the reviewer's choice (29 Oct 2026): open access; set REVIEW_PASSWORD to turn the login back on
    print("WARNING: no REVIEW_PASSWORD, so anyone with the address can use the app and its Claude credit", flush=True)
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_MAX_USD = float(env("CLAUDE_MAX_USD", "9"))  # stop Claude searches before the $10 credit runs out
MYT_KEY, MYT_BASE = env("MYT_API_KEY"), (env("MYT_BASE_URL") or "").rstrip("/")
# USD per million tokens (input, output), from the Claude model table, Oct 2026
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
