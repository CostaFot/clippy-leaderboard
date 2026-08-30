# clippy-leaderboard

The global leaderboard for [omarchy-inappropriate-clippy](https://github.com/CostaFot/omarchy-inappropriate-clippy). Installs post their kill/slap tallies here, and the front page renders them as a failed `systemctl status clippy` followed by a `coredumpctl list` of everyone who did it — one row per handle, kill bar √-scaled so the leader doesn't flatten the rest.

No cookies, no accounts. Handles are first-come, never-owned: anyone can post as anyone, collisions merge, and cheating is trivially easy over the plugin's own IPC. Every score was self-reported murder to begin with, so none of that matters.

## Endpoints

| Endpoint | What |
|---|---|
| `POST /bump` | Requires a `costafot.clippy/*` User-Agent (the doorman: keeps scanners out, spoofable by design). JSON `{"handle": "costa", "kills": 1, "slaps": 3}` — **deltas**, added to the running totals. Handle must match `[a-z0-9_.-]{1,24}` (lowercased first), deltas clamp to 0–50 per request. Returns the new totals plus rank: `{"handle", "kills", "slaps", "rank", "total"}`. A zero-delta bump is legal and creates the row. |
| `GET /` | The graveyard. Top 100 rows. No JavaScript beyond a self-hosted Umami tracker (nothing on the page needs it; block it and the page is unchanged); the only other external request is a Google Fonts stylesheet for JetBrains Mono (Omarchy users get CaskaydiaMono if installed). |
| `GET /api/scores?limit=N` | The board as JSON, default 50, cap 500. |
| `GET /api/score/<handle>` | One handle's totals and rank, or 404. |

## Deployment

Runs on Railway: Railpack detects Python + the Procfile, a Postgres service next door provides `DATABASE_URL`. The table is created on boot.

## Local run

```bash
pip install -r requirements.txt
DATABASE_URL=postgres://... python app.py
```
