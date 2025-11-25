"""
SQLite storage for user flight choices.

Schema:
  - flight_choices: stores selected offers with basic info for recall.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List, Optional


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS flight_choices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id TEXT,
            airline TEXT,
            price REAL,
            currency TEXT,
            cabin_class TEXT,
            origin TEXT,
            destination TEXT,
            departure_date TEXT,
            return_date TEXT,
            passenger_ids TEXT,
            chosen_at INTEGER
        )
        """
    )
    conn.commit()


def save_flight_choice(choice: Dict[str, Any], db_path: str = "flight_choices.sqlite") -> int:
    """
    Persist a selected flight offer.

    Expected keys in `choice` (best-effort): offer_id, airline, price, currency,
    cabin_class, origin, destination, departure_date, return_date, passenger_ids (list).

    Returns:
        inserted row id.
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO flight_choices
        (offer_id, airline, price, currency, cabin_class, origin, destination, departure_date, return_date, passenger_ids, chosen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            choice.get("offer_id"),
            choice.get("airline"),
            choice.get("price"),
            choice.get("currency"),
            choice.get("cabin_class"),
            choice.get("origin"),
            choice.get("destination"),
            choice.get("departure_date"),
            choice.get("return_date"),
            ",".join(choice.get("passenger_ids", [])) if isinstance(choice.get("passenger_ids"), list) else None,
            int(time.time()),
        ),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def load_flight_choices(limit: int = 10, db_path: str = "flight_choices.sqlite") -> List[Dict[str, Any]]:
    """
    Retrieve recent saved flight choices.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM flight_choices ORDER BY chosen_at DESC LIMIT ?",
        (max(1, limit),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
