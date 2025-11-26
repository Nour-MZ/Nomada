"""
Utilities to persist Hotelbeds search results into a local SQLite database.

Schema (simplified):
  - hotel_searches: one row per search (destination, dates, timestamp)
  - hotels: basic hotel info linked to a search
  - rooms: room types per hotel
  - rates: individual rate options per room (stores cancellation/taxes/promotions/offers as JSON)
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotel_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination TEXT,
            check_in TEXT,
            check_out TEXT,
            created_at INTEGER
        )
        """
    )
    # Hotel images table (even if images not yet fetched)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotel_images (
            hotel_code TEXT PRIMARY KEY,
            images_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotels (
            code TEXT,
            search_id INTEGER,
            name TEXT,
            category TEXT,
            currency TEXT,
            min_rate TEXT,
            max_rate TEXT,
            destination TEXT,
            address TEXT,
            PRIMARY KEY (code, search_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_code TEXT,
            search_id INTEGER,
            code TEXT,
            name TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            hotel_code TEXT,
            search_id INTEGER,
            room_code TEXT,
            rate_key TEXT,
            rate_class TEXT,
            rate_type TEXT,
            net TEXT,
            allotment INTEGER,
            payment_type TEXT,
            board_code TEXT,
            board_name TEXT,
            adults INTEGER,
            children INTEGER,
            cancellation_policies TEXT,
            taxes TEXT,
            promotions TEXT,
            offers TEXT,
            room_images TEXT
        )
        """
    )
    # Ensure room_images column exists in case of legacy DB
    try:
        cur.execute("SELECT room_images FROM rates LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cur.execute("ALTER TABLE rates ADD COLUMN room_images TEXT")
        except Exception:
            pass
    conn.commit()


def save_hotel_search_results(
    results: Dict[str, Any],
    *,
    destination: str,
    check_in: str,
    check_out: str,
    db_path: str = "databases/hotelbeds.sqlite",
) -> int:
    """
    Persist Hotelbeds search results into SQLite.

    Args:
        results: dict returned by search_hotels_impl (expects key "results").
        destination: destination code used for the search.
        check_in: YYYY-MM-DD check-in date.
        check_out: YYYY-MM-DD check-out date.
        db_path: path to SQLite database file.

    Returns:
        search_id (int) for the inserted search row.
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO hotel_searches (destination, check_in, check_out, created_at) VALUES (?, ?, ?, ?)",
        (destination, check_in, check_out, int(time.time())),
    )
    search_id = cur.lastrowid

    hotels: List[Dict[str, Any]] = []
    raw_hotels = results.get("results") if isinstance(results, dict) else []
    if isinstance(raw_hotels, list):
        hotels = raw_hotels

    for h in hotels:
        code = h.get("code")
        cur.execute(
            """
            INSERT OR REPLACE INTO hotels
            (code, search_id, name, category, currency, min_rate, max_rate, destination, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                search_id,
                h.get("name"),
                h.get("category"),
                h.get("currency"),
                h.get("min_rate"),
                h.get("max_rate"),
                h.get("destination"),
                h.get("address"),
            ),
        )

        rooms = h.get("rooms") or []
        for room in rooms:
            cur.execute(
                "INSERT INTO rooms (hotel_code, search_id, code, name) VALUES (?, ?, ?, ?)",
                (code, search_id, room.get("code"), room.get("name")),
            )
            room_id = cur.lastrowid

            rates = room.get("rates") or []
            for rate in rates:
                cur.execute(
                    """
                    INSERT INTO rates
                    (room_id, hotel_code, search_id, room_code, rate_key, rate_class, rate_type, net, allotment, payment_type,
                     board_code, board_name, adults, children, cancellation_policies, taxes, promotions, offers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        room_id,
                        code,
                        search_id,
                        room.get("code"),
                        rate.get("rateKey"),
                        rate.get("rateClass"),
                        rate.get("rateType"),
                        rate.get("net"),
                        rate.get("allotment"),
                        rate.get("paymentType"),
                        rate.get("boardCode"),
                        rate.get("boardName"),
                        rate.get("adults"),
                        rate.get("children"),
                        json.dumps(rate.get("cancellationPolicies")),
                        json.dumps(rate.get("taxes")),
                        json.dumps(rate.get("promotions")),
                        json.dumps(rate.get("offers")),
                    ),
                )

    conn.commit()
    conn.close()
    return search_id

def save_hotel_images(
    hotel_images: Dict[str, List[Dict[str, Any]]],
    db_path: str = "hotelbeds.sqlite",
    attach_to_rates: bool = True,
) -> None:
    """
    Persist hotel images keyed by hotel_code. Images stored as JSON array per hotel.
    If attach_to_rates is True, room-level images (with roomCode) are also stored
    on matching rate rows.
    """
    conn = sqlite3.connect(db_path, timeout=5)
    cur = conn.cursor()
    # Ensure base schema exists so rate updates don't fail
    _ensure_schema(conn)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotel_images (
            hotel_code TEXT PRIMARY KEY,
            images_json TEXT
        )
        """
    )
    # Ensure room_images column exists (best effort)
    if attach_to_rates:
        try:
            cur.execute("SELECT room_images FROM rates LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cur.execute("ALTER TABLE rates ADD COLUMN room_images TEXT")
            except Exception:
                pass

    for code, imgs in hotel_images.items():
        cur.execute(
            "INSERT OR REPLACE INTO hotel_images (hotel_code, images_json) VALUES (?, ?)",
            (code, json.dumps(imgs)),
        )

        if attach_to_rates:
            # Group images by roomCode and update rates for this hotel
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for img in imgs or []:
                rc = img.get("roomCode")
                if not rc:
                    continue
                grouped.setdefault(rc, []).append(img)
            for room_code, imgs_for_room in grouped.items():
                try:
                    cur.execute(
                        "UPDATE rates SET room_images=? WHERE hotel_code=? AND room_code=?",
                        (json.dumps(imgs_for_room), code, room_code),
                    )
                except sqlite3.OperationalError:
                    # rates table might be missing in legacy db; skip silently
                    pass

    conn.commit()
    conn.close()


def load_hotel_search(
    search_id: int | None = None,
    db_path: str = "hotelbeds.sqlite",
) -> Dict[str, Any]:
    """
    Load a saved hotel search (and nested hotels/rooms/rates) from SQLite.

    Args:
        search_id: specific search to load; if None, loads the latest search.
        db_path: path to SQLite database file.

    Returns:
        dict with keys: search (meta), hotels (list with rooms -> rates).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    cur = conn.cursor()

    if search_id is None:
        row = cur.execute(
            "SELECT id, destination, check_in, check_out, created_at FROM hotel_searches ORDER BY id DESC LIMIT 2"
        ).fetchone()
        if not row:
            conn.close()
            return {"error": "No searches found"}
        search_id = row["id"]
    else:
        row = cur.execute(
            "SELECT id, destination, check_in, check_out, created_at FROM hotel_searches WHERE id=?",
            (search_id,),
        ).fetchone()
        if not row:
            conn.close()
            return {"error": f"Search id {search_id} not found"}

    search_meta = dict(row)

    hotels_out: List[Dict[str, Any]] = []
    hotel_rows = cur.execute(
        "SELECT * FROM hotels WHERE search_id=?",
        (search_id,),
    ).fetchall()

    for hrow in hotel_rows:
        hotel = dict(hrow)
        hotel_rooms: List[Dict[str, Any]] = []
        room_rows = cur.execute(
            "SELECT * FROM rooms WHERE hotel_code=? AND search_id=?",
            (hotel["code"], search_id),
        ).fetchall()
        for rrow in room_rows:
            room = dict(rrow)
            rate_rows = cur.execute(
                "SELECT * FROM rates WHERE room_id=?",
                (room["id"],),
            ).fetchall()
            rates_out: List[Dict[str, Any]] = []
            for rate in rate_rows:
                rate_dict = dict(rate)
                # Parse JSON fields back to objects where possible
                for key in ("cancellation_policies", "taxes", "promotions", "offers"):
                    val = rate_dict.get(key)
                    if isinstance(val, str):
                        try:
                            rate_dict[key] = json.loads(val)
                        except Exception:
                            pass
                rates_out.append(rate_dict)
            room["rates"] = rates_out
            hotel_rooms.append(room)
        hotel["rooms"] = hotel_rooms
        hotels_out.append(hotel)

    conn.close()
    return {"search": search_meta, "hotels": hotels_out}

save_hotel_images = save_hotel_images
load_hotel_search = load_hotel_search