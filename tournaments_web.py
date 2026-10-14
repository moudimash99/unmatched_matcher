"""
Tournament pages and API (/tournaments), behind one shared password.

Each password opens its own tournaments: anyone can make a password on the login page
(a "space"), and only that password sees the tournaments created with it.

Configuration (environment, or a .env file next to app.py, which is gitignored):
  SECRET_KEY                 signs the login cookie (required; same value for every worker)
  TOURNAMENT_PASSWORD_HASH   optional: sha256 hex of the first password (the old app's PASSWORD_HASH
                             works too). Logging in with it makes its space and gives it every
                             tournament that has no owner yet (from before passwords had spaces).
  TOURNAMENT_SIGNUP          "0" turns off making new passwords on the login page
  TOURNAMENT_DATA_DIR        where tournaments are saved (default: data/tournaments)
Without SECRET_KEY the pages say the feature isn't set up.
Both secrets stay out of git: the repo is public, and anyone with SECRET_KEY could forge a login.
"""
import hashlib
import hmac
import json
import os
import threading
import time

from flask import Blueprint, abort, current_app, jsonify, redirect, request, session, url_for

import tournaments as T


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# Wrong passwords: after LOGIN_MAX_FAILURES from one address within LOGIN_WINDOW_SECONDS, that
# address has to wait out the window. Kept per worker process, which is enough to stop guessing.
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
_failures = {}
_failures_lock = threading.Lock()


def _client_address():
    # The site is reached through a Cloudflare tunnel, so nginx's X-Real-IP is the tunnel's address for
    # every visitor; Cloudflare passes the visitor's own address in CF-Connecting-IP.
    return (request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP")
            or request.remote_addr or "?")


def _recent_failures(addr, now):
    return [t for t in _failures.get(addr, []) if now - t < LOGIN_WINDOW_SECONDS]


def login_blocked(addr, now=None):
    now = now or time.time()
    with _failures_lock:
        return len(_recent_failures(addr, now)) >= LOGIN_MAX_FAILURES


def record_failure(addr, now=None):
    now = now or time.time()
    with _failures_lock:
        _failures[addr] = _recent_failures(addr, now) + [now]


# New passwords: at most SIGNUP_MAX per address per SIGNUP_WINDOW_SECONDS, so nobody can fill the disk
SIGNUP_MAX = 5
SIGNUP_WINDOW_SECONDS = 24 * 60 * 60
MIN_PASSWORD_LENGTH = 6
_signups = {}


def signup_allowed(addr, now=None):
    now = now or time.time()
    with _failures_lock:
        _signups[addr] = [t for t in _signups.get(addr, []) if now - t < SIGNUP_WINDOW_SECONDS]
        return len(_signups[addr]) < SIGNUP_MAX


def record_signup(addr, now=None):
    now = now or time.time()
    with _failures_lock:
        _signups.setdefault(addr, []).append(now)


def create_blueprint(engine, render_tool, fighters_by_id, all_sets, get_collection):
    bp = Blueprint("tournaments", __name__)

    def store():
        return T.TournamentStore(current_app.config["TOURNAMENT_DATA_DIR"])

    def spaces():
        return T.SpaceStore(current_app.config["TOURNAMENT_DATA_DIR"])

    def configured():
        return bool(current_app.secret_key)

    def signup_enabled():
        return current_app.config.get("TOURNAMENT_SIGNUP", True)

    def space():
        """The logged-in password's space id, or None."""
        sid = session.get("tournament_space") if configured() else None
        return sid if sid and spaces().exists(sid) else None

    def authed():
        return space() is not None

    def owned(t):
        return t if (t and t.get("owner") == space()) else None

    def log_in(sid):
        session["tournament_space"] = sid
        session.permanent = True

    def claim_unowned(sid):
        """Tournaments from before passwords had spaces go to the first (legacy) password."""
        st = store()
        for t in st.list():
            if not t.get("owner"):
                st.save(dict(t, owner=sid), t["version"], "Moved to its password's space")

    def win_pct(a, b):
        if not a or not b or a == b or a not in fighters_by_id or b not in fighters_by_id:
            return None
        return engine.estimate_win_rate(a, b)

    def fairness(a, b):
        return engine._calculate_matchup_fairness(a, b)

    def view(t):
        """The tournament plus everything the page shows that's worked out from it."""
        matches = T.match_index(t)
        out = []
        for m in t["matches"]:
            top, bot = T.resolve(t, m["top"], matches), T.resolve(t, m["bot"], matches)
            pct = win_pct(top, bot)
            games = engine.games_played(top, bot) if pct is not None else 0
            nxt = T.consumers(t, m["id"])
            picks = T.match_picks(t, m, matches)
            out.append(dict(m, top_fighter=top, bot_fighter=bot, status=T.status(t, m, matches),
                            top_player=picks.get("top"), bot_player=picks.get("bot"),
                            win_pct=None if pct is None else round(pct, 1), games=games,
                            next=nxt[0][0]["id"] if nxt else None))
        final = T.final_match(t)
        return {
            **{k: t[k] for k in ("id", "name", "version", "updated", "players", "scoring", "rounds", "bench")},
            "matches": out,
            # Scores include any adjustments; the adjustments themselves aren't sent with the page
            # (they're kept out of sight) and load only from /adjustments when asked for in edit mode.
            "scores": T.scores(t, win_pct),
            "current_round": T.current_round(t),
            "champion": final["winner"] if final else None,
            "notes": T.notes(t),
            "open_winners": [m["id"] for m in T.open_winners(t)],
            "eliminated": sorted(T.losers(t)),
        }

    def progress(t):
        played = sum(1 for m in t["matches"] if m["winner"])
        return {"played": played, "total": len(t["matches"]), "fighters": len(T.all_fighters(t))}

    # -- pages ---------------------------------------------------------------

    @bp.route("/tournaments")
    def index():
        if not authed():
            return render_tool("tournaments.html", configured=configured(), authed=False, signup=signup_enabled(),
                               collection=get_collection(), error=request.args.get("error"),
                               min_password=MIN_PASSWORD_LENGTH)
        items = [dict(t, progress=progress(t), current=T.current_round(t), champion=(T.final_match(t) or {}).get("winner"))
                 for t in store().list(owner=space())]
        return render_tool("tournaments.html", configured=True, authed=True, items=items,
                           all_sets=all_sets, collection=get_collection(),
                           error=request.args.get("error"))

    @bp.route("/tournaments/login", methods=["POST"])
    def login():
        if not configured():
            abort(404)
        addr = _client_address()
        if login_blocked(addr):
            return redirect(url_for("tournaments.index", error="Too many wrong passwords. Try again in 15 minutes."))
        password = request.form.get("password", "")
        sid = spaces().find(password) if password else None
        legacy = current_app.config.get("TOURNAMENT_PASSWORD_HASH")
        if not sid and password and legacy and hmac.compare_digest(password_hash(password), legacy):
            sid = spaces().create(password)
        if sid:
            if legacy and hmac.compare_digest(password_hash(password), legacy):
                claim_unowned(sid)
            log_in(sid)
            return redirect(url_for("tournaments.index"))
        record_failure(addr)
        return redirect(url_for("tournaments.index", error="No tournaments open with that password. Check it, or make a new password below."))

    @bp.route("/tournaments/signup", methods=["POST"])
    def signup():
        if not configured() or not signup_enabled():
            abort(404)
        password = request.form.get("password", "")
        if len(password) < MIN_PASSWORD_LENGTH:
            return redirect(url_for("tournaments.index", error=f"Use at least {MIN_PASSWORD_LENGTH} characters."))
        if password != request.form.get("confirm", ""):
            return redirect(url_for("tournaments.index", error="The two passwords don't match."))
        existing = spaces().find(password)
        if existing:  # it's already someone's password; whoever knows it may open it
            log_in(existing)
            return redirect(url_for("tournaments.index"))
        addr = _client_address()
        if not signup_allowed(addr):
            return redirect(url_for("tournaments.index", error="Too many new passwords from here today. Try again tomorrow."))
        record_signup(addr)
        log_in(spaces().create(password))
        return redirect(url_for("tournaments.index"))

    @bp.route("/tournaments/logout")
    def logout():
        session.pop("tournament_space", None)
        return redirect(url_for("tournaments.index"))

    @bp.route("/tournaments/new", methods=["POST"])
    def create():
        if not authed():
            abort(401)
        fighters = [f for f in request.form.getlist("fighters") if f in fighters_by_id]
        players = [p for p in request.form.getlist("players") if p.strip()]
        try:
            t = T.new_tournament(request.form.get("name"), players, fighters, fairness)
        except T.TournamentError as e:
            return redirect(url_for("tournaments.index", error=str(e)))
        t = store().create(dict(t, owner=space()))
        return redirect(url_for("tournaments.page", tid=t["id"]))

    @bp.route("/tournaments/import", methods=["POST"])
    def import_old():
        if not authed():
            abort(401)
        try:
            bracket = json.load(request.files["bracket"])
            state = json.load(request.files["state"]) if request.files.get("state") else {}
            names = {"P1": request.form.get("p1") or "P1", "P2": request.form.get("p2") or "P2"}
            t = T.import_legacy(bracket, state, request.form.get("name") or "Imported tournament", names)
        except (KeyError, ValueError, TypeError) as e:
            return redirect(url_for("tournaments.index", error=f"Couldn't import those files: {e}"))
        unknown = sorted(f for f in T.all_fighters(t) if f not in fighters_by_id)
        if unknown:
            return redirect(url_for("tournaments.index", error="Unknown fighters in the bracket: " + ", ".join(unknown)))
        t = store().create(dict(t, owner=space()))
        return redirect(url_for("tournaments.page", tid=t["id"]))

    @bp.route("/tournaments/<tid>/delete", methods=["POST"])
    def delete(tid):
        if not authed():
            abort(401)
        if owned(store().get(tid)):
            store().delete(tid)
        return redirect(url_for("tournaments.index"))

    @bp.route("/tournaments/<tid>")
    def page(tid):
        if not authed():
            return redirect(url_for("tournaments.index"))
        t = owned(store().get(tid))
        if not t:
            abort(404)
        return render_tool("tournament.html", js_matchups=True, tournament=view(t), all_sets=all_sets,
                           collection=get_collection())

    # -- API -----------------------------------------------------------------

    def api_guard(tid):
        if not authed():
            abort(401)
        t = owned(store().get(tid))
        if not t:
            abort(404)
        return t

    @bp.route("/api/tournaments/<tid>")
    def api_get(tid):
        t = api_guard(tid)
        if request.args.get("since") == str(t["version"]):
            return "", 204
        return jsonify(view(t))

    @bp.route("/api/tournaments/<tid>/op", methods=["POST"])
    def api_op(tid):
        t = api_guard(tid)
        body = request.get_json(silent=True) or {}
        if body.get("version") != t["version"]:
            return jsonify({"error": "This tournament changed on another device; it has been reloaded.",
                            "tournament": view(t)}), 409
        try:
            new, summary = T.apply_op(t, body.get("op"), body.get("args"), win_pct)
            new = store().save(new, t["version"], summary)
        except T.TournamentError as e:
            return jsonify({"error": str(e), "tournament": view(t)}), 400
        except T.VersionConflict as e:
            return jsonify({"error": "This tournament changed on another device; it has been reloaded.",
                            "tournament": view(e.args[0])}), 409
        except TimeoutError as e:
            return jsonify({"error": str(e), "tournament": view(t)}), 503
        return jsonify({"summary": summary, "tournament": view(new)})

    @bp.route("/api/tournaments/<tid>/history")
    def api_history(tid):
        api_guard(tid)
        return jsonify([h for h in store().history(tid) if not T.is_adjustment_change(h["summary"])])

    @bp.route("/api/tournaments/<tid>/adjustments")
    def api_adjustments(tid):
        return jsonify(api_guard(tid).get("adjustments", []))

    @bp.route("/api/tournaments/<tid>/restore", methods=["POST"])
    def api_restore(tid):
        t = api_guard(tid)
        body = request.get_json(silent=True) or {}
        old = store().version(tid, body.get("restore"))
        if old is None:
            return jsonify({"error": "That version isn't in the history any more."}), 404
        try:
            new = store().save(dict(old, updated=T._now(), owner=t.get("owner")), t["version"],
                               f"Restored version {body.get('restore')}")
        except T.VersionConflict as e:
            return jsonify({"error": "This tournament changed on another device; it has been reloaded.",
                            "tournament": view(e.args[0])}), 409
        return jsonify({"summary": f"Restored version {body.get('restore')}", "tournament": view(new)})

    return bp


def load_env_file(path):
    """KEY=value lines from a .env file into os.environ (values already set in the environment win)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def configure(app):
    """Reads the tournament settings from the environment (and .env next to app.py)."""
    load_env_file(os.path.join(app.root_path, ".env"))
    app.secret_key = app.secret_key or os.environ.get("SECRET_KEY")
    app.config.setdefault("TOURNAMENT_PASSWORD_HASH",
                          os.environ.get("TOURNAMENT_PASSWORD_HASH") or os.environ.get("PASSWORD_HASH"))
    app.config.setdefault("TOURNAMENT_DATA_DIR", os.environ.get("TOURNAMENT_DATA_DIR", os.path.join("data", "tournaments")))
    app.config.setdefault("TOURNAMENT_SIGNUP", os.environ.get("TOURNAMENT_SIGNUP", "1") != "0")
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 60 * 60 * 24 * 90)
