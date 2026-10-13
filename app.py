"""A small Kudos app for demonstrating a spec-driven feature."""

from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (
    Flask,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


DEMO_USERS = [
    (1, "Alex Morgan", "alex@example.test", "employee"),
    (2, "Sam Taylor", "sam@example.test", "employee"),
    (3, "Jamie Chen", "jamie@example.test", "employee"),
    (4, "Morgan Admin", "admin@example.test", "admin"),
]


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("KUDOS_SECRET_KEY", "local-demo-key-change-before-deploy"),
        DATABASE=os.environ.get(
            "KUDOS_DATABASE", str(Path(app.instance_path) / "kudos.sqlite")
        ),
        APP_ENV=os.environ.get("APP_ENV", "development"),
        DEMO_MODE=os.environ.get("KUDOS_DEMO_MODE", "true").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",
    )
    if test_config:
        app.config.update(test_config)

    if app.config["APP_ENV"] == "production" and app.config["DEMO_MODE"]:
        raise RuntimeError("Demo sign-in must be disabled in production.")
    if app.config["APP_ENV"] == "production" and not os.environ.get("KUDOS_SECRET_KEY"):
        raise RuntimeError("Set KUDOS_SECRET_KEY before running in production.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_db(app)

    @app.before_request
    def prepare_request() -> None:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    @app.context_processor
    def add_template_helpers():
        return {"csrf_token": lambda: session.get("csrf_token", "")}

    @app.get("/")
    def home():
        user = get_current_user()
        if not user:
            return render_template("login.html", demo_users=DEMO_USERS)
        colleagues = get_db().execute(
            "SELECT id, name FROM users WHERE is_active = 1 AND id != ? ORDER BY name",
            (user["id"],),
        ).fetchall()
        return render_template("dashboard.html", user=user, colleagues=colleagues)

    @app.post("/login")
    def login():
        if not app.config["DEMO_MODE"]:
            return "Sign in is provided by the organisation's SSO.", 501
        if not valid_csrf():
            return "Your session expired. Refresh the page and try again.", 400
        user_id = request.form.get("user_id", "")
        user = get_db().execute(
            "SELECT id FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        if not user:
            return render_template(
                "login.html", demo_users=DEMO_USERS, error="Choose an active demo user."
            ), 400
        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("home"))

    @app.post("/logout")
    def logout():
        if not valid_csrf():
            return "Your session expired. Refresh the page and try again.", 400
        session.clear()
        return redirect(url_for("home"))

    @app.get("/api/users")
    @employee_required
    def search_users():
        query = request.args.get("q", "").strip()
        if query and len(query) < 2:
            return jsonify(error="Enter at least two letters to search."), 400
        current = get_current_user()
        sql = "SELECT id, name FROM users WHERE is_active = 1 AND id != ?"
        params: list[Any] = [current["id"]]
        if query:
            sql += " AND lower(name) LIKE ?"
            params.append(f"%{query.lower()}%")
        sql += " ORDER BY name LIMIT 20"
        users = get_db().execute(sql, params).fetchall()
        return jsonify(users=[dict(row) for row in users])

    @app.post("/api/kudos")
    @employee_required
    def create_kudos():
        if not valid_csrf():
            return jsonify(error="Your session expired. Refresh and try again."), 400
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Send a valid kudos form."), 400

        message = body.get("message")
        recipient_id = body.get("recipient_id")
        idempotency_key = body.get("idempotency_key")
        if not isinstance(message, str) or not message.strip():
            return jsonify(error="Write a message before submitting."), 400
        message = message.strip()
        if len(message) > 500:
            return jsonify(error="Messages must be 500 characters or fewer."), 400
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 100:
            return jsonify(error="Refresh the page and try submitting again."), 400
        try:
            recipient_id = int(recipient_id)
        except (TypeError, ValueError):
            return jsonify(error="Choose a colleague from the list."), 400

        sender = get_current_user()
        if recipient_id == sender["id"]:
            return jsonify(error="You cannot send kudos to yourself."), 400
        recipient = get_db().execute(
            "SELECT id FROM users WHERE id = ? AND is_active = 1", (recipient_id,)
        ).fetchone()
        if not recipient:
            return jsonify(error="That colleague is not available."), 400

        db = get_db()
        previous = db.execute(
            "SELECT id FROM kudos WHERE sender_id = ? AND idempotency_key = ?",
            (sender["id"], idempotency_key),
        ).fetchone()
        if previous:
            return jsonify(message="Kudos already submitted.", id=previous["id"]), 200

        created_at = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            """INSERT INTO kudos
               (sender_id, recipient_id, message, created_at, is_visible, idempotency_key)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (sender["id"], recipient_id, message, created_at, idempotency_key),
        )
        db.commit()
        return jsonify(message="Kudos sent!", id=cursor.lastrowid), 201

    @app.get("/api/kudos")
    @employee_required
    def recent_kudos():
        limit = bounded_int(request.args.get("limit"), default=20, minimum=1, maximum=50)
        offset = bounded_int(request.args.get("offset"), default=0, minimum=0, maximum=100000)
        rows = get_db().execute(
            """SELECT k.id, k.message, k.created_at,
                      sender.name AS sender_name, recipient.name AS recipient_name
               FROM kudos AS k
               JOIN users AS sender ON sender.id = k.sender_id
               JOIN users AS recipient ON recipient.id = k.recipient_id
               WHERE k.is_visible = 1 AND k.is_deleted = 0
               ORDER BY k.created_at DESC, k.id DESC LIMIT ? OFFSET ?""",
            (limit + 1, offset),
        ).fetchall()
        has_more = len(rows) > limit
        return jsonify(
            items=[dict(row) for row in rows[:limit]],
            next_offset=offset + limit if has_more else None,
        )

    @app.get("/admin")
    @page_admin_required
    def admin_page():
        return render_template("admin.html", user=get_current_user())

    @app.get("/api/admin/kudos")
    @admin_required
    def admin_kudos():
        rows = get_db().execute(
            """SELECT k.id, k.message, k.created_at, k.is_visible, k.is_deleted,
                      k.moderation_reason, sender.name AS sender_name,
                      recipient.name AS recipient_name
               FROM kudos AS k
               JOIN users AS sender ON sender.id = k.sender_id
               JOIN users AS recipient ON recipient.id = k.recipient_id
               ORDER BY k.created_at DESC, k.id DESC LIMIT 100"""
        ).fetchall()
        return jsonify(items=[dict(row) for row in rows])

    @app.post("/api/admin/kudos/<int:kudos_id>/moderate")
    @admin_required
    def moderate_kudos(kudos_id: int):
        if not valid_csrf():
            return jsonify(error="Your session expired. Refresh and try again."), 400
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Send a valid moderation action."), 400
        action = body.get("action")
        reason = body.get("reason")
        if action not in {"hide", "restore", "delete"}:
            return jsonify(error="Choose hide, restore or delete."), 400
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
            return jsonify(error="Add a reason of up to 500 characters."), 400

        db = get_db()
        kudos = db.execute("SELECT id FROM kudos WHERE id = ?", (kudos_id,)).fetchone()
        if not kudos:
            return jsonify(error="Kudos message not found."), 404
        is_visible = 1 if action == "restore" else 0
        is_deleted = 1 if action == "delete" else 0
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """UPDATE kudos SET is_visible = ?, is_deleted = ?, moderated_by = ?,
                      moderated_at = ?, moderation_reason = ? WHERE id = ?""",
            (is_visible, is_deleted, get_current_user()["id"], now, reason.strip(), kudos_id),
        )
        db.execute(
            """INSERT INTO moderation_history
               (kudos_id, admin_id, action, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (kudos_id, get_current_user()["id"], action, reason.strip(), now),
        )
        db.commit()
        return jsonify(message=f"Message {action} action saved.")

    @app.get("/api/admin/kudos/<int:kudos_id>/history")
    @admin_required
    def moderation_history(kudos_id: int):
        rows = get_db().execute(
            """SELECT h.action, h.reason, h.created_at, u.name AS admin_name
               FROM moderation_history AS h JOIN users AS u ON u.id = h.admin_id
               WHERE h.kudos_id = ? ORDER BY h.created_at DESC""",
            (kudos_id,),
        ).fetchall()
        return jsonify(events=[dict(row) for row in rows])

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app


def init_db(app: Flask) -> None:
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK (role IN ('employee', 'admin')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS kudos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id),
            recipient_id INTEGER NOT NULL REFERENCES users(id),
            message TEXT NOT NULL CHECK (length(trim(message)) BETWEEN 1 AND 500),
            created_at TEXT NOT NULL,
            is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0, 1)),
            moderated_by INTEGER REFERENCES users(id),
            moderated_at TEXT,
            moderation_reason TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
            idempotency_key TEXT,
            CHECK (sender_id != recipient_id),
            UNIQUE (sender_id, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_kudos_feed
            ON kudos (is_visible, is_deleted, created_at DESC);
        CREATE TABLE IF NOT EXISTS moderation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kudos_id INTEGER NOT NULL REFERENCES kudos(id),
            admin_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL CHECK (action IN ('hide', 'restore', 'delete')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO users (id, name, email, role) VALUES (?, ?, ?, ?)",
            [(user_id, name, email, role) for user_id, name, email, role in DEMO_USERS],
        )
    db.commit()
    db.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return get_db().execute(
        "SELECT id, name, email, role FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


def valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    submitted = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    return bool(token and secrets.compare_digest(token, submitted))


def bounded_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value) if value is not None else default
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def employee_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            return jsonify(error="Please sign in first."), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify(error="Please sign in first."), 401
        if user["role"] != "admin":
            return jsonify(error="Administrator access is required."), 403
        return view(*args, **kwargs)

    return wrapped


def page_admin_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("home"))
        if user["role"] != "admin":
            return "Administrator access is required.", 403
        return view(*args, **kwargs)

    return wrapped


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("APP_ENV", "development") != "production")
