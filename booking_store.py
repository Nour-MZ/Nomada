"""
Simple SQLite-backed booking store for user bookings (flights/hotels).
"""

from __future__ import annotations

import sqlite3
import time
import json
from typing import List, Dict, Any

DB_PATH = "databases/bookings.sqlite"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            type TEXT NOT NULL,
            ref TEXT,
            title TEXT,
            detail_json TEXT,
            status TEXT DEFAULT 'active',
            created_at INTEGER
        )
        """
    )
    conn.commit()


def save_booking(user_email: str, booking_type: str, ref: str = "", title: str = "", details: Dict[str, Any] | None = None, db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bookings (user_email, type, ref, title, detail_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (user_email, booking_type, ref, title, json.dumps(details or {}), int(time.time())),
    )
    bid = cur.lastrowid
    conn.commit()
    conn.close()
    return bid


def list_bookings(user_email: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM bookings WHERE user_email = ? ORDER BY created_at DESC",
        (user_email,),
    ).fetchall()
    conn.close()
    results: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        try:
            item["detail_json"] = json.loads(item.get("detail_json") or "{}")
        except Exception:
            item["detail_json"] = {}
        results.append(item)
    return results


def cancel_booking_record(user_email: str, ref: str, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    cur = conn.cursor()
    cur.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE user_email = ? AND ref = ?",
        (user_email, ref),
    )
    conn.commit()
    conn.close()
