# map_servers/hotelbeds_server.py

"""
Lightweight Hotelbeds integration (test-mode friendly).

Endpoints (Hotelbeds test):
  - Availability:   GET  https://api.test.hotelbeds.com/hotel-api/1.0/hotels
  - Booking:        POST https://api.test.hotelbeds.com/hotel-api/1.0/bookings
  - Booking detail: GET  https://api.test.hotelbeds.com/hotel-api/1.0/bookings/{reference}
  - Cancel:         DELETE https://api.test.hotelbeds.com/hotel-api/1.0/bookings/{reference}

Authentication:
  - X-Signature header is SHA256(api_key + secret + timestamp) where timestamp is seconds since epoch.
  - X-Timestamp is implicit (timestamp used for signature).
  - X-Api-Key header contains the API key.

Notes:
  - This module defaults to the Hotelbeds TEST environment.
  - Set HOTELBEDS_API_KEY and HOTELBEDS_SECRET in your environment or .env.
  - Request/response schemas are simplified for demo purposes; adjust as needed for production.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from .base import ServerParams

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

HOTELBEDS_PARAMS = ServerParams(
    name="hotelbeds",
    base_url="https://api.test.hotelbeds.com",
    description="Hotelbeds API for hotel availability and bookings (test).",
    commands={
        "availability": "/hotel-api/1.0/hotels",
        "booking": "/hotel-api/1.0/bookings",
        "booking_detail": "/hotel-api/1.0/bookings/{reference}",
        "content_hotels": "/hotel-content-api/1.0/hotels",
    },
)


def _hotelbeds_keys() -> Optional[Dict[str, str]]:
    api_key = os.getenv("HOTELBEDS_API_KEY")
    secret = os.getenv("HOTELBEDS_SECRET")
    if not api_key or not secret:
        return None
    return {"api_key": api_key, "secret": secret}


def _hotelbeds_headers() -> Optional[Dict[str, str]]:
    keys = _hotelbeds_keys()
    if not keys:
        return None
    api_key = keys["api_key"]
    secret = keys["secret"]
    ts = str(int(time.time()))
    signature = hashlib.sha256((api_key + secret + ts).encode("utf-8")).hexdigest()
    return {
        "Api-key": api_key,
        "X-Signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# def _allowed_destinations() -> List[str]:
#     """
#     Hotelbeds TEST environment only supports a limited set of destination codes.
#     Allow overriding via HOTELBEDS_TEST_DESTS (comma-separated). Defaults to a
#     handful of known test destinations.
#     """
#     override = os.getenv("HOTELBEDS_TEST_DESTS")
#     if override:
#         return [code.strip().upper() for code in override.split(",") if code.strip()]
#     return ["PMI", "BCN", "LON", "NYC", "PAR", "MAD", "BKK"]


# ------------------------
# Pure implementation APIs
# ------------------------


def search_hotels_impl(
    *,
    destination_code: str,
    check_in: str,
    check_out: str,
    rooms: Optional[List[Dict[str, Any]]] = None,
    limit: int = 5,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None,
    keywords: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Basic availability search using Hotelbeds TEST API. destination_code is a Hotelbeds destination code (e.g., "PMI" for Palma).
    rooms: list of {"adults": int, "children": int, "paxes": [{"type": "AD"/"CH", "age": int}, ...]}
    Note: Hotelbeds test environment only has a subset of destinations (e.g., PMI, BCN, LON).
    """
    
    headers = _hotelbeds_headers()
    if not headers:
        return {"error": "Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET"}

    limit = max(1, min(limit, 50))
    occ = rooms or [{"adults": 2, "children": 0}]

    dest_code = destination_code.upper().strip()
   
    occupancies: List[Dict[str, Any]] = []
    for idx, o in enumerate(occ, start=1):
        # Normalize to dict
        if isinstance(o, int):
            o = {"adults": int(o)}
        elif isinstance(o, str):
            # best effort parse for "2" or "2 adults"
            try:
                o = {"adults": int(o.split()[0])}
            except Exception:
                o = {"adults": 2}
        elif not isinstance(o, dict):
            o = {"adults": 2}

        paxes = o.get("paxes")
        if not paxes:
            paxes = []
            for _ in range(max(0, int(o.get("adults", 0)))):
                paxes.append({"roomId": idx, "type": "AD", "age": 30})
            for _ in range(max(0, int(o.get("children", 0)))):
                paxes.append({"roomId": idx, "type": "CH", "age": 8})
        adults_count = o.get("adults", len([p for p in paxes if p.get("type") == "AD"]))
        children_count = o.get("children", len([p for p in paxes if p.get("type") == "CH"]))
        occupancies.append({"rooms": 1, "adults": adults_count, "children": children_count, "paxes": paxes})

    body = {
        "stay": {"checkIn": check_in, "checkOut": check_out},
        "occupancies": occupancies,
        "destination": {"code": dest_code},
        "filter": {"maxHotels": limit},
    }

    # Optional filters supported by Hotelbeds availability
    if min_rate is not None:
        body["filter"]["minRate"] = float(min_rate)
    if max_rate is not None:
        body["filter"]["maxRate"] = float(max_rate)
    if keywords:
        body["keywords"] = [{"code": k} for k in keywords if k]
    if categories:
        body["filter"]["hotelCategory"] = categories

    url = HOTELBEDS_PARAMS.base_url + HOTELBEDS_PARAMS.commands["availability"]
    resp = None
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Hotelbeds availability failed: %s", e)
        payload: Any = {}
        status = None
        if resp is not None:
            status = resp.status_code
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
        return {
            "error": f"Availability failed: {e}",
            "status": status,
            "response": payload,
            "hint": "Use a Hotelbeds destination code available in the TEST environment (e.g., PMI, BCN, LON).",
        }

    data = resp.json().get("hotels", {})
    hotels = data.get("hotels") if isinstance(data, dict) else []
    if not isinstance(hotels, list):
        hotels = []
    print(data)
    hotels_out: List[Dict[str, Any]] = []
    for h in hotels[:limit]:
        if not isinstance(h, dict):
            continue
        name = h.get("name")
        if isinstance(name, dict):
            name = name.get("content")
        category = h.get("categoryName")
        if isinstance(category, dict):
            category = category.get("content")
        destination_name = h.get("destinationName")
        if isinstance(destination_name, dict):
            destination_name = destination_name.get("content")
        address = h.get("address")
        if isinstance(address, dict):
            address = address.get("content")
        description = (h.get("description") or {}).get("content")
        coords = h.get("coordinates") or {}
        lat = coords.get("latitude")
        lng = coords.get("longitude")
        keywords_raw = h.get("keywords") or []
        keywords: List[str] = []
        if isinstance(keywords_raw, list):
            for kw in keywords_raw:
                if isinstance(kw, dict):
                    content = kw.get("content")
                    if isinstance(content, dict) and content.get("description"):
                        keywords.append(content["description"])
                    elif isinstance(content, str):
                        keywords.append(content)
                elif isinstance(kw, str):
                    keywords.append(kw)
        facilities = h.get("facilities") if isinstance(h.get("facilities"), list) else []
        facility_names: List[str] = []
        for f in facilities:
            if isinstance(f, dict):
                if f.get("facilityName"):
                    facility_names.append(f["facilityName"])
                elif f.get("description"):
                    facility_names.append(f["description"])

        hotels_out.append(
            {
                "code": h.get("code"),
                "name": name,
                "category": category,
                "currency": h.get("currency"),
                "min_rate": h.get("minRate"),
                "max_rate": h.get("maxRate"),
                "destination": destination_name,
                "address": address,
                "rooms": h.get("rooms"),
                "description": description,
                "latitude": lat,
                "longitude": lng,
                "keywords": keywords,
                "zone": h.get("zoneName"),
                "category_code": h.get("categoryCode"),
                "chain": h.get("chain"),
                "facilities": facility_names,
            }
        )
    
    return {"results": hotels_out}


def book_hotel_impl(
    *,
    holder: Dict[str, str],
    rooms: List[Dict[str, Any]],
    client_reference: str,
    remark: str = "",
) -> Dict[str, Any]:
    """
    Create a booking in Hotelbeds. Requires:
      - holder: {"name": "...", "surname": "..."}
      - rooms: list of {"rateKey": "...", "paxes": [{"roomId": 1, "type": "AD"/"CH", "name": "...", "surname": "...", "age": int}]}
      - client_reference: your reference string
    """
    headers = _hotelbeds_headers()
    if not headers:
        return {"error": "Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET"}

    url = HOTELBEDS_PARAMS.base_url + HOTELBEDS_PARAMS.commands["booking"]
    payload = {
        "holder": holder,
        "rooms": rooms,
        "clientReference": client_reference,
        "remark": remark,
    }

    resp = None
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Hotelbeds booking failed: %s", e)
        payload_out: Any = {}
        status = None
        if resp is not None:
            status = resp.status_code
            try:
                payload_out = resp.json()
            except Exception:
                payload_out = {"text": resp.text}
        return {"error": f"Booking failed: {e}", "status": status, "response": payload_out, "payload_sent": payload}

    data = resp.json().get("booking", {})
    return {
        "booking_reference": data.get("reference"),
        "status": data.get("status"),
        "creation_date": data.get("creationDate"),
        "total_net": data.get("totalNet"),
        "currency": data.get("currency"),
        "raw": data,
    }


def get_booking_impl(reference: str) -> Dict[str, Any]:
    """
    Retrieve booking details by reference.
    """
    headers = _hotelbeds_headers()
    if not headers:
        return {"error": "Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET"}

    url = HOTELBEDS_PARAMS.base_url + HOTELBEDS_PARAMS.commands["booking_detail"].format(reference=reference)
    resp = None
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        payload_out: Any = {}
        status = None
        if resp is not None:
            status = resp.status_code
            try:
                payload_out = resp.json()
            except Exception:
                payload_out = {"text": resp.text}
        logger.error("Hotelbeds get booking failed: %s", e)
        return {"error": f"Get booking failed: {e}", "status": status, "response": payload_out}

    data = resp.json().get("booking", {})
    return {
        "booking_reference": data.get("reference"),
        "status": data.get("status"),
        "total_net": data.get("totalNet"),
        "currency": data.get("currency"),
        "raw": data,
    }


def cancel_booking_impl(reference: str) -> Dict[str, Any]:
    """
    Cancel a booking by reference.
    """
    headers = _hotelbeds_headers()
    if not headers:
        return {"error": "Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET"}

    url = HOTELBEDS_PARAMS.base_url + HOTELBEDS_PARAMS.commands["booking_detail"].format(reference=reference)
    resp = None
    try:
        resp = requests.delete(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        payload_out: Any = {}
        status = None
        if resp is not None:
            status = resp.status_code
            try:
                payload_out = resp.json()
            except Exception:
                payload_out = {"text": resp.text}
        logger.error("Hotelbeds cancel failed: %s", e)
        return {"error": f"Cancel failed: {e}", "status": status, "response": payload_out}

    data = resp.json().get("booking", {})
    return {
        "booking_reference": data.get("reference"),
        "status": data.get("status"),
        "cancellation_reference": data.get("cancellationReference"),
        "raw": data,
    }


# Tool-ready exports
search_hotels = search_hotels_impl
book_hotel = book_hotel_impl
get_booking = get_booking_impl
cancel_booking = cancel_booking_impl


def get_hotel_images_impl(
    hotel_codes: List[int] | List[str],
    fields: str = "images",
    language: str = "ENG",
) -> Dict[str, Any]:
    """
    Fetch hotel content (images) for given hotel codes using Hotelbeds Content API.
    """
    headers = _hotelbeds_headers()
    if not headers:
        return {"error": "Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET"}

    codes_param = ",".join(str(c) for c in hotel_codes)
    params = {
        "codes": codes_param,
        "fields": fields,
        "language": language,
    }
    url = HOTELBEDS_PARAMS.base_url + HOTELBEDS_PARAMS.commands["content_hotels"]
    resp = None
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        payload: Any = {}
        status = None
        if resp is not None:
            status = resp.status_code
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
        logger.error("Hotelbeds content fetch failed: %s", e)
        return {"error": f"Content fetch failed: {e}", "status": status, "response": payload}

    data = resp.json().get("hotels", [])
    images_out: Dict[str, List[Dict[str, Any]]] = {}
    for h in data:
        code = h.get("code")
        imgs = h.get("images", [])
        images_out[str(code)] = imgs

    return {"hotels": images_out, "raw": data}
