"""
db.py - tiny SQLite helper. Stores one row per chat so the dashboard can show stats.
SQLite is built into Python, so nothing extra needs to be installed.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("CHATBOT_DB", os.path.join(BASE_DIR, "chatbot.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn


def init_db():
    """Create the table if it does not exist yet."""
    with get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,      -- UTC time, 'YYYY-MM-DD HH:MM:SS'
                user_message TEXT,
                bot_reply TEXT,
                status TEXT NOT NULL,          -- 'ok' or 'error'
                error_text TEXT,
                duration_ms INTEGER,
                mode TEXT                      -- 'demo' or 'live'
            )"""
        )


def log_chat(user_message, bot_reply, status, error_text, duration_ms, mode):
    """Save one chat. Text is shortened so the database stays small."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chats (created_at, user_message, bot_reply, status, error_text, duration_ms, mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, (user_message or "")[:500], (bot_reply or "")[:500], status,
             error_text, duration_ms, mode),
        )


def get_stats():
    """Totals shown in the top strip of the dashboard."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(status='ok'), 0) AS ok, "
            "COALESCE(SUM(status='error'), 0) AS errors, "
            "AVG(CASE WHEN status='ok' THEN duration_ms END) AS avg_ms "
            "FROM chats"
        ).fetchone()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_count = conn.execute(
            "SELECT COUNT(*) FROM chats WHERE date(created_at) = ?", (today,)
        ).fetchone()[0]
    total = row["total"]
    return {
        "total": total,
        "ok": row["ok"],
        "errors": row["errors"],
        "success_rate": round(row["ok"] * 100 / total, 1) if total else None,
        "avg_ms": round(row["avg_ms"]) if row["avg_ms"] is not None else None,
        "today": today_count,
    }


def get_daily(days=7):
    """Chats per day for the last N days (days with no chats show as 0)."""
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date(created_at) AS day, "
            "SUM(status='ok') AS ok, SUM(status='error') AS errors "
            "FROM chats WHERE date(created_at) >= ? GROUP BY day",
            (start,),
        ).fetchall()
    found = {r["day"]: (r["ok"] or 0, r["errors"] or 0) for r in rows}
    result = []
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        ok, errors = found.get(day, (0, 0))
        result.append({"date": day, "ok": ok, "errors": errors})
    return result


def get_recent(limit=15):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT created_at, user_message, bot_reply, status, error_text, duration_ms "
            "FROM chats ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_top_errors(limit=5):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT error_text AS error, COUNT(*) AS count FROM chats "
            "WHERE status='error' GROUP BY error_text ORDER BY count DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
