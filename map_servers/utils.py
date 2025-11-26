from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict



SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587")) if os.environ.get("SMTP_PORT") else None
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


def send_booking_email( booking: Dict[str, Any]) -> None:
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and SMTP_FROM):
        print("Email not sent: SMTP_* env vars not fully configured")
        return

    order_id = booking.get("order_id", "")
    ref = booking.get("booking_reference", "") or order_id
    total = booking.get("total", "")
    currency = booking.get("currency", "")
    itinerary = booking.get("itinerary", [])
    passengers = booking.get("passengers", [])
    payment_required_by = booking.get("payment_required_by")
    order_type = booking.get("order_type")
    # Collect recipient emails: primary plus passenger emails
    recipients = set()
    if booking.get("email"):
        recipients.add(booking.get("email"))
    for p in passengers:
        if p.get("email"):
            recipients.add(p["email"])
    def fmt_dt(val):
        return val or "N/A"

    lines = [
        "Thank you for booking with Nomada.",
        "",
        "Booking Summary",
        f" - Booking reference: {ref}",
        f" - Order ID: {order_id}",
        f" - Type: {order_type}",
        f" - Total: {total} {currency}",
        f" - Payment required by: {payment_required_by or 'N/A'}",
        "",
        "Passenger(s):",
    ]
    for p in passengers:
        lines.append(
            f" - {p.get('title','').title()} {p.get('given_name','')} {p.get('family_name','')} ({p.get('gender','')}) "
            f"DOB: {p.get('born_on','')} Email: {p.get('email','')} Phone: {p.get('phone_number','')}"
        )

    lines.append("")
    lines.append("Itinerary:")
    for idx, leg in enumerate(itinerary, start=1):
        segments = leg.get("segments") or []
        dep_seg = segments[0] if segments else {}
        arr_seg = segments[-1] if segments else {}
        origin = dep_seg.get("origin", {}) or {}
        dest = arr_seg.get("destination", {}) or {}
        carrier = dep_seg.get("marketing_carrier", {}) or {}

        lines.append(f"Leg {idx}: {origin.get('iata_code') or origin.get('name')} → {dest.get('iata_code') or dest.get('name')}")
        lines.append(f"  Departure: {fmt_dt(dep_seg.get('departing_at'))}")
        lines.append(f"  Arrival:   {fmt_dt(arr_seg.get('arriving_at'))}")
        lines.append(f"  Flight:    {carrier.get('name','')} {dep_seg.get('marketing_carrier_flight_number','')}")
        lines.append(f"  Aircraft:  {(dep_seg.get('aircraft') or {}).get('name','')}")
        lines.append(f"  Duration:  {dep_seg.get('duration','')}")
        baggage = dep_seg.get("passengers", [{}])[0].get("baggages", []) if dep_seg.get("passengers") else []
        if baggage:
            lines.append("  Baggage:  " + "; ".join([f"{b.get('quantity','')} {b.get('type','')}" for b in baggage]))
        lines.append("")

    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Your Nomada flight booking {ref or order_id}"
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients) if recipients else ""
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"Sent booking email to {recipients.email} for {ref}")
    except Exception as e:
        print(f"Failed to send booking email: {e}")


def _load_decisions() -> Dict[str, Any]:
    """
    Helper function to load existing user decisions from a local JSON file.
    Returns an empty dictionary if no data is available or if JSON is invalid.
    """
    if os.path.exists(DECISIONS_FILE_PATH):
        try:
            with open(DECISIONS_FILE_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # If file is empty or invalid, return empty dict
            return {}
    return {}


def _save_decisions(data: Dict[str, Any]) -> None:
    """
    Helper function to save user decisions to a local JSON file.
    """
    with open(DECISIONS_FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)




def save_user_flight_decision(
    offer_id: str,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    cabin_class: str = "economy",
    price: float = 0.0,
    currency: str = "USD",
) -> None:
    """
    Save the user's flight selection decision (like offer_id, origin, destination, etc.) to a local JSON file.
    This function is wrapped as a tool for the LLM to call as needed.
    """
    decisions = _load_decisions()

    # Store flight details under the user's flight decision
    flight_decision = {
        "offer_id": offer_id,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "cabin_class": cabin_class,
        "price": price,
        "currency": currency,
    }

    # Store flight decision with a unique identifier, you can change key based on user's session or other factors
    decisions[offer_id] = flight_decision
    print(f"Saving the decision: {flight_decision}")
    _save_decisions(decisions)
