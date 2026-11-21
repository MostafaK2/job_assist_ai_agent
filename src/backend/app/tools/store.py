"""Server-side storage for applications and drafts: one SQLite file, src/backend/data/applications.db.

    put(kind, id, data)   save (or update) one item; an update keeps its creation time
    get(kind, id)         the item, or None if it's unknown or older than EXPIRES_SECONDS
    purge()               delete expired items

It holds private answers (email, phone, self-ID): keep data/*.db out of git.
"""
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from app.config import PROFILE_PATH

DB_PATH = Path(PROFILE_PATH).resolve().parent / "applications.db"   # next to profile.json
EXPIRES_SECONDS = 2 * 60 * 60


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS items (kind TEXT, id TEXT, created REAL, data TEXT, "
                 "PRIMARY KEY (kind, id))")
    return conn


def put(kind: str, item_id: str, data: dict) -> None:
    with closing(_connect()) as conn, conn:          # second "conn": commit, or roll back on error
        conn.execute("INSERT INTO items VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (kind, id) DO UPDATE SET data = excluded.data",
                     (kind, item_id, time.time(), json.dumps(data)))


def get(kind: str, item_id: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT data FROM items WHERE kind = ? AND id = ? AND created > ?",
                           (kind, item_id, time.time() - EXPIRES_SECONDS)).fetchone()
    return json.loads(row[0]) if row else None


def purge() -> int:
    with closing(_connect()) as conn, conn:
        return conn.execute("DELETE FROM items WHERE created <= ?", (time.time() - EXPIRES_SECONDS,)).rowcount