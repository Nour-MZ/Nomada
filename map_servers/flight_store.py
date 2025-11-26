"""
SQLite storage for user flight choices.

Schema:
  - flight_choices: stores selected offers with basic info for recall.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List, Optional
import json

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

    # Tables for full flight search results
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS flight_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER,
            query_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS flight_offers (
            offer_id TEXT PRIMARY KEY,
            search_id INTEGER,
            airline TEXT,
            total_amount TEXT,
            currency TEXT,
            cabin_class TEXT,
            owner_name TEXT,
            emissions_kg TEXT,
            departure_at TEXT,
            return_departure_at TEXT,
            expires_at TEXT,
            payment_required_by TEXT,
            refundable_allowed INTEGER,
            passenger_ids TEXT,
            duration_out TEXT,
            duration_return TEXT,
            offer_url TEXT,
            image_url TEXT,
            raw_json TEXT
        )
        """
    )
    # Add new columns to legacy tables (best effort)
    for col, coldef in [
        ("departure_at", "TEXT"),
        ("return_departure_at", "TEXT"),
        ("expires_at", "TEXT"),
        ("payment_required_by", "TEXT"),
        ("refundable_allowed", "INTEGER"),
        ("passenger_ids", "TEXT"),
        ("duration_out", "TEXT"),
        ("duration_return", "TEXT"),
        ("offer_url", "TEXT"),
        ("image_url", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE flight_offers ADD COLUMN {col} {coldef}")
        except sqlite3.OperationalError:
            pass
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


def save_flight_search_results(
    offers: List[Dict[str, Any]],
    query: Optional[Dict[str, Any]] = None,
    db_path: str = "flight_choices.sqlite",
) -> int:
    """
    Persist flight search offers into SQLite for later retrieval.

    Args:
        offers: list of offer dicts (e.g., response from search_flights_impl).
        query: optional dict capturing the search parameters (origin/destination/dates).
        db_path: sqlite path.

    Returns:
        search_id of the inserted search row.
    """
    conn = sqlite3.connect(db_path, timeout=5)
    _ensure_schema(conn)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO flight_searches (created_at, query_json) VALUES (?, ?)",
        (int(time.time()), json.dumps(query or {})),
    )
    search_id = cur.lastrowid

    for offer in offers or []:
        # Extract helpful fields
        slices = offer.get("slices") or []
        first_slice = slices[0] if slices else {}
        return_slice = slices[1] if len(slices) > 1 else {}
        dep_at = None
        ret_dep_at = None
        if first_slice.get("segments"):
            dep_at = first_slice["segments"][0].get("departing_at")
        if return_slice.get("segments"):
            ret_dep_at = return_slice["segments"][0].get("departing_at")

        refundable = None
        try:
            refundable = bool(
                ((offer.get("conditions") or {}).get("refund_before_departure") or {}).get("allowed")
            )
        except Exception:
            refundable = None

        passenger_ids = []
        for p in offer.get("passengers") or []:
            if p.get("id"):
                passenger_ids.append(p["id"])

        duration_out = first_slice.get("duration") if isinstance(first_slice, dict) else None
        duration_ret = return_slice.get("duration") if isinstance(return_slice, dict) else None

        cur.execute(
            """
            INSERT OR REPLACE INTO flight_offers
            (offer_id, search_id, airline, total_amount, currency, cabin_class, owner_name, emissions_kg,
             departure_at, return_departure_at, expires_at, payment_required_by, refundable_allowed, passenger_ids,
             duration_out, duration_return, offer_url, image_url, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer.get("id"),
                search_id,
                offer.get("airline") or offer.get("owner", {}).get("name"),
                offer.get("total_amount") or offer.get("price") or offer.get("total"),
                offer.get("total_currency") or offer.get("currency"),
                offer.get("cabin_class"),
                (offer.get("owner") or {}).get("name"),
                offer.get("total_emissions_kg"),
                dep_at,
                ret_dep_at,
                offer.get("expires_at"),
                (offer.get("payment_requirements") or {}).get("payment_required_by"),
                1 if refundable else 0 if refundable is False else None,
                ",".join(passenger_ids) if passenger_ids else None,
                duration_out,
                duration_ret,
                offer.get("url"),
                offer.get("image_url") or offer.get("owner", {}).get("logo_symbol_url"),
                json.dumps(offer),
            ),
        )

    conn.commit()
    conn.close()
    return search_id


def load_latest_search_offers(
    db_path: str = "flight_choices.sqlite",
) -> List[Dict[str, Any]]:
    """
    Fetch all offers from the most recent flight search.

    Returns a list of dicts with offer_id, passenger_ids (list), and raw offer JSON.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    cur = conn.cursor()

    latest = cur.execute(
        "SELECT id FROM flight_searches ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not latest:
        conn.close()
        return []

    search_id = latest["id"]
    rows = cur.execute(
        "SELECT offer_id, passenger_ids, raw_json FROM flight_offers WHERE search_id = ? ORDER BY rowid ASC",
        (search_id,),
    ).fetchall()
    conn.close()

    offers: List[Dict[str, Any]] = []
    for row in rows:
        pax_ids = []
        if row["passenger_ids"]:
            pax_ids = [p for p in row["passenger_ids"].split(",") if p]
        offers.append(
            {
                "offer_id": row["offer_id"],
                "passenger_ids": pax_ids,
                "raw": json.loads(row["raw_json"]) if row["raw_json"] else {},
            }
        )
    return offers
