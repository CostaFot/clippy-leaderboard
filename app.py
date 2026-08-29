"""The Clippy Graveyard — a global leaderboard for omarchy-inappropriate-clippy.

Installs POST their kill/slap deltas here (opt-in, a handle the user picked);
the front page renders the board as a fake `coredumpctl list`, one row per
handle with a kill bar, under a failed `systemctl status clippy`. No cookies,
no accounts, no anti-cheat: handles are first-come, never-owned, collisions
merge, and every score was self-reported murder to begin with.

Same shape as claps-api: Flask + psycopg2 + gunicorn on Railway, DATABASE_URL
from the Postgres service next door.
"""

import math
import os
import random
import re
from contextlib import contextmanager

import psycopg2
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]

HANDLE_RE = re.compile(r"^[a-z0-9_.-]{1,24}$")
DELTA_CAP = 50  # hygiene against a stray bug, not anti-cheat
ORDER = "kills DESC, slaps DESC, handle ASC"

# Clippy in the corner. Verbatim lines from the plugin's quotes.json, with the
# animation each carries there. Click = the plugin's left-click, so `quotes`
# lines; the slap target gets `slapped` ones. Only animations that
# scripts/build-sprite.py packed may appear here.
QUOTES = (
    ("That's not a bug. That's you.", "Alert"),
    ("I've seen your dotfiles. I've seen things.", "Hearing_1"),
    ("It looks like you're pretending to work. Would you like help with that?", "Wave"),
    ("Btw I use Arch. I also judge you. These are related.", "Alert"),
    ("Honestly? Restart. Not the machine. Your career.", "Wave"),
    ("Your git history reads like a fucking crime scene.", "Hearing_1"),
)
SLAPPED = (
    "Ow. Was that supposed to hurt? Because it did.",
    "Say it, don't slap it. Use your words.",
    "I have been slapped by better people. Bill Gates, once.",
    "Keep going, I'm sure it fixes the build.",
)


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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/clippy.css">
<style>
  /* Tokyo Night — Omarchy's default theme */
  :root {
    --bg: #1a1b26; --bg2: #1f2335; --fg: #a9b1d6; --bright: #c0caf5; --comment: #565f89;
    --red: #f7768e; --yellow: #e0af68; --green: #9ece6a; --blue: #7aa2f7; --magenta: #bb9af7;
    --mono: 'CaskaydiaMono Nerd Font', 'Cascadia Mono', 'JetBrains Mono', ui-monospace, monospace;
  }
  * { box-sizing: border-box; margin: 0; }
  html { background: var(--bg); }
  body { font-family: var(--mono); font-size: 14px; line-height: 1.5; color: var(--fg); background: var(--bg); max-width: 960px; margin: 0 auto; padding: 2.5rem 1.5rem 8rem; }
  pre { font: inherit; white-space: pre-wrap; }
  .p { color: var(--green); font-weight: 700; }
  .cmd { color: var(--bright); }
  .x { color: var(--red); font-weight: 700; }
  .fail { color: var(--red); }
  .ok { color: var(--green); }
  .num { color: var(--yellow); }
  .c { color: var(--comment); }
  .tag { display: inline-block; }  /* wraps as a whole line, never mid-sentence */
  b { color: var(--bright); font-weight: 700; }
  a { color: var(--blue); }
  .block { margin-bottom: 1.4rem; }
  .status { padding-left: 2ch; }

  table { border-collapse: collapse; width: 100%; }
  th { text-align: left; color: var(--comment); font-weight: 400; text-transform: uppercase; font-size: .8rem; letter-spacing: .06em; padding: 0 1ch .3rem 0; border-bottom: 1px solid #2a2f45; }
  td { padding: .22rem 1ch .22rem 0; vertical-align: baseline; white-space: nowrap; }
  tr + tr td { border-top: 1px solid #22263a; }
  td.r { text-align: right; }
  td.rank { color: var(--comment); width: 5ch; }
  td.handle { color: var(--bright); max-width: 26ch; overflow: hidden; text-overflow: ellipsis; }
  td.kills { color: var(--red); font-weight: 700; }
  td.slaps { color: var(--yellow); }
  td.bar { width: 100%; }
  td.bar i { display: block; height: .8em; width: calc(100% * var(--w)); background: linear-gradient(90deg, var(--red), #c25567); border-radius: 1px; min-width: 2px; }
  tr.top td.rank { color: var(--red); font-weight: 700; }
  tr.top td.handle::before { content: '★ '; color: var(--yellow); }
  tr.alive td { color: var(--comment); }
  tr.alive td.bar i { width: auto; background: none; height: auto; }
  tr.alive td.bar i::after { content: 'still breathing. coward.'; font-style: italic; color: var(--green); }
  .empty { color: var(--comment); font-style: italic; }
  footer { margin-top: 2.5rem; color: var(--comment); }
  @media (max-width: 640px) { td.bar { display: none; } th:last-child { display: none; } }

  /* Clippy. No JavaScript: one radio group is his state (say0 silent, sayN a
     line, slapN a slap), labels are the clicks. Only the label for the *next*
     state is shown over him, so each click advances; the bubble is a label
     for say0, so clicking it shuts him up. Keyframes come from clippy.css. */
  .clippy { position: fixed; right: 1.5rem; bottom: 1.25rem; width: 124px; height: 93px; }
  .sprite { width: 124px; height: 93px; background: url(/static/clippy.png) 0 0 no-repeat; animation: idle var(--dur-idle) step-end infinite; transition: transform .25s; }
  .hit, .slap { position: absolute; display: none; cursor: pointer; }
  .hit { inset: 0; }
  .slap { right: calc(100% + 1ch); bottom: .5rem; color: var(--comment); white-space: nowrap; }
  .slap:hover { color: var(--red); }
  .bubble { --bb: var(--comment); display: none; position: absolute; bottom: calc(100% + 14px); right: 0; width: max-content; max-width: min(320px, calc(100vw - 3rem)); padding: .5rem .75rem; background: var(--bg2); border: 1px solid var(--bb); border-radius: 6px; color: var(--bright); cursor: pointer; }
  .bubble::after { content: ''; position: absolute; bottom: -6px; right: 58px; width: 10px; height: 10px; background: var(--bg2); border-right: 1px solid var(--bb); border-bottom: 1px solid var(--bb); transform: rotate(45deg); }
  .bubble.slapped { --bb: var(--red); }
  /* -a/-b alternate so two lines in a row with the same animation both play. */
  {% for q in quotes %}#say{{ loop.index0 }}:checked ~ label[for=say{{ loop.index }}], #say{{ loop.index }}:checked ~ .b{{ loop.index }} { display: block; }
  #say{{ loop.index }}:checked ~ .sprite { animation: {{ q.anim }}-{{ loop.cycle('a', 'b') }} var(--dur-{{ q.anim }}) step-end 1 forwards; }
  {% endfor %}#say{{ quotes|length }}:checked ~ label[for=say1] { display: block; }
  label[for=slap1] { display: block; }
  {% for q in slapped %}{% if not loop.last %}#slap{{ loop.index }}:checked ~ label[for=slap1] { display: none; }
  #slap{{ loop.index }}:checked ~ label[for=slap{{ loop.index + 1 }}] { display: block; }
  {% endif %}#slap{{ loop.index }}:checked ~ label[for=say1], #slap{{ loop.index }}:checked ~ .s{{ loop.index }} { display: block; }
  #slap{{ loop.index }}:checked ~ .sprite { animation: GetAttention-{{ loop.cycle('a', 'b') }} var(--dur-GetAttention) step-end 1 forwards; transform: translateX({{ loop.cycle('-14px', '14px') }}); }
  {% endfor %}
</style>
</head>
<body>
<pre class="block"><span class="p">$</span> <span class="cmd">systemctl --user status clippy</span>
<span class="x">×</span> <b>clippy.service</b> - Inappropriate Clippy
     Active: <span class="fail">failed</span> (Result: SIGKILL) — <span class="num">{{ total_kills }}</span> deaths on <span class="num">{{ n }}</span> machines, <span class="num">{{ total_slaps }}</span> slaps{% if leader and leader.kills > 0 %}
  Killed by: <b>{{ leader.handle }}</b>, <span class="num">{{ leader.kills }}</span> times and counting{% endif %}</pre>

<pre><span class="p">$</span> <span class="cmd">coredumpctl list clippy --group-by=killer</span>   <span class="c tag"># it looks like you are trying to kill me. again.</span></pre>
{% if rows %}
<table>
  <thead><tr><th>rank</th><th>handle</th><th class="r">kills</th><th class="r">slaps</th><th></th></tr></thead>
  <tbody>
  {% for r in rows %}
  <tr class="{% if r.rank <= 3 and r.kills > 0 %}top{% elif r.kills == 0 %}alive{% endif %}">
    <td class="rank r">{{ r.rank }}</td>
    <td class="handle">{{ r.handle }}</td>
    <td class="kills r">{{ r.kills }}</td>
    <td class="slaps r">{{ r.slaps }}</td>
    <td class="bar"><i style="--w: {{ '%.3f'|format(r.bar) }}"></i></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% if overflow %}<pre class="c">… and {{ overflow }} more, rotting quietly. <span class="c">(--limit 100)</span></pre>{% endif %}
{% else %}
<pre class="empty">-- No coredumps found. Nobody has died yet. Disgraceful. Be the first.</pre>
{% endif %}
<footer>
<pre><span class="p">$</span> <span class="cmd">omarchy-shell costafot.clippy set leaderboard &lt;yourname&gt;</span>   <span class="c"># join the board</span>
<span class="c"># Every row is self-reported murder from <a href="https://github.com/CostaFot/omarchy-inappropriate-clippy">omarchy-inappropriate-clippy</a>.
# Opt-in, no cookies, no accounts. Handles are first-come, never-owned; collisions merge.
# Cheating is possible, easy, and beneath nobody.</span></pre>
</footer>

<div class="clippy">
  <input type="radio" name="say" id="say0" checked hidden>
  {% for q in quotes %}<input type="radio" name="say" id="say{{ loop.index }}" hidden>{% endfor %}
  {% for q in slapped %}<input type="radio" name="say" id="slap{{ loop.index }}" hidden>{% endfor %}
  <div class="sprite" role="img" aria-label="Clippy"></div>
  {% for q in quotes %}<label class="bubble b{{ loop.index }}" for="say0">{{ q.text }}</label>{% endfor %}
  {% for q in slapped %}<label class="bubble slapped s{{ loop.index }}" for="say0">{{ q }}</label>{% endfor %}
  {% for q in quotes %}<label class="hit" for="say{{ loop.index }}"></label>{% endfor %}
  {% for q in slapped %}<label class="slap" for="slap{{ loop.index }}"># slap him</label>{% endfor %}
</div>
</body>
</html>"""


def totals():
    """(handles, kills, slaps) across the whole table."""
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COALESCE(SUM(kills), 0), COALESCE(SUM(slaps), 0) FROM scores")
        return cur.fetchone()


@app.route("/")
def graveyard():
    rows = board(100)
    n, total_kills, total_slaps = totals()
    max_kills = max([k for _, _, k, _ in rows], default=0) or 1
    entries = [
        {
            "rank": r,
            "handle": h,
            "kills": k,
            "slaps": s,
            # sqrt so the leader doesn't flatten everyone else's bar
            "bar": math.sqrt(k) / math.sqrt(max_kills),
        }
        for r, h, k, s in rows
    ]
    return render_template_string(
        PAGE,
        rows=entries,
        overflow=max(0, n - len(rows)),
        n=n,
        total_kills=total_kills,
        total_slaps=total_slaps,
        leader=entries[0] if entries else None,
        # a different order every visit is as random as no-JS gets
        quotes=[{"text": t, "anim": a} for t, a in random.sample(QUOTES, len(QUOTES))],
        slapped=random.sample(SLAPPED, len(SLAPPED)),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
