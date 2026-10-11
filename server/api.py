"""
api.py — Production-ready Flask API for Sri Valmiki Ramayana corpus.

Security Features:
  ✅ Password login with hashed credentials (from env vars)
  ✅ Session-based authentication (login required for all pages)
  ✅ Rate limiting (anti-abuse)
  ✅ Strict security headers
  ✅ Input validation & sanitization
  ✅ CSRF protection via SameSite cookies
  ✅ Compatible with gunicorn (production WSGI)

Local:  python server/api.py
Deploy: gunicorn server.api:app --bind 0.0.0.0:$PORT --workers 2
"""

import sys
import os
import re
import secrets
from pathlib import Path
from datetime import timedelta
from functools import wraps

# ── Path setup — works locally AND on Render/gunicorn ────────────────────────
ROOT_DIR   = Path(__file__).resolve().parent.parent
SCRAPER_DIR = ROOT_DIR / "scraper"
sys.path.insert(0, str(SCRAPER_DIR))

from flask import (
    Flask, request, jsonify, send_from_directory,
    session, redirect, url_for, render_template_string
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

from db import (
    get_connection, get_verse_by_ref, search_verses,
    get_chapter_verses, get_stats, KANDA_NAMES,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH    = str(ROOT_DIR / "data" / "ramayana.db")
SEARCH_DIR = str(ROOT_DIR / "search")

# ── Credentials (from environment variables — set on Render or in .env) ──────
USERNAME      = os.environ.get("RAMAYANA_USERNAME", "admin")
_raw_password = os.environ.get("RAMAYANA_PASSWORD", "ramayana2024")
PASSWORD_HASH = generate_password_hash(_raw_password)

# ── App Setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=SEARCH_DIR)

app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY  = True,
    SESSION_COOKIE_SAMESITE  = "Lax",
    SESSION_COOKIE_SECURE    = os.environ.get("RENDER", False),  # HTTPS on Render
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8),
)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS(app, origins="*", supports_credentials=True)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per minute"],
    storage_uri="memory://",
)

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            # API calls get 401, browser requests get redirect
            if request.path.startswith(("/stats", "/verse", "/search", "/kandas", "/chapters", "/chapter")):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["X-XSS-Protection"]        = "1; mode=block"
    response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]      = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


def clean_query(raw: str, max_len: int = 200) -> str:
    q = raw.strip()[:max_len]
    q = re.sub(r"[<>\"'`;\\]", "", q)
    return q


def get_db():
    if not os.path.exists(DB_PATH):
        return None
    return get_connection(DB_PATH)


def verse_to_dict(row) -> dict:
    return dict(row) if row else {}


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE  (beautiful ISKCON-styled)
# ══════════════════════════════════════════════════════════════════════════════

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login — Śrī Vālmīki Rāmāyaṇa</title>
  <link rel="stylesheet" href="/search/fonts/fonts.css">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      background: #FFFDF9;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .iskcon-symbol-wrap {
      text-align: center;
      margin-bottom: 14px;
    }
    .iskcon-symbol {
      width: 80px;
      height: 80px;
      object-fit: contain;
      border-radius: 12px;
      padding: 4px;
      background: #FFFFFF;
      box-shadow: 0 4px 16px rgba(184, 58, 36, 0.15);
      border: 1px solid rgba(200, 147, 10, 0.25);
      transition: transform .25s ease;
    }
    .iskcon-symbol:hover {
      transform: scale(1.06);
    }
    .card {
      background: #fff;
      border: 1px solid rgba(200,147,10,0.22);
      border-top: 4px solid #E8650A;
      border-radius: 14px;
      padding: 36px 32px 32px;
      width: 100%;
      max-width: 380px;
      box-shadow: 0 4px 30px rgba(13,33,68,0.10);
    }
    .brand { text-align: center; margin-bottom: 24px; }
    .brand-deva {
      font-family: 'Noto Serif Devanagari', serif;
      font-size: 1.25rem;
      font-weight: 600;
      color: #0D2144;
      display: block;
      line-height: 1.3;
    }
    .brand-latin {
      font-family: 'Crimson Pro', serif;
      font-size: .82rem;
      color: #8A7055;
      font-style: italic;
      display: block;
      margin-top: 3px;
    }
    .divider {
      height: 1px;
      background: linear-gradient(to right, transparent, rgba(200,147,10,0.3), transparent);
      margin: 0 0 22px;
    }
    label {
      display: block;
      font-size: .74rem;
      font-weight: 700;
      letter-spacing: .06em;
      color: #4A3820;
      margin-bottom: 6px;
      text-transform: uppercase;
    }
    .input-wrap { position: relative; margin-bottom: 14px; }
    input {
      width: 100%;
      padding: 11px 14px;
      border: 1.5px solid rgba(200,147,10,0.28);
      border-radius: 8px;
      font-family: 'Inter', sans-serif;
      font-size: .93rem;
      color: #1A1208;
      background: #FFFDF9;
      outline: none;
      transition: border-color .2s, box-shadow .2s;
    }
    input:focus {
      border-color: #E8650A;
      box-shadow: 0 0 0 3px rgba(232,101,10,0.12);
      background: #fff;
    }
    button[type="submit"] {
      width: 100%;
      padding: 12px;
      background: #0D2144;
      color: #fff;
      border: none;
      border-radius: 100px;
      font-family: 'Inter', sans-serif;
      font-size: .9rem;
      font-weight: 600;
      cursor: pointer;
      transition: background .2s, transform .1s;
      letter-spacing: .04em;
      margin-top: 6px;
    }
    button[type="submit"]:hover { background: #1A3A6B; }
    button[type="submit"]:active { transform: scale(.98); }
    .error {
      background: #FFF0E6;
      border: 1px solid rgba(232,101,10,0.3);
      border-radius: 8px;
      color: #C4520A;
      font-size: .82rem;
      font-weight: 500;
      padding: 10px 14px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .footer-note {
      text-align: center;
      font-size: .72rem;
      color: #B8A080;
      margin-top: 18px;
      font-family: 'Crimson Pro', serif;
      font-style: italic;
    }
    @media (max-width: 400px) {
      .card { padding: 28px 20px 24px; }
    }
  </style>
</head>
<body>
  <div class="iskcon-symbol-wrap">
    <img src="/search/iskcon_lotus_symbol.jpg" alt="ISKCON Lotus Symbol" class="iskcon-symbol">
  </div>
  <div class="card">
    <div class="brand">
      <span class="brand-deva">श्रीवाल्मीकिरामायणम्</span>
      <span class="brand-latin">Śrī Vālmīki Rāmāyaṇa — Digital Corpus</span>
    </div>
    <div class="divider"></div>
    {% if error %}
    <div class="error">⚠ {{ error }}</div>
    {% endif %}
    <form method="POST" action="/login" autocomplete="off">
      <label for="username">Username</label>
      <div class="input-wrap">
        <input type="text" id="username" name="username"
               placeholder="Enter your username" required autofocus
               value="{{ username_val or '' }}">
      </div>
      <label for="password">Password</label>
      <div class="input-wrap">
        <input type="password" id="password" name="password"
               placeholder="Enter your password" required>
      </div>
      <button type="submit">Sign In</button>
    </form>
    <p class="footer-note">🔒 Secured · For authorised access only</p>
  </div>
</body>
</html>"""


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    # Already logged in → go home
    if session.get("logged_in"):
        return redirect("/")

    error = None
    username_val = ""
    if request.method == "POST":
        username_val = request.form.get("username", "").strip()
        password     = request.form.get("password", "")

        if username_val == USERNAME and check_password_hash(PASSWORD_HASH, password):
            session.permanent = True
            session["logged_in"] = True
            session["user"]      = username_val
            next_url = request.args.get("next", "/")
            if not next_url.startswith("/"):
                next_url = "/"
            return redirect(next_url)
        else:
            error = "Invalid username or password. Please try again."

    return render_template_string(LOGIN_HTML, error=error, username_val=username_val)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════════════════
#  STATIC FILES  (all login-protected)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    return send_from_directory(SEARCH_DIR, "index.html")


@app.route("/search/app.js")
@login_required
def serve_js():
    return send_from_directory(SEARCH_DIR, "app.js")


@app.route("/search/style.css")
@login_required
def serve_css():
    return send_from_directory(SEARCH_DIR, "style.css")


@app.route("/search/fonts/fonts.css")
@login_required
def serve_fonts_css():
    return send_from_directory(os.path.join(SEARCH_DIR, "fonts"), "fonts.css")


@app.route("/search/fonts/<path:filename>")
@login_required
def serve_fonts(filename):
    return send_from_directory(os.path.join(SEARCH_DIR, "fonts"), filename)


# Serve any other file from search/ that might be requested
@app.route("/search/<path:filename>")
@login_required
def serve_search_static(filename):
    return send_from_directory(SEARCH_DIR, filename)


# ══════════════════════════════════════════════════════════════════════════════
#  API ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/stats")
@login_required
@limiter.limit("60 per minute")
def stats():
    conn = get_db()
    if conn is None:
        return jsonify({"error": "Database not found."}), 503
    data = get_stats(conn)
    conn.close()
    return jsonify(data)


@app.route("/verse/<path:ref>")
@login_required
@limiter.limit("120 per minute")
def get_verse(ref: str):
    if not re.match(r"^\d+\.\d+\.[\d\-]+$", ref.strip()):
        return jsonify({"error": "Invalid verse reference. Use format: K.C.V  e.g. 1.1.1"}), 400

    parts = ref.strip().split(".")
    try:
        kanda_num   = int(parts[0])
        chapter_num = int(parts[1])
        verse_num   = int(parts[2].split("-")[0])
    except (ValueError, IndexError):
        return jsonify({"error": f"Invalid reference: {ref}"}), 400

    conn = get_db()
    if conn is None:
        return jsonify({"error": "Database not found."}), 503

    row = get_verse_by_ref(conn, kanda_num, chapter_num, verse_num)
    conn.close()

    if row is None:
        return jsonify({"error": f"Verse {ref} not found in database."}), 404

    return jsonify(verse_to_dict(row))


@app.route("/chapter/<int:kanda_num>/<int:chapter_num>")
@login_required
@limiter.limit("60 per minute")
def get_chapter(kanda_num: int, chapter_num: int):
    if not (1 <= kanda_num <= 7 and 1 <= chapter_num <= 500):
        return jsonify({"error": "Invalid kanda or chapter number."}), 400

    conn = get_db()
    if conn is None:
        return jsonify({"error": "Database not found."}), 503

    rows = get_chapter_verses(conn, kanda_num, chapter_num)
    conn.close()

    if not rows:
        return jsonify({"error": f"No verses found for {kanda_num}.{chapter_num}"}), 404

    return jsonify({
        "kanda_num":   kanda_num,
        "kanda_name":  KANDA_NAMES.get(kanda_num, ""),
        "chapter_num": chapter_num,
        "verses":      [verse_to_dict(r) for r in rows],
    })


@app.route("/search")
@login_required
@limiter.limit("30 per minute")
def search():
    raw_q = request.args.get("q", "").strip()
    if not raw_q:
        return jsonify({"error": "Missing query parameter: q"}), 400

    q = clean_query(raw_q)
    if not q:
        return jsonify({"error": "Query contains invalid characters."}), 400

    kanda_num   = request.args.get("kanda",   type=int)
    chapter_num = request.args.get("chapter", type=int)
    limit       = min(request.args.get("limit",  default=30, type=int), 100)
    offset      = max(request.args.get("offset", default=0,  type=int), 0)

    conn = get_db()
    if conn is None:
        return jsonify({"error": "Database not found."}), 503

    try:
        rows = search_verses(conn, q, kanda_num, chapter_num, limit, offset)
    except sqlite3.OperationalError:
        conn.close()
        return jsonify({"error": "Search failed. Try a simpler query."}), 400

    conn.close()
    return jsonify({
        "query":   q,
        "total":   len([verse_to_dict(r) for r in rows]),
        "results": [verse_to_dict(r) for r in rows],
    })


@app.route("/kandas")
@login_required
@limiter.limit("60 per minute")
def kandas():
    conn = get_db()
    if conn is None:
        return jsonify({"kandas": []})
    rows = conn.execute("""
        SELECT kanda_num, kanda_name,
               COUNT(*) as verse_count,
               COUNT(DISTINCT chapter_num) as chapter_count
        FROM verses
        GROUP BY kanda_num
        ORDER BY kanda_num
    """).fetchall()
    conn.close()
    return jsonify({"kandas": [dict(r) for r in rows]})


@app.route("/chapters/<int:kanda_num>")
@login_required
@limiter.limit("60 per minute")
def chapters(kanda_num: int):
    if not (1 <= kanda_num <= 7):
        return jsonify({"error": "Invalid kanda number."}), 400

    conn = get_db()
    if conn is None:
        return jsonify({"chapters": []})

    rows = conn.execute("""
        SELECT chapter_num, chapter_title, COUNT(*) as verse_count
        FROM verses
        WHERE kanda_num = ?
        GROUP BY chapter_num
        ORDER BY chapter_num
    """, (kanda_num,)).fetchall()
    conn.close()
    return jsonify({"kanda_num": kanda_num, "chapters": [dict(r) for r in rows]})


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/search") or request.path.startswith("/verse") or \
       request.path.startswith("/stats") or request.path.startswith("/kandas"):
        return jsonify({"error": "Not found."}), 404
    return redirect(url_for("login"))


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Too many requests. Please slow down and try again."}), 429


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error."}), 500


# ══════════════════════════════════════════════════════════════════════════════
#  LOCAL DEV STARTUP
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("🕉  Sri Valmiki Ramayana — Secured Search API")
    print("─" * 50)
    print(f"📂  Database : {DB_PATH}")
    print(f"   Exists   : {os.path.exists(DB_PATH)}")
    print(f"🌐  Open     : http://localhost:5000")
    print(f"🔐  Username : {USERNAME}")
    print(f"🔐  Password : (set via RAMAYANA_PASSWORD env var)")
    print("─" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
