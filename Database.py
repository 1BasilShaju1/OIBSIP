"""
database.py
===========
Your original script had:

    SETTINGS = load_settings()      # ONE global dict, ONE json file
    reminders = []                  # ONE global list
    notes = []                      # ONE global list

That's fine for a desktop app you alone run. It's broken for a website:
if two strangers visit your URL at the same time, they'd be reading and
overwriting the SAME settings, SAME reminders, SAME notes. User B could
see User A's reminders. User B renaming "Sky" to "Bob" would rename it
for User A too.

The fix: every row is tagged with a user_id. Where does user_id come
from? The browser generates a random UUID the first time it visits and
stores it in a cookie/localStorage, then sends it with every request.
No login system needed for a demo - just "this browser session = this
user".
"""

import sqlite3
import json
import datetime
from contextlib import contextmanager

DB_PATH = "sky.db"

DEFAULT_SETTINGS = {
    "ai_name": "Sky",
    "user_name": "Boss",
    "default_city": "Thrissur",
}


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                task TEXT NOT NULL,
                time TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def get_settings(user_id):
    with get_db() as conn:
        row = conn.execute("SELECT data FROM settings WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            settings = DEFAULT_SETTINGS.copy()
            settings.update(json.loads(row["data"]))
            return settings
        return DEFAULT_SETTINGS.copy()


def save_settings(user_id, settings):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (user_id, data) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
            (user_id, json.dumps(settings))
        )


def add_reminder(user_id, task, time_str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reminders (user_id, task, time, created_at) VALUES (?, ?, ?, ?)",
            (user_id, task, time_str, datetime.datetime.now().isoformat())
        )


def get_reminders(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, task, time FROM reminders WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_reminder(user_id, reminder_id):
    with get_db() as conn:
        conn.execute("DELETE FROM reminders WHERE user_id = ? AND id = ?", (user_id, reminder_id))


def add_note(user_id, text):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO notes (user_id, text, created_at) VALUES (?, ?, ?)",
            (user_id, text, datetime.datetime.now().isoformat())
        )


def get_notes(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, text, created_at FROM notes WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
