"""Server-side storage for applications and drafts: one SQLite file, src/backend/data/applications.db.

    put(kind, id, data)   save (or update) one item; an update keeps its creation time
                          unless renew=True
    get(kind, id)         the item, or None if it's unknown or expired (TTL_SECONDS per kind)
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
TTL_SECONDS = {"queues": 24 * 60 * 60}   # a queue of approved jobs can take a day to work through


def _ttl(kind: str) -> int:
    return TTL_SECONDS.get(kind, EXPIRES_SECONDS)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS items (kind TEXT, id TEXT, created REAL, data TEXT, "
                 "PRIMARY KEY (kind, id))")
    return conn


def put(kind: str, item_id: str, data: dict, renew: bool = False) -> None:
    """renew=True also restarts the item's expiry clock (e.g. a new queue replacing an old one)."""
    update = "data = excluded.data" + (", created = excluded.created" if renew else "")
    with closing(_connect()) as conn, conn:          # second "conn": commit, or roll back on error
        conn.execute(f"INSERT INTO items VALUES (?, ?, ?, ?) ON CONFLICT (kind, id) DO UPDATE SET {update}",
                     (kind, item_id, time.time(), json.dumps(data)))


def get(kind: str, item_id: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT data FROM items WHERE kind = ? AND id = ? AND created > ?",
                           (kind, item_id, time.time() - _ttl(kind))).fetchone()
    return json.loads(row[0]) if row else None


def purge() -> int:
    now, deleted = time.time(), 0
    with closing(_connect()) as conn, conn:
        for kind, ttl in TTL_SECONDS.items():
            deleted += conn.execute("DELETE FROM items WHERE kind = ? AND created <= ?", (kind, now - ttl)).rowcount
        marks = ",".join("?" * len(TTL_SECONDS))
        deleted += conn.execute(f"DELETE FROM items WHERE kind NOT IN ({marks}) AND created <= ?",
                                (*TTL_SECONDS, now - EXPIRES_SECONDS)).rowcount
    return deleted