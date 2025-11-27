from __future__ import annotations

import json
import os
from typing import Any, Dict, Callable, List, Optional
from datetime import datetime, date, timedelta
import openai
from agents import function_tool

# Import the Duffel functions (these should already be written and available)
from map_servers.flight_server import (
    search_flights,
    create_order,
    create_payment,
    get_order,
    cancel_order,
    get_offer,
    request_order_change_offers,
    confirm_order_change,
    tokenize_card,
)
from map_servers.hotelbeds_server import (
    search_hotels,
    book_hotel,
    get_booking,
    cancel_booking,
)
from map_servers.hotelbeds_store import load_hotel_search
from map_servers.flight_store import save_flight_choice, load_flight_choices, save_flight_search_results, load_latest_search_offers
from map_servers.utils import send_booking_email
from booking_store import save_booking, cancel_booking_record

# ----------------------------------------------------------------------
# Dedup cache to avoid repeated create_order on the same offer (per process)
_recent_orders: Dict[str, float] = {}

# ----------------------------------------------------------------------
# 1. Configure OpenAI LLM
# ----------------------------------------------------------------------

# OPTION A (recommended): read from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "Please set OPENAI_API_KEY as an environment variable or "
        "hard-code it in agent_app.py before running."
    )

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Create OpenAI client for newer API
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------------------------------------------
# 2. Tool registry: names -> description + Python callables
# ----------------------------------------------------------------------

def _tool_schema() -> Dict[str, Dict[str, Any]]:
    """
    Describe tools in natural language + argument info.
    This is what the LLM sees when deciding which tool to call.
    """
    return {
        "search_flights": {
            "description": "Search for flight offers based on the provided origin, destination, and dates.",
            "args": {
                "slices": "list of { origin: string (IATA Form), destination: string, departure_date: string (YYYY‑MM‑DD) } (required)",
                "passengers": "list of { type: string ('adult'/'child'/'infant') or age: integer } (required)",
                "cabin_class": "string (optional) - 'economy'/'premium_economy'/'business'/'first'",
                
                "max_offers": "integer (optional)"  
            }
        },
        "generate_passenger_template": {
            "description": "Use whenever a user chooses a flight number after getting the `recent flight offers:` message and only after search_flights have been called. Run before the create_order function",
            "args": {
                "selection": "integer (required) - 1-based index of the flight from the latest search results"
            }
        },
        "create_order": {
            "description": "Create a flight order from a selected offer. Requires passenger identities and contact details.",
            "args": {
                "offer_id": "string (required) - the Duffel offer ID (e.g., 'off_12345').",
                "payment_type": "string (optional) - The payment method to use (default is 'balance').",
                "passengers": "list (required) - A list of passenger details with id, title, gender type: string ('m'/'f'), given_name, family_name, born_on, email, phone_number.",
                "mode": "string (optional) - The order type: 'instant' or 'hold' (default is 'instant').",
                "create_hold": "boolean (optional) - If True, create a hold order without taking payment (default is False).",
            },
        },
        "create_payment": {
            "description": "Create a payment for an existing order. Supports balance payments and experimental card payments (via payment_source). If amount/currency are missing, it will use the order total.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "amount": "string (optional) - amount to pay; defaults to order total.",
                "currency": "string (optional) - currency code; defaults to order currency.",
                "payment_type": "string (optional) - payment method, defaults to 'balance'. Use 'card' when providing payment_source for card payments.",
                "payment_source": "object (optional) - provider-specific fields (e.g., token/payment_method_id) for non-balance payments.",
            },
        },
        "get_order": {
            "description": "Fetch order details including passengers, itinerary, and payments.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...)."
            },
        },
        "get_offer": {
            "description": "Fetch detailed offer of a flight info including segments, baggage, cabin, fare brand, and pricing.",
            "args": {
                "offer_id": "string (required) - Duffel offer ID (off_...)."
            },
        },
        "cancel_order": {
            "description": "Request and (optionally) confirm cancellation of an order. Returns refund info when available.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "auto_confirm": "boolean (optional) - confirm the cancellation immediately, default true.",
            },
        },
        "request_order_change_offers": {
            "description": "Request change offers for an order (e.g., new dates/routes). Returns priced change offers.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "slices": "list (optional) - new journey slices {origin, destination, departure_date} to reprice changes.",
                "max_offers": "integer (optional) - max change offers to return (default 5).",
            },
        },
        "confirm_order_change": {
            "description": "Confirm a change offer. If amount/currency are omitted, it will fetch the change offer to fill them.",
            "args": {
                "order_change_offer_id": "string (required) - Duffel order change offer ID.",
                "payment_type": "string (optional) - payment method (default 'balance').",
                "amount": "string (optional) - change total to pay; defaults from change offer.",
                "currency": "string (optional) - currency; defaults from change offer.",
            },
        },
        "search_hotels": {
            "description": "Search hotel availability via Hotelbeds (test environment by default). Use Hotelbeds destination codes (e.g., PMI, BCN, LON).",
            "args": {
                "destination_code": "string (required) - Hotelbeds destination code (e.g., 'PMI').",
                "check_in": "string (required) - check-in date YYYY-MM-DD.",
                "check_out": "string (required) - check-out date YYYY-MM-DD.",
                "rooms": "list (optional) - occupancy details, e.g., [{'adults':2,'children':0}] or with paxes.",
                "limit": "integer (optional) - max hotels to return (default 5).",
                "min_rate": "float (optional) - minimum rate to filter hotels.",
                "max_rate": "float (optional) - maximum rate to filter hotels.",
                "keywords": "list (optional) - keyword codes to filter hotels. you can extract this from prompt example (sea, mountain, city, etc.)",
                "categories": "list (optional) - category codes to filter hotels.",
            },
        },
        "book_hotel": {
            "description": "Create a hotel booking via Hotelbeds. Requires rateKey(s) from a search.",
            "args": {
                "holder": "object (required) - {name, surname} of lead guest.",
                "rooms": "list (required) - [{rateKey, paxes: [{roomId, type:'AD'/'CH', name, surname, age}]}].",
                "client_reference": "string (required) - your booking reference.",
                "remark": "string (optional) - special notes.",
            },
        },
        "get_booking": {
            "description": "Retrieve a hotel booking by reference.",
            "args": {
                "reference": "string (required) - booking reference returned by Hotelbeds.",
            },
        },
        "cancel_booking": {
            "description": "Cancel a hotel booking by reference.",
            "args": {
                "reference": "string (required) - booking reference returned by Hotelbeds.",
            },
        },
        "save_flight_choice": {
            "description": "Persist a selected flight offer to local storage for later recall.",
            "args": {
                "choice": "object (required) - flight choice with fields like offer_id, airline, price, currency, cabin_class, origin, destination, departure_date, return_date, passenger_ids",
                "db_path": "string (optional) - sqlite file path, default flight_choices.sqlite"
            },
        },
        "load_flight_choices": {
            "description": "Retrieve recently saved flight choices.",
            "args": {
                "limit": "integer (optional) - number of rows to return (default 10)",
                "db_path": "string (optional) - sqlite file path, default flight_choices.sqlite"
            },
        },
        "plan_trip_first": {
            "description": "Plan a full travel package with flights, hotels, and activities within a budget.",
            "args": {
                "origin": "string (required) - origin IATA code",
                "destination": "string (required) - destination IATA code",
                "departure_date": "string (required) - YYYY-MM-DD",
                "return_date": "string (optional) - YYYY-MM-DD",
                "budget": "float (required) - total trip budget",
                "passengers": "integer or list (optional) - number of travelers or pax list",
                "cabin_class": "string (optional) - flight cabin class",
                "hotel_keywords": "list (optional) - hotel keyword codes",
                "interests": "list (optional) - activities interests (e.g., hiking, food)",
            },
        },
        "plan_things_to_do": {
            "description": "Suggest activities/things to do at a destination based on interests.",
            "args": {
                "destination": "string (required) - city or place",
                "interests": "list (optional) - interests such as hiking, food, culture",
                "days": "integer (optional) - length of stay",
                "budget_per_day": "float (optional) - activity budget per day",
            },
        },
        "book_plan_trip": {
            "description": "Book both flight and hotel from the latest planned trip (plan_trip_first). Requires passenger details and hotel holder/rooms.",
            "args": {
                "passengers": "list (required) - passengers for the flight order (id/title/gender/given_name/family_name/born_on/email/phone_number)",
                "payment_type": "string (optional) - payment method for flight (default balance)",
                "flight_offer_id": "string (optional) - Duffel offer id; if omitted, uses last flight id from plan summary",
                "hotel_rate_key": "string (optional) - Hotelbeds rateKey; if omitted, uses last rate_key from plan summary",
                "holder": "object (required) - {name, surname} for hotel booking",
                "rooms": "list (required) - hotel rooms payload [{rateKey, paxes:[{roomId, type:'AD'/'CH', name, surname, age}]}]",
                "client_reference": "string (required) - booking reference for hotel from plan summary",
                "selection": "integer (optional) - flight selection number to generate passenger template if passengers are missing",
            },
        },
        
    }
# Removed duplicate TOOL_FUNCTIONS definition

# ----------------------------------------------------------------------
# 3. Agent logic: decide tool vs direct answer, then explain
# ----------------------------------------------------------------------

# Initialize the conversation memory list
conversation_history = []
# Track if we already asked clarifying questions for plan_trip_first
_plan_questions_pending = False

def _truncate(text: str, max_chars: int = 4000) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def generate_passenger_template(selection: int, db_path: str = "databases/flights.sqlite") -> Dict[str, Any]:
    """
    Return the raw offer for a selected flight index from the most recent search,
    suitable for prompting the passenger template on the frontend.
    """
    offers = load_latest_search_offers(db_path=db_path)
    if not offers:
        return {"error": "No recent flight search found. Please run a flight search and choose a number."}
    if selection < 1 or selection > len(offers):
        return {
            "error": f"Selection {selection} is out of range. Latest search has {len(offers)} offer(s).",
            "count": len(offers),
        }
    chosen = offers[selection - 1].get("raw") or {}

    # Trim to only the fields needed by the frontend template
    passengers = []
    for pax in chosen.get("passengers", []) or []:
        passengers.append({"id": pax.get("id") or ""})
    if not passengers:
        passengers = [{"id": ""}]

    passenger_template = {
        # Duplicate id for frontend compatibility
        "id": chosen.get("id"),
        "offer_id": chosen.get("id"),
        "passengers": passengers,
        "required_fields": ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number", "id"],
    }

    return {"passenger_template": passenger_template, "selection": selection}


def plan_things_to_do(
    destination: str,
    interests: Optional[List[str]] = None,
    days: Optional[int] = None,
    budget_per_day: Optional[float] = None,
) -> Dict[str, Any]:
    suggestions: List[Dict[str, Any]] = []
    interests = interests or ["food", "culture", "outdoors"]
    base = [
        {"name": "City walking tour", "type": "culture", "cost": "low", "notes": "Explore old town and landmarks"},
        {"name": "Local food crawl", "type": "food", "cost": "medium", "notes": "Sample street food and markets"},
        {"name": "Sunset viewpoint", "type": "outdoors", "cost": "low", "notes": "Easy hike or cable car"},
        {"name": "Museum visit", "type": "culture", "cost": "medium", "notes": "Top-rated museum in the city"},
    ]
    for item in base:
        if any(kw in item["type"] for kw in interests):
            suggestions.append(item)
    return {
        "destination": destination,
        "days": days,
        "budget_per_day": budget_per_day,
        "suggestions": suggestions,
    }


def _extract_latest_plan_refs() -> Dict[str, str]:
    """
    Parse conversation_history for the latest summary line containing flight/hotel identifiers.
    """
    flight_id = ""
    hotel_rate_key = ""
    for msg in reversed(conversation_history):
        text = msg.get("content") if isinstance(msg, dict) else ""
        if not isinstance(text, str):
            continue
        if "rate_key=" in text or "rateKey=" in text:
            if not hotel_rate_key:
                try:
                    part = text.split("rate_key=")[1]
                    hotel_rate_key = part.split()[0].strip()
                except Exception:
                    pass
        if "id=" in text and "flight" in text.lower():
            if not flight_id:
                try:
                    part = text.split("id=")[1]
                    flight_id = part.split()[0].strip(" )")
                except Exception:
                    pass
        if flight_id and hotel_rate_key:
            break
    return {"flight_offer_id": flight_id, "hotel_rate_key": hotel_rate_key}


def _fetch_passenger_ids_for_offer(offer_id: str, db_path: str = "databases/flights.sqlite") -> List[str]:
    """
    Grab passenger ids from the latest flight search for a given offer.
    Falls back to the first offer's passengers if a direct match is not found.
    """
    if not offer_id:
        return []
    ids: List[str] = []
    try:
        offers = load_latest_search_offers(db_path=db_path) or []
    except Exception:
        offers = []
    for row in offers:
        raw = row.get("raw") or {}
        oid = raw.get("id") or row.get("offer_id")
        if oid == offer_id:
            ids = [p.get("id") or "" for p in raw.get("passengers") or [] if isinstance(p, dict)]
            break
    if not ids and offers:
        raw = offers[0].get("raw") or {}
        ids = [p.get("id") or "" for p in raw.get("passengers") or [] if isinstance(p, dict)]
    return [i for i in ids if i]


def _apply_passenger_ids(passengers: List[Dict[str, Any]], offer_id: str) -> List[Dict[str, Any]]:
    """
    Ensure each passenger has an id by pulling them from the stored offer.
    """
    ids = _fetch_passenger_ids_for_offer(offer_id)
    if not passengers or not ids:
        return passengers or []
    filled: List[Dict[str, Any]] = []
    for idx, pax in enumerate(passengers):
        pax_copy = dict(pax)
        pid = pax_copy.get("id") or ""
        if (not pid or not str(pid).startswith("pas_")) and idx < len(ids):
            pax_copy["id"] = ids[idx]
        filled.append(pax_copy)
    return filled


def _passenger_ids_missing_or_invalid(passengers: List[Dict[str, Any]]) -> bool:
    """
    Detect if any passenger lacks a Duffel passenger id (pas_...).
    """
    for pax in passengers or []:
        pid = pax.get("id") or ""
        if not pid or not str(pid).startswith("pas_"):
            return True
    return False


def _normalize_payment_source(src: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Duffel card payments require a card_id or 3DS session. If raw card details
    arrive from the frontend, tokenize them into a pseudo card_id and strip PAN/CVC.
    This is a lightweight stand-in for a real PSP tokenization flow.
    """
    if not src or not isinstance(src, dict):
        return src
    # If caller already provided a Duffel card token, honor it
    card_id = src.get("card_id")
    if card_id and str(card_id).startswith("card_"):
        # Drop raw fields if any snuck in
        cleaned = {k: v for k, v in src.items() if k == "card_id" or k == "three_d_secure_session_id"}
        return cleaned

    card_number = src.get("card_number")
    exp_month = src.get("exp_month")
    exp_year = src.get("exp_year")
    cvc = src.get("cvc")
    holder = src.get("holder_name", "")
    if card_number and exp_month and exp_year and cvc:
        tokenized = tokenize_card(
            card_number=str(card_number),
            exp_month=str(exp_month),
            exp_year=str(exp_year),
            cvc=str(cvc),
            holder_name=holder,
        )
        if isinstance(tokenized, dict) and tokenized.get("card_id"):
            return {"card_id": tokenized["card_id"], "exp_month": str(exp_month), "exp_year": str(exp_year), "holder_name": holder}
        # If tokenization failed, return an error object so caller can surface it
        return {"error": tokenized}

    # As a final fallback, if a card_id exists but lacks the prefix, add it
    if card_id:
        return {**{k: v for k, v in src.items() if k != "card_number" and k != "cvc"}, "card_id": f"card_{card_id}"}
    return None


def _valid_duffel_card_id(card_id: str) -> bool:
    """
    Duffel card tokens typically look like card_XXXXXXXX... with alnum chars.
    """
    if not card_id or not isinstance(card_id, str):
        return False
    if not card_id.startswith("card_"):
        return False
    stripped = card_id[len("card_") :]
    return stripped.isalnum() and len(stripped) >= 6


def _normalize_rooms_for_booking(
    rooms: List[Dict[str, Any]],
    default_rate_key: str,
    holder: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Ensure Hotelbeds payload always contains at least one adult per room and a rateKey.
    """
    normalized: List[Dict[str, Any]] = []
    for idx, room in enumerate(rooms or []):
        rate_key = room.get("rateKey") or room.get("rate_key") or default_rate_key
        paxes = room.get("paxes") or []
        norm_paxes: List[Dict[str, Any]] = []
        for p_idx, pax in enumerate(paxes):
            age = pax.get("age")
            try:
                age = int(age) if age is not None else 30
            except Exception:
                age = 30
            p_type = pax.get("type") or ("AD" if age >= 18 else "CH")
            if age >= 18 and p_type == "CH":
                p_type = "AD"
            norm_paxes.append(
                {
                    "roomId": pax.get("roomId") or (p_idx + 1),
                    "type": p_type,
                    "name": pax.get("name") or (holder.get("name") if holder else ""),
                    "surname": pax.get("surname") or (holder.get("surname") if holder else ""),
                    "age": age,
                }
            )
        if not norm_paxes:
            norm_paxes.append(
                {
                    "roomId": 1,
                    "type": "AD",
                    "name": holder.get("name") if holder else "Adult",
                    "surname": holder.get("surname") if holder else "Guest",
                    "age": 30,
                }
            )
        if not any(px.get("type") == "AD" for px in norm_paxes):
            norm_paxes[0]["type"] = "AD"
            if holder:
                norm_paxes[0]["name"] = norm_paxes[0].get("name") or holder.get("name", "")
                norm_paxes[0]["surname"] = norm_paxes[0].get("surname") or holder.get("surname", "")
            if norm_paxes[0].get("age", 0) < 18:
                norm_paxes[0]["age"] = 30
        normalized.append({"rateKey": rate_key, "paxes": norm_paxes})
    return normalized


def _format_booking_message(result: Dict[str, Any]) -> str:
    """Create a concise human-readable booking summary for chat."""
    flight = result.get("flight_order") if isinstance(result, dict) else {}
    hotel = result.get("hotel_booking") if isinstance(result, dict) else {}

    lines = ["Your bookings are confirmed:"]

    if isinstance(flight, dict):
        ref = flight.get("booking_reference") or flight.get("order_id") or ""
        total = f"{flight.get('total')} {flight.get('currency')}".strip()
        order_type = flight.get("order_type") or ""
        pax_names = []
        for p in flight.get("passengers") or []:
            name = " ".join(filter(None, [p.get("title"), p.get("given_name"), p.get("family_name")])).strip()
            if name:
                pax_names.append(name)
        route = ""
        itinerary = flight.get("itinerary") or []
        if itinerary:
            first = itinerary[0]
            dep_seg = (first.get("segments") or [{}])[0]
            origin = (dep_seg.get("origin") or {}).get("iata_code") or ""
            dest = (dep_seg.get("destination") or {}).get("iata_code") or ""
            route = f"{origin}->{dest}" if origin or dest else ""
            dep_time = dep_seg.get("departing_at") or ""
        else:
            dep_time = ""

        lines += [
            "",
            "Flight:",
            f" - Reference: {ref}",
            f" - Type: {order_type}",
            f" - Route: {route}",
            f" - Departure: {dep_time}",
            f" - Total: {total}",
            f" - Passenger(s): {', '.join(pax_names) if pax_names else 'n/a'}",
        ]

    if isinstance(hotel, dict):
        hotel_raw = hotel.get("raw") or {}
        hotel_info = hotel_raw.get("hotel", {}) or hotel_raw.get("hotel_info", {}) or {}
        name = hotel_info.get("name") or hotel_raw.get("name") or ""
        destination = hotel_info.get("destinationName") or hotel_info.get("destinationCode") or ""
        check_in = hotel_info.get("checkIn") or hotel.get("check_in", "")
        check_out = hotel_info.get("checkOut") or hotel.get("check_out", "")
        total = hotel.get("total_net") or hotel_raw.get("totalNet") or ""
        currency = hotel.get("currency") or hotel_raw.get("currency") or ""
        lines += [
            "",
            "Hotel:",
            f" - Reference: {hotel_raw.get('reference') or hotel.get('booking_reference') or ''}",
            f" - Name: {name}",
            f" - Destination: {destination}",
            f" - Check-in: {check_in}",
            f" - Check-out: {check_out}",
            f" - Total: {total} {currency}".strip(),
        ]

    lines += [
        "",
        "We've emailed your itinerary to the address on file. Safe travels! ✈️🏨",
    ]
    return "\n".join(lines)


def book_plan_trip(
    passengers: List[Dict[str, Any]],
    payment_type: str = "balance",
    flight_offer_id: Optional[str] = None,
    hotel_rate_key: Optional[str] = None,
    holder: Optional[Dict[str, str]] = None,
    rooms: Optional[List[Dict[str, Any]]] = None,
    client_reference: Optional[str] = None,
) -> Dict[str, Any]:
    refs = _extract_latest_plan_refs()
    flight_offer_id = flight_offer_id or refs.get("flight_offer_id")
    hotel_rate_key = hotel_rate_key or refs.get("hotel_rate_key")

    missing = []
    if not flight_offer_id:
        missing.append("flight_offer_id")
    if not passengers:
        missing.append("passengers")
    if not hotel_rate_key:
        missing.append("hotel_rate_key")
    if not holder:
        missing.append("holder")
    if not rooms:
        missing.append("rooms")
    if not client_reference:
        missing.append("client_reference")
    if missing:
        return {"error": "Missing required fields", "missing_fields": missing}

    results: Dict[str, Any] = {}

    # Fill passenger ids from the stored offer when they are missing
    passengers_with_ids = _apply_passenger_ids(passengers, flight_offer_id)
    # Validate passengers before attempting to create the order
    required_fields = ["id", "title", "gender", "given_name", "family_name", "born_on", "email", "phone_number"]
    missing_passenger_fields = []
    for idx, pax in enumerate(passengers_with_ids):
        missing_fields = [f for f in required_fields if not pax.get(f)]
        if missing_fields:
            missing_passenger_fields.append({"passenger_index": idx, "missing_fields": missing_fields})
    if missing_passenger_fields or _passenger_ids_missing_or_invalid(passengers_with_ids):
        results["flight_order"] = {
            "error": "Missing required passenger details",
            "required_fields": required_fields,
            "missing": missing_passenger_fields,
            "hint": "Provide passengers with all required fields or share the missing details so I can retry.",
        }
        return results

    try:
        flight_resp = create_order(
            offer_id=flight_offer_id,
            passengers=passengers_with_ids,
            payment_type=payment_type,
        )
        results["flight_order"] = flight_resp
    except Exception as e:
        results["flight_error"] = str(e)

    try:
        normalized_rooms = _normalize_rooms_for_booking(rooms, hotel_rate_key, holder)
        hotel_resp = book_hotel(holder=holder, rooms=normalized_rooms, client_reference=client_reference)
        results["hotel_booking"] = hotel_resp
    except Exception as e:
        results["hotel_error"] = str(e)

    # Attach the email field for downstream mailer
    if passengers_with_ids:
        primary_email = passengers_with_ids[0].get("email")
        if primary_email:
            results["email"] = primary_email
    try:
        send_booking_email(results)
    except Exception as e:
        print(f"send_booking_email failed: {e}")

    return results


def plan_trip_first(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    budget: Optional[float] = None,
    passengers: Optional[Any] = None,
    cabin_class: str = "economy",
    hotel_min_rate: Optional[float] = None,
    hotel_max_rate: Optional[float] = None,
    hotel_keywords: Optional[List[str]] = None,
    hotel_categories: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    def _unspecified(val: Optional[str]) -> bool:
        if val is None:
            return True
        if isinstance(val, str):
            return val.strip().lower() in {"any", "anywhere", "n/a", "none", ""}
        return False
    print("test")
    missing = []
    if _unspecified(origin):
        missing.append("origin (IATA code)")
    if _unspecified(destination):
        missing.append("destination (IATA code)")
    if _unspecified(departure_date):
        missing.append("departure_date (YYYY-MM-DD)")
    if budget is None:
        missing.append("budget")
    if missing:
        numbered = "\n".join([f"{idx+1}. {field}" for idx, field in enumerate(missing)])
        return {
            "error": "Missing required fields",
            "missing_fields": missing,
            "prompt": "Please provide the following (you can say 'any' if no preference):\n" + numbered + "\nOptional: return_date, passengers, cabin_class, hotel_min_rate/max_rate, hotel_keywords/categories, interests."
        }
    print("test2")
    def _parse_date(val: str) -> Optional[date]:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None

    dep = _parse_date(departure_date)
    ret = _parse_date(return_date) if return_date else None
    nights = (ret - dep).days if dep and ret else None

    # Perform fresh searches to populate DB
    try:
        pax_list = None
        if isinstance(passengers, int):
            pax_list = [{"type": "adult"} for _ in range(max(1, passengers))]
        elif isinstance(passengers, list):
            pax_list = passengers
        else:
            pax_list = [{"type": "adult"}]

        search_flights(
            slices=[{"origin": origin.upper(), "destination": destination.upper(), "departure_date": departure_date}],
            passengers=pax_list,
            cabin_class=cabin_class,
        )
    except Exception as e:
        print(f"plan_trip_first: flight search failed {e}")
        print("Test3")

    

    flights = load_latest_search_offers(db_path="databases/flights.sqlite")
    best_flight = None
    if flights:
        flights_sorted = sorted(flights, key=lambda x: x.get("raw", {}).get("total_amount", float("inf")))
        best_flight = flights_sorted[0].get("raw")
    if not best_flight:
        return {
            "error": "No flights found for the provided criteria. Try different dates or routes.",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
        }
    print("Test4")

    def _arrival_date_from_flight(raw_flight: Dict[str, Any]) -> Optional[str]:
        """Pick the arrival date of the last segment in the first slice, as YYYY-MM-DD."""
        try:
            slices = raw_flight.get("slices") or []
            if not slices:
                return None
            last_seg = (slices[0].get("segments") or [])[-1]
            arriving_at = last_seg.get("arriving_at")
            if not arriving_at:
                return None
            # Normalize ISO strings with trailing Z for fromisoformat
            ts = arriving_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            return dt.date().isoformat()
        except Exception:
            return None

    try:
        # Align hotel check-in with flight arrival date instead of departure date
        flight_arrival_date = _arrival_date_from_flight(best_flight) or departure_date
        check_in = flight_arrival_date
        check_out = return_date or (
            datetime.fromisoformat(check_in).date() + timedelta(days=3)
        ).isoformat()

        hotelresults = search_hotels(
            destination_code=destination.upper(),
            check_in=check_in,
            check_out=check_out,
            # rooms = [{"adults": 2, "children": 0}],
            limit=5,
        )
        if isinstance(hotelresults, dict) and hotelresults.get("error"):
            return {
                "error": hotelresults.get("error"),
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
            }
    except Exception as e:
        print(f"plan_trip_first: hotel search failed {e}")
        return {
            "error": f"Hotel search failed: {e}",
            "destination": destination,
            "check_in": check_in if 'check_in' in locals() else departure_date,
            "check_out": check_out if 'check_out' in locals() else return_date or departure_date,
        }
        
    hotels = []
    try:
        loaded = load_hotel_search(db_path="databases/hotelbeds.sqlite")
        hotels = loaded.get("hotels", []) if isinstance(loaded, dict) else []
    except Exception:
        hotels = []
    best_hotel = None
    if hotels:
        def rate_val(h):
            try:
                return float(h.get("min_rate") or h.get("max_rate") or 0)
            except Exception:
                return float("inf")
        hotels_sorted = sorted(hotels, key=rate_val)
        best_hotel = hotels_sorted[0]
    if not best_hotel:
        return {
            "error": "No hotels found for the provided destination/dates. Try adjusting destination or dates.",
            "destination": destination,
            "check_in": departure_date,
            "check_out": ret.isoformat() if ret else departure_date,
        }

    activities = plan_things_to_do(destination=destination, interests=interests)

    estimate = {}
    if best_flight and best_hotel:
        try:
            flight_cost = float(best_flight.get("total_amount") or best_flight.get("price") or 0)
            hotel_cost = float(best_hotel.get("min_rate") or best_hotel.get("max_rate") or 0)
            # Hotel rates already cover the full stay; do not multiply by nights
            total_est = flight_cost + hotel_cost
            estimate = {"total_estimated": total_est, "currency": best_hotel.get("currency") or "USD"}
        except Exception:
            pass

    return {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "budget": budget,
        "passengers": passengers,
        "flight": best_flight,
        "hotel": best_hotel,
        "activities": activities,
        "estimate": estimate,
        "nights": nights,
    }
TOOL_FUNCTIONS = {
    "search_flights": search_flights,
    "generate_passenger_template": generate_passenger_template, 
    "create_order" : create_order,
    "create_payment": create_payment,
    "get_order": get_order,
    "cancel_order": cancel_order,
    "get_offer": get_offer,
    "request_order_change_offers": request_order_change_offers,
    "confirm_order_change": confirm_order_change,
    "search_hotels": search_hotels,
    "book_hotel": book_hotel,
    "get_booking": get_booking,
    "cancel_booking": cancel_booking,
    "save_flight_choice": save_flight_choice,
    "load_flight_choices": load_flight_choices,
    "plan_trip_first": plan_trip_first,  # set after definition
    "plan_things_to_do": plan_things_to_do,  # set after definition
    "book_plan_trip": book_plan_trip,
}


def build_system_prompt() -> str:
    tools_desc = _tool_schema()
    tools_text_parts = []
    for name, spec in tools_desc.items():
        tools_text_parts.append(
            f"- {name}:\n"
            f"  description: {spec['description']}\n"
            f"  args: {json.dumps(spec['args'], indent=2)}"
        )
    tools_text = "\n".join(tools_text_parts)

    return (
        "You are a travel assistant that can call a set of tools (Duffel API functions).\n"
        "YOU ONLY ANSWER TRAVEL RELATED QUESTIONS!\n"
        "DONT ANSWER ANYTHING NOT TRAVEL/TOURSIM RELATED!\n"
        "If the user Say plan full trip/jounrye use the plan_trip_first toolfollow context too and DONT USE the search_hotel/search_flights/plan_things_to_do tool in atleast 3 following prompts unless prompt is very clear about searching for flight/hotel\n"
        "If the user uses search_flights tool then provides a flight selection number, you MUST call generate_passenger_template with that number before creating any order.\n"
        "Do not call create_order until you have collected passenger details via the passenger template.\n"
        "Tools available:\n"
        f"{tools_text}\n\n"
        "You MUST decide if you need to call a tool.\n"
        "If you need a tool, respond ONLY with a JSON object of the form:\n"
        '{\n'
        '  "tool": "<tool_name>",\n'
        '  "args": { ... }\n'
        '}\n'
        "where <tool_name> is one of the tools above, and args contains only simple JSON types.\n"
        "If you can answer directly without tools (e.g., conceptual explanation), respond ONLY with:\n"
        '{ "answer": "<your natural language answer>" }\n'
        "Do not add any extra text outside the JSON. The JSON must be the entire response.\n"
        f"today is{datetime.now()}"
    )

def load_prompt_from_file(prompt_key: str, file_path: str = 'prompts.json') -> str:
    try:
        with open(file_path, 'r') as f:
            prompts = json.load(f)
        return prompts.get(prompt_key, "")
    except FileNotFoundError:
        raise Exception(f"Prompt file '{file_path}' not found.")
    except json.JSONDecodeError:
        raise Exception(f"Error decoding JSON from the prompt file.")

def ask_llm_for_tool_or_answer(user_message: str) -> Dict[str, Any]:
    """
    Step 1: Ask the LLM whether to call a tool, and which one.
    
    Returns parsed JSON dict, either:
      { "answer": "..." }
    or
      { "tool": "<name>", "args": { ... } }
    """
    # Add current user message to conversation history
    conversation_history.append({"role": "user", "content": user_message})

    # Build the system prompt to guide the LLM's behavior
    system_prompt = build_system_prompt()

    # Send the full conversation history + system prompt as context
    messages = [{"role": "system", "content": system_prompt}] + conversation_history[-25:]  # Limit context to last few messages

    # Make the API request with conversation history + system prompt
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Use a valid model
        messages=messages,
        max_tokens= 4090,
    )

    # Extract the response text
    text = response.choices[0].message.content.strip()

    # Add assistant's response to conversation history
    conversation_history.append({"role": "assistant", "content": text})

    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        # Fallback: wrap whatever the model said as a direct answer
        data = {"answer": text}

    return data

def llm_post_tool_response(
    user_message: str,
    tool_name: str,
    args: Dict[str, Any],
    result: Any,
    prompt_key: str = "explain_decision",
    prompt_file: str = "prompts.json"
) -> str:
    """
    Step 3: After calling the tool, ask the LLM to explain the result.
    """
    prompter = load_prompt_from_file(prompt_key, prompt_file)

    if not prompter:
        raise ValueError(f"No prompt found with key '{prompt_key}' in {prompt_file}")
    
    # Pre-process variables
    tool_desc = _tool_schema().get(tool_name, {})
    tool_description = tool_desc.get('description', '') if isinstance(tool_desc, dict) else ''
    
    # ✅ FIX: Actually format the prompt with the variables
    formatted_prompt = prompter.format(
        user_message=user_message,
        tool_name=tool_name,
        tool_description=tool_description,
        formatted_args=_truncate(json.dumps(args, indent=2), max_chars=2000),
        formatted_result=_truncate(json.dumps(result, indent=2), max_chars=4000)
    )
    
    if tool_name == "plan_trip_first":
        # Append concise context about chosen flight/hotel to conversation history
        try:
            flight_name = ""
            flight_id = ""
            hotel_name = ""
            hotel_rate_key = ""
            if isinstance(result, dict):
                flight_raw = result.get("flight") or {}
                hotel_raw = result.get("hotel") or {}
                flight_name = flight_raw.get("owner", {}).get("name") or flight_raw.get("id") or ""
                flight_id = flight_raw.get("id") or flight_raw.get("offer_id") or ""
                # Pull a representative rate key from first room/rate
                rooms = hotel_raw.get("rooms") or []
                if rooms:
                    rates = rooms[0].get("rates") or []
                    if rates:
                        hotel_rate_key = rates[0].get("rateKey") or rates[0].get("rate_key") or ""
                hotel_name = hotel_raw.get("name") or hotel_raw.get("code") or ""
            summary_ctx = (
                f"flight_summary: {flight_name} offer_id={flight_id}\n"
                f"hotel_summary: {hotel_name} rate_key={hotel_rate_key}"
            )
            conversation_history.append({"role": "assistant", "content": summary_ctx})
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=summary_ctx,
                max_tokens=4090,
            )

            text = response.choices[0].message.content.strip()
            # ❌ REMOVE this print to avoid duplicate output
            # print ("this is the text habibi", text)
            conversation_history.append({"role": "assistant", "content": text})
            return text
        except Exception:
            pass

    messages = [{"role": "system", "content": "You are a helpful flight booking assistant."}] + conversation_history[-25:] + [
        {"role": "user", "content": formatted_prompt},  # ✅ Use formatted_prompt, not raw prompter
    ]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=4090,
    )

    text = response.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": text})
    return text

def handle_user_message(user_message: str) -> str:
    """
    Full agent flow for one user message:
    1. Ask LLM whether to use a tool or answer directly.
    2. If tool: run the Python function, then ask LLM to explain result.
    """
   

    # Fast-path: if frontend sends structured booking payload, bypass LLM and create order directly
    try:
        data = json.loads(user_message)
        if isinstance(data, dict) and data.get("offer_id") and isinstance(data.get("passengers"), list):
            order_payload = {
                "offer_id": data["offer_id"],
                "passengers": [p for p in data["passengers"] if isinstance(p, dict)],
                "payment_type": data.get("payment_type", "balance"),
                "payment_source": _normalize_payment_source(data.get("payment_source")),
                "mode": data.get("mode", "instant"),
                "create_hold": data.get("create_hold", False),
            }
            if isinstance(order_payload.get("payment_source"), dict) and order_payload["payment_source"].get("error"):
                err = order_payload["payment_source"]["error"]
                try:
                    return json.dumps(err, indent=2)
                except Exception:
                    return str(err)
            if (
                order_payload["payment_type"] == "card"
                and not _valid_duffel_card_id((order_payload["payment_source"] or {}).get("card_id", ""))
            ):
                return (
                    "Card payments need a Duffel card token (card_id). "
                    "Use balance/hold, or provide a Duffel-issued card_id/3DS token."
                )
            # Dedup guard: avoid rebooking same offer id immediately
            from time import time
            now = time()
            last = _recent_orders.get(order_payload["offer_id"])
            if last and (now - last) < 120:
                return f"Order for offer {order_payload['offer_id']} was already submitted recently. Please search again to book a new offer."
            try:
                # Record user payload in history for context
                conversation_history.append({"role": "user", "content": json.dumps(order_payload)})
                result = create_order(**order_payload)
                _recent_orders[order_payload["offer_id"]] = now
                user_email = data.get("user_email") or data.get("email")
                if user_email:
                    ref = result.get("order_id") or result.get("booking_reference") or data.get("offer_id")
                    title = f"Flight booking {ref}"
                    print("the title", ref)
                    # save_booking(user_email, "flight", ref=ref, title=title, details=result)
                send_booking_email( result)    
                print(result)
                conversation_history.append({"role": "assistant", "content": json.dumps(result)})
                # Fast-path handled; skip downstream tool invocation by returning early
                return llm_post_tool_response(user_message, "create_order", order_payload, result)
            except Exception as e:
                return llm_post_tool_response(user_message, "create_order", order_payload, e)
        if isinstance(data, dict) and data.get("order_id") and data.get("cancel_booking"):
            conversation_history.append({"role": "user", "content": json.dumps(data)})
            result = cancel_order(data["order_id"], auto_confirm=True)
            user_email = data.get("user_email") or data.get("email")
            if user_email:
                try:
                    cancel_booking_record(user_email, data["order_id"],db_path="databases/bookings.sqlite")
                except Exception as e:
                    print(f"Failed to mark booking cancelled: {e}")
            formatted_result = json.dumps(result, indent=2)
            if len(formatted_result) > 500:
                formatted_result = formatted_result[:500] + "\n... [truncated]"
            conversation_history.append({"role": "assistant", "content": formatted_result})
            return llm_post_tool_response(user_message, "cancel_order", {"order_id": data["order_id"]}, result)
        # Direct tool invocation if payload specifies tool and args
        if isinstance(data, dict) and data.get("tool") in TOOL_FUNCTIONS:
            tool_name = data.get("tool")
            args = data.get("args") or {k: v for k, v in data.items() if k != "tool"}
            try:
                tool_fn = TOOL_FUNCTIONS[tool_name]
                if tool_name == "book_plan_trip":
                    # If passenger ids are missing/invalid, return a template instead of attempting booking
                    pax_list = args.get("passengers") or []
                    if not pax_list or _passenger_ids_missing_or_invalid(pax_list):
                        refs = _extract_latest_plan_refs()
                        offer_id_hint = args.get("flight_offer_id") or refs.get("flight_offer_id") or ""
                        rate_key_hint = args.get("hotel_rate_key") or refs.get("hotel_rate_key") or ""
                        pax_ids = _fetch_passenger_ids_for_offer(offer_id_hint)
                        pax_seed = pax_ids if pax_ids else [""]
                        passenger_entries = [
                            {"id": pid, "title": "", "gender": "", "given_name": "", "family_name": "", "born_on": "", "email": "", "phone_number": ""}
                            for pid in pax_seed
                        ]
                        passenger_template = {
                            "id": offer_id_hint,
                            "offer_id": offer_id_hint,
                            "passengers": passenger_entries,
                            "required_fields": ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number", "id"],
                        }
                        holder_template = {"name": "", "surname": ""}
                        rooms_template = [
                            {
                                "rateKey": rate_key_hint,
                                "paxes": [{"roomId": 1, "type": "AD", "name": "", "surname": "", "age": 30}],
                            }
                        ]
                        template = {
                            "flight_offer_id": offer_id_hint,
                            "hotel_rate_key": rate_key_hint,
                            "passenger_template": passenger_template,
                            "hotel_holder": holder_template,
                            "hotel_rooms": rooms_template,
                            "client_reference": "",
                            "missing_fields": ["passengers"],
                        }
                        return json.dumps(template, indent=2)
                result = tool_fn(**args)
                if tool_name == "book_plan_trip" and isinstance(result, dict):
                    pretty = _format_booking_message(result)
                    if pretty:
                        return pretty
                return json.dumps(result, indent=2) if not isinstance(result, str) else result
            except Exception as e:
                return f"Tool '{tool_name}' failed: {e}"
    except Exception:
        # Not a structured booking payload; continue with normal flow
        pass

    decision = ask_llm_for_tool_or_answer(user_message)
   
    # Direct answer path
    if "answer" in decision and "tool" not in decision:
        return decision["answer"]

    # Tool path
    tool_name = decision.get("tool")
    args = decision.get("args", {}) or {}
    print(decision)
    if tool_name not in TOOL_FUNCTIONS:
        return f"I tried to call an unknown tool '{tool_name}'. Please refine your request."

    tool_fn = TOOL_FUNCTIONS[tool_name]

    try:
        if tool_name == "plan_trip_first":
            global _plan_questions_pending
            if not _plan_questions_pending:
                # Build dynamic clarification prompts based on missing args
                questions  = llm_post_tool_response(user_message, tool_name, args, "", prompt_key="ask_for_info")
                conversation_history.append({"role": "assistant", "content": questions})
                _plan_questions_pending = True
                return questions
            # Reset flag and proceed to run the planner with whatever details we have.
            _plan_questions_pending = False

        if tool_name == "book_plan_trip":
            # If required pieces are missing, return a template instead of calling the tool
            refs = _extract_latest_plan_refs()
            rate_key_hint = args.get("hotel_rate_key") or refs.get("hotel_rate_key") or ""
            offer_id_hint = args.get("flight_offer_id") or refs.get("flight_offer_id") or ""
            missing_fields = []
            if not args.get("passengers"):
                missing_fields.append("passengers")
            if not args.get("holder"):
                missing_fields.append("holder")
            if not args.get("rooms"):
                missing_fields.append("rooms")
            if not args.get("client_reference"):
                missing_fields.append("client_reference")
            if missing_fields:
                # Build a hotel/flight booking template
                pax_ids = _fetch_passenger_ids_for_offer(offer_id_hint)
                pax_seed = pax_ids if pax_ids else [""]
                passenger_entries = [{"id": pid, "title": "", "gender": "", "given_name": "", "family_name": "", "born_on": "", "email": "", "phone_number": ""} for pid in pax_seed]
                passenger_template = {
                    "id": offer_id_hint,
                    "offer_id": offer_id_hint,
                    "passengers": passenger_entries,
                    "required_fields": ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number", "id"],
                }
                holder_template = {"name": "", "surname": ""}
                rooms_template = [
                    {
                        "rateKey": rate_key_hint,
                        "paxes": [{"roomId": 1, "type": "AD", "name": "", "surname": "", "age": 30}],
                    }
                ]
                template = {
                    "flight_offer_id": offer_id_hint,
                    "hotel_rate_key": rate_key_hint,
                    "passenger_template": passenger_template,
                    "hotel_holder": holder_template,
                    "hotel_rooms": rooms_template,
                    "client_reference": "",
                    "missing_fields": missing_fields,
                }
                return json.dumps(template, indent=2)

        result = tool_fn(**args)
        # Avoid dumping large plan payloads into history; keep others as before
        if tool_name != "plan_trip_first":
            formatted_result = json.dumps(result, indent=2)
            # Keep tool result in memory, but cap size to avoid blowing context window
            max_chars = 5000
            if len(formatted_result) > max_chars:
                formatted_result = formatted_result[:max_chars] + "\n... [truncated]"
            conversation_history.append({"role": "assistant", "content": formatted_result})

        if tool_name == "search_hotels":
            # Return hotel results as JSON for frontend templates; fall back to LLM on errors
            if isinstance(result, dict) and result.get("error"):
                return llm_post_tool_response(user_message, tool_name, args, result)
            try:
                loaded = load_hotel_search(db_path="databases/hotelbeds.sqlite")
                hotels = loaded.get("hotels", []) if isinstance(loaded, dict) else []
            except Exception:
                hotels = result.get("results", []) if isinstance(result, dict) else []

            # Build a concise summary of cheapest rate per hotel for conversation history
            summary_lines = []
            for idx, h in enumerate(hotels, start=1):
                cheapest_rate = None
                hotel_name = h.get("name") or "Hotel"
                for room in h.get("rooms") or []:
                    for rate in room.get("rates") or []:
                        # Normalize rate fields: net or price fields might be strings
                        try:
                            net_val = rate.get("net") or rate.get("min_rate") or rate.get("max_rate")
                            net = float(net_val) if net_val is not None else float("inf")
                        except Exception:
                            net = float("inf")
                        if cheapest_rate is None or net < cheapest_rate[0]:
                            cheapest_rate = (net, rate.get("rate_key"), room.get("code"))
                if cheapest_rate:
                    amount, rate_key, room_code = cheapest_rate
                    summary_lines.append(f"{idx}. {hotel_name} ({h.get('code')}), room {room_code}, rateKey={rate_key}, net={amount}")
                else:
                    summary_lines.append(f"{idx}. {hotel_name} ({h.get('code')}): no rates found")
            if summary_lines:
                summary_text = (
                    "Cheapest rates per hotel (remember to include a client_reference when booking):\n"
                    + "\n".join(summary_lines)
                )
                conversation_history.append({"role": "assistant", "content": summary_text})

           

            # Return original structure (full hotels) to frontend
            return json.dumps({"hotels": hotels}, indent=2)
        if tool_name == "search_flights":
            # Return raw flight offer JSON so the caller (e.g., frontend) can display all offers,
            # including those saved to the database, without truncation.
            print("search flights was used")
            try:
                if isinstance(result, dict) and result.get("error"):
                    return llm_post_tool_response(user_message, tool_name, args, result)
                offers = load_latest_search_offers(db_path="databases/flights.sqlite")
                if offers:
                    lines = []
                    for idx, offer in enumerate(offers, start=1):
                        pax_str = ", ".join(offer.get("passenger_ids") or []) or "n/a"
                        lines.append(f"{idx}. offer_id={offer.get('offer_id')} passengers=[{pax_str}]")
                    summary = "Recent flight offers:\n" + "\n".join(lines)
                    print(summary)
                    conversation_history.append({"role": "assistant", "content": summary})
                return json.dumps(result, indent=2)
            except Exception:
                return llm_post_tool_response(user_message, tool_name, args, result)
        if tool_name =="generate_passenger_template":
            # Return the passenger template directly to the user
            passenger_template = result.get("passenger_template")
            if passenger_template:
                return json.dumps(passenger_template, indent=2)
            return result.get("error", "No passenger template available. Please rerun flight search and select a valid number.")
        if tool_name == "plan_trip_first":
            if isinstance(result, dict) and result.get("missing_fields"):
                return llm_post_tool_response(user_message, tool_name, args, result, prompt_key="ask_for_missing_fields")
            if isinstance(result, dict) and result.get("error"):
                return llm_post_tool_response(user_message, tool_name, args, result, prompt_key="explain_decision")
            # Add concise flight/hotel identifiers to history
            try:
                flight = result.get("flight") if isinstance(result, dict) else {}
                hotel = result.get("hotel") if isinstance(result, dict) else {}
                flight_id = ""
                flight_name = ""
                booking_ref = result.get("booking_reference") if isinstance(result, dict) else ""
                if isinstance(flight, dict):
                    flight_id = flight.get("id") or flight.get("offer_id") or ""
                    flight_name = flight.get("owner", {}).get("name") or flight.get("marketing_carrier", {}).get("name") or ""
                hotel_rate_key = ""
                hotel_name = ""
                if isinstance(hotel, dict):
                    hotel_name = hotel.get("name") or hotel.get("code") or ""
                    rooms = hotel.get("rooms") or []
                    if rooms:
                        rates = rooms[0].get("rates") or []
                        if rates:
                            hotel_rate_key = rates[0].get("rateKey") or rates[0].get("rate_key") or ""
                summary = (
                    f"flight={flight_name or 'n/a'} (id={flight_id or 'n/a'}) "
                    f"hotel={hotel_name or 'n/a'} rate_key={hotel_rate_key or 'n/a'} "
                    f"booking_reference={booking_ref or 'n/a'}"
                )
                conversation_history.append({"role": "assistant", "content": summary})
            except Exception:
                pass
            try:
                return json.dumps(result, indent=2)
            except Exception:
                return str(result)
        if tool_name == "book_plan_trip":
            # If passengers missing, surface passenger template like in search flow
            if not args.get("passengers"):
                selection = args.get("selection", 1)
                template = generate_passenger_template(selection=selection)
                passenger_template = template.get("passenger_template") if isinstance(template, dict) else None
                if passenger_template:
                    prompt = (
                        "Please provide passenger details to proceed with booking. "
                        "Fill this template and resend:\n"
                        + json.dumps(passenger_template, indent=2)
                    )
                    return prompt
                return json.dumps(template, indent=2) if isinstance(template, dict) else str(template)
            # Otherwise proceed with normal flow
            try:
                pretty = _format_booking_message(result) if isinstance(result, dict) else ""
                # Prefer the readable summary; avoid dumping raw JSON into the chat bubble
                if pretty:
                    return pretty
                return json.dumps(result, indent=2)
            except Exception:
                return str(result)
    except TypeError as e:
        return f"There was an error calling tool '{tool_name}' with arguments {args}: {e}"
    except Exception as e:
        return f"Tool '{tool_name}' failed with an exception: {e}"
    return llm_post_tool_response(user_message, tool_name, args, result)
# ----------------------------------------------------------------------
# 4. Simple REPL
# ----------------------------------------------------------------------

def main() -> None:
    print("Flight Assistant (OpenAI model: gpt-3.5-turbo)")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye.")
            return

        if not user_input:
            continue

        answer = handle_user_message(user_input)
        print("\nAssistant:\n")
        print(answer)
        
        print("\n---\n")


if __name__ == "__main__":
    main()
