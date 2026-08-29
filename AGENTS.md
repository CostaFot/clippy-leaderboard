# AGENTS.md

Notes for anyone (human or agent) working on this repo.

## What this is

The global leaderboard for [omarchy-inappropriate-clippy](https://github.com/CostaFot/omarchy-inappropriate-clippy). One Flask file, one Postgres table, deployed on Railway with gunicorn. See `README.md` for the endpoints.

## Layout

- `app.py` — the whole app. Routes, SQL, and the front page's Jinja template (`PAGE`, a string; there is no `templates/` directory).
- `Procfile` — `web: gunicorn app:app`.
- `requirements.txt` — flask, gunicorn, psycopg2-binary. No dev dependencies, no test suite.

## Invariants — keep these true

- **`DATABASE_URL` is required at import.** `app.py` connects and runs `CREATE TABLE IF NOT EXISTS` on boot; there is no SQLite fallback and none is wanted.
- **`/bump` takes deltas, not totals.** Clamped to 0–50 per request as hygiene against a client bug. It is not anti-cheat and there is no anti-cheat; the README explains why. Don't add accounts, tokens, or rate limits.
- **The User-Agent check on `/bump` is a doorman, not a lock.** It keeps scanners out. Don't "harden" it.
- **Ranking is `kills DESC, slaps DESC`** with SQL `RANK()`, so equal kills+slaps share a rank; handle only breaks display order. `ORDER` in `app.py` is the single source of truth.
- **The front page is server-rendered with no JavaScript.** The only external request is a Google Fonts stylesheet. Keep it that way.
- **Front-page design:** a fake `systemctl --user status clippy` (failed, SIGKILL) followed by a fake `coredumpctl list`, one row per handle. Colours are Omarchy's default Tokyo Night palette; font stack prefers CaskaydiaMono, falls back to JetBrains Mono. Kill bars are √-scaled so the leader doesn't flatten the rest. Zero-kill handles show "still breathing. coward." Tagline is `# it looks like you are trying to kill me. again.`
- **Copy is part of the design.** The footer text and the empty-state line are deliberate; don't neutralise them.

## Running it without a database

For eyeballing the page, stub `psycopg2` before importing `app` and swap the two data functions:

```python
import os, sys, types
fake = types.ModuleType("psycopg2")
class _Cur:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, *a, **k): pass
    def fetchone(self): return (0,)
class _Conn:
    def cursor(self): return _Cur()
    def commit(self): pass
    def close(self): pass
fake.connect = lambda *a, **k: _Conn()
sys.modules["psycopg2"] = fake
os.environ["DATABASE_URL"] = "postgres://fake"

import app as lb
lb.board = lambda limit=None: [(1, "dhh", 412, 1337), (2, "costa", 388, 902), (3, "lurker", 0, 0)]
lb.totals = lambda: (3, 800, 2239)
lb.app.run(port=5055)
```

`board()` returns `[(rank, handle, kills, slaps)]` in canonical order; `totals()` returns `(handles, kills, slaps)` across the whole table. Both are what `/` consumes.

Real local run: `DATABASE_URL=postgres://... python app.py`.

## Git

- Don't commit, push, or amend unless explicitly asked.
- No `Co-Authored-By` or other attribution trailers.
- `__pycache__/` is ignored; don't add it back.
