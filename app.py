"""The Clippy Graveyard — a global leaderboard for omarchy-inappropriate-clippy.

Installs POST their kill/slap deltas here (opt-in, a handle the user picked);
the front page renders one headstone per handle, sized by kills. No cookies,
no accounts, no anti-cheat: handles are first-come, never-owned, collisions
merge, and every score was self-reported murder to begin with.

Same shape as claps-api: Flask + psycopg2 + gunicorn on Railway, DATABASE_URL
from the Postgres service next door.
"""

import math
import os
import re
from contextlib import contextmanager

import psycopg2
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]

HANDLE_RE = re.compile(r"^[a-z0-9_.-]{1,24}$")
DELTA_CAP = 50  # hygiene against a stray bug, not anti-cheat
ORDER = "kills DESC, slaps DESC, handle ASC"


@contextmanager
def db():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                handle TEXT PRIMARY KEY,
                kills INTEGER NOT NULL DEFAULT 0,
                slaps INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


init_db()


def clean_handle(raw):
    """Lowercased [a-z0-9_.-]{1,24} or None. Case folds so Costa == costa."""
    if not isinstance(raw, str):
        return None
    handle = raw.strip().lower()
    return handle if HANDLE_RE.match(handle) else None


def clean_delta(v):
    try:
        return max(0, min(DELTA_CAP, int(v)))
    except (TypeError, ValueError):
        return 0


def board(limit=None):
    """[(rank, handle, kills, slaps)] in canonical order."""
    sql = f"SELECT RANK() OVER (ORDER BY kills DESC, slaps DESC) , handle, kills, slaps FROM scores ORDER BY {ORDER}"
    if limit:
        sql += " LIMIT %s"
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,) if limit else None)
        return cur.fetchall()


def score_of(handle):
    """(kills, slaps, rank, total) or None."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT kills, slaps, rank, total FROM (
                SELECT handle, kills, slaps,
                       RANK() OVER (ORDER BY kills DESC, slaps DESC) AS rank,
                       COUNT(*) OVER () AS total
                FROM scores
            ) ranked WHERE handle = %s
            """,
            (handle,),
        )
        return cur.fetchone()


UA_PREFIX = "costafot.clippy/"


@app.route("/bump", methods=["POST"])
def bump():
    # Only the plugin's own User-Agent may post. Trivially spoofed (the
    # string is right here in a public repo) -- this is a doorman, not a
    # lock: it keeps scanners and copy-paste curls out of the table.
    if not request.headers.get("User-Agent", "").startswith(UA_PREFIX):
        return jsonify({"error": "you are not a paperclip"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body required"}), 400
    handle = clean_handle(data.get("handle"))
    if not handle:
        return jsonify({"error": "handle must match [a-z0-9_.-]{1,24}"}), 400
    kills = clean_delta(data.get("kills"))
    slaps = clean_delta(data.get("slaps"))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scores (handle, kills, slaps) VALUES (%s, %s, %s)
            ON CONFLICT (handle) DO UPDATE
                SET kills = scores.kills + EXCLUDED.kills,
                    slaps = scores.slaps + EXCLUDED.slaps,
                    updated_at = now()
            """,
            (handle, kills, slaps),
        )
    kills_t, slaps_t, rank, total = score_of(handle)
    return jsonify({"handle": handle, "kills": kills_t, "slaps": slaps_t, "rank": rank, "total": total})


@app.route("/api/scores")
def api_scores():
    try:
        limit = max(1, min(500, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50
    rows = board(limit)
    return jsonify([{"rank": r, "handle": h, "kills": k, "slaps": s} for r, h, k, s in rows])


@app.route("/api/score/<raw>")
def api_score(raw):
    handle = clean_handle(raw)
    row = score_of(handle) if handle else None
    if not row:
        return jsonify({"error": "unknown handle"}), 404
    kills, slaps, rank, total = row
    return jsonify({"handle": handle, "kills": kills, "slaps": slaps, "rank": rank, "total": total})


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Clippy Graveyard</title>
<style>
  :root {
    --ground: #12100e;
    --sky: #1a1d24;
    --stone: #6b7280;
    --stone-face: #7d8694;
    --etch: #23272e;
    --moss: #3f4b3a;
    --text: #c7cdd6;
    --dim: #6f7683;
    --accent: #d4a017;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: linear-gradient(var(--sky) 0%, #14161b 70%, var(--ground) 70.2%);
    color: var(--text);
    font-family: Georgia, 'Times New Roman', serif;
    min-height: 100vh;
    padding: 3rem 1.5rem 4rem;
  }
  header { text-align: center; margin-bottom: 3rem; }
  h1 { font-size: 2.4rem; letter-spacing: 0.06em; color: #e8eaee; }
  .subtitle { color: var(--dim); font-style: italic; margin-top: 0.5rem; }
  .yard {
    display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: center;
    gap: 2.2rem 1.6rem; max-width: 1100px; margin: 0 auto;
  }
  .grave { text-align: center; }
  .stone {
    position: relative;
    width: calc(120px * var(--s));
    padding: calc(18px * var(--s)) 10px calc(12px * var(--s));
    background: linear-gradient(160deg, var(--stone-face), var(--stone) 60%, #565e6a);
    border-radius: calc(60px * var(--s)) calc(60px * var(--s)) 4px 4px;
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.12), 0 6px 12px rgba(0,0,0,0.55);
    margin: 0 auto;
  }
  .stone .clip { font-size: calc(1.1rem * var(--s)); color: var(--etch); }
  .stone .handle {
    font-size: calc(0.95rem * var(--s)); color: var(--etch); font-weight: bold;
    letter-spacing: 0.04em; word-break: break-all; text-shadow: 0 1px 0 rgba(255,255,255,0.15);
  }
  .stone .kills { font-size: calc(1.7rem * var(--s)); color: var(--etch); font-weight: bold; }
  .stone .klabel { font-size: calc(0.6rem * var(--s)); color: var(--etch); letter-spacing: 0.12em; text-transform: uppercase; }
  .stone .rank {
    position: absolute; top: calc(-10px * var(--s)); right: -8px;
    background: var(--accent); color: #1d1405; font-size: 0.72rem; font-weight: bold;
    padding: 2px 7px; border-radius: 9px; box-shadow: 0 2px 5px rgba(0,0,0,0.5);
    font-family: system-ui, sans-serif;
  }
  .mound {
    width: calc(150px * var(--s)); height: calc(16px * var(--s));
    background: radial-gradient(ellipse at 50% 0%, #2a2620, var(--ground) 75%);
    border-radius: 50% 50% 0 0; margin: -2px auto 0;
  }
  .slaps { color: var(--dim); font-size: 0.75rem; margin-top: 0.45rem; font-family: system-ui, sans-serif; }
  .breathing { color: var(--moss); font-size: 0.7rem; font-style: italic; }
  .empty { text-align: center; color: var(--dim); font-size: 1.2rem; margin: 5rem 0; font-style: italic; }
  .more { text-align: center; color: var(--dim); font-style: italic; margin-top: 3rem; }
  footer {
    max-width: 640px; margin: 5rem auto 0; text-align: center;
    color: var(--dim); font-size: 0.85rem; line-height: 1.7;
    border-top: 1px solid #262a31; padding-top: 1.5rem;
  }
  footer code {
    font-family: ui-monospace, monospace; font-size: 0.8rem;
    background: #20242b; padding: 2px 6px; border-radius: 4px; color: var(--text);
  }
  footer a { color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>&#9879; The Clippy Graveyard</h1>
  <p class="subtitle">It looks like you're trying to bury me. Again.</p>
</header>
{% if rows %}
<div class="yard">
  {% for r in rows %}
  <div class="grave" style="--s: {{ '%.3f'|format(r.scale) }}">
    <div class="stone">
      {% if r.rank <= 3 and r.kills > 0 %}<span class="rank">#{{ r.rank }}</span>{% endif %}
      <div class="clip">&#128206;</div>
      <div class="handle">{{ r.handle }}</div>
      <div class="kills">{{ r.kills }}</div>
      <div class="klabel">kill{{ '' if r.kills == 1 else 's' }}</div>
    </div>
    <div class="mound"></div>
    {% if r.kills == 0 %}
    <div class="breathing">still breathing. coward.</div>
    {% else %}
    <div class="slaps">{{ r.slaps }} slap{{ '' if r.slaps == 1 else 's' }}</div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% if overflow %}<p class="more">&hellip;and {{ overflow }} more, rotting quietly.</p>{% endif %}
{% else %}
<p class="empty">Nobody has died yet. Disgraceful. Be the first.</p>
{% endif %}
<footer>
  <p>Every grave here is self-reported murder from
  <a href="https://github.com/CostaFot/omarchy-inappropriate-clippy">omarchy-inappropriate-clippy</a>.
  Join with <code>omarchy-shell costafot.clippy set leaderboard &lt;yourname&gt;</code> &mdash;
  opt-in, no cookies, no accounts. Handles are first-come, never-owned; collisions merge.
  Cheating is possible, easy, and beneath nobody.</p>
</footer>
</body>
</html>"""


@app.route("/")
def graveyard():
    rows = board(101)
    overflow = 0
    if len(rows) > 100:
        rows = rows[:100]
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scores")
            overflow = cur.fetchone()[0] - 100
    max_kills = max([k for _, _, k, _ in rows], default=0) or 1
    graves = [
        {
            "rank": r,
            "handle": h,
            "kills": k,
            "slaps": s,
            "scale": 0.55 + 0.45 * math.sqrt(k) / math.sqrt(max_kills),
        }
        for r, h, k, s in rows
    ]
    return render_template_string(PAGE, rows=graves, overflow=overflow)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
