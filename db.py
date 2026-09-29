"""SQLite cache so repeated runs don't re-hit paid APIs (and demos work offline)."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "copilot.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS api_cache (
               cache_key TEXT PRIMARY KEY,
               payload   TEXT NOT NULL,
               created   TEXT NOT NULL
           )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
               id         INTEGER PRIMARY KEY AUTOINCREMENT,
               query      TEXT NOT NULL,
               created    TEXT NOT NULL,
               result     TEXT NOT NULL
           )"""
    )
    return conn


def cache_get(key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT payload FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def cache_set(key: str, payload) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO api_cache VALUES (?, ?, ?)",
            (key, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )


def save_run(query: str, result: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (query, created, result) VALUES (?, ?, ?)",
            (query, datetime.now(timezone.utc).isoformat(), json.dumps(result, default=str)),
        )
        return cur.lastrowid


def list_runs(limit: int = 20):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, query, created FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
