"""Make an API key, for a script that uses ClipCut without the dashboard.

    python -m studio.apikey                          prints a new key for the owner (no sign-in mode)
    python -m studio.apikey --email you@example.com  for that account (with CLIPCUT_ACCOUNTS=1)
    python -m studio.apikey --env path/to/.env       writes it into that file as CLIPCUT_API_KEY=..., not on screen

Scripts send it as:  Authorization: Bearer <key>"""
import argparse
import re
from pathlib import Path

import sqlalchemy as sa

from . import auth, config, db


def _write_env(path: Path, key: str):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [x for x in lines if not re.match(r"\s*CLIPCUT_API_KEY\s*=", x)] + [f"CLIPCUT_API_KEY={key}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main():
    p = argparse.ArgumentParser(description="Make a ClipCut API key.")
    p.add_argument("--email", help="the account the key is for (only when sign-in is on)")
    p.add_argument("--name", default="script", help="a label, to tell keys apart")
    p.add_argument("--env", help="write the key into this .env file instead of printing it")
    a = p.parse_args()
    db.init()
    if config.ACCOUNTS:
        if not a.email:
            raise SystemExit("Sign-in is on here: say which account with --email.")
        with db.engine.connect() as c:
            u = c.execute(sa.select(db.users).where(db.users.c.email == a.email.strip().lower())).first()
        if not u:
            raise SystemExit("No account with that email.")
    else:
        u = auth.local_user()
    key = auth.new_api_key(u.id, a.name)
    if a.env:
        _write_env(Path(a.env).expanduser(), key)
        print(f"Saved a new API key in {a.env}")
    else:
        print(key)


if __name__ == "__main__":
    main()
