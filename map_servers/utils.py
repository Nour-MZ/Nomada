from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, Optional


SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587")) if os.environ.get("SMTP_PORT") else None
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


def send_booking_email(booking: Dict[str, Any]) -> None:
    """
    Send a consolidated booking email that includes flight (and optionally hotel) details.
    Requires SMTP_* environment variables to be set.
    """
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and SMTP_FROM):
        print("Email not sent: SMTP_* env vars not fully configured")
        return

    flight = booking.get("flight_order") or booking
    hotel = booking.get("hotel_booking") or {}

    order_id = flight.get("order_id", "")
    ref = flight.get("booking_reference", "") or order_id
    total = flight.get("total", "") or flight.get("total_net", "")
    currency = flight.get("currency", "")
    itinerary = flight.get("itinerary", [])
    passengers = flight.get("passengers", [])
    payment_required_by = flight.get("payment_required_by")
    order_type = flight.get("order_type", "instant")

    recipients = set()
    if booking.get("email"):
        recipients.add(booking.get("email"))
    if flight.get("email"):
        recipients.add(flight.get("email"))
    for p in passengers:
        if p.get("email"):
            recipients.add(p["email"])
    if not recipients:
        print("Email not sent: no recipient emails available in booking payload")
        return

    def fmt_dt(val: Optional[str]) -> str:
        return val or "N/A"

    lines = [
        "Thank you for booking with Nomada.",
        "",
        "Flight Summary",
        f" - Booking reference: {ref}",
        f" - Order ID: {order_id}",
        f" - Type: {order_type}",
        f" - Total: {total} {currency}".strip(),
        f" - Payment required by: {payment_required_by or 'N/A'}",
        "",
        "Passengers:",
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

        lines.append(f" Leg {idx}: {origin.get('iata_code') or origin.get('name')} -> {dest.get('iata_code') or dest.get('name')}")
        lines.append(f"  Departure: {fmt_dt(dep_seg.get('departing_at'))}")
        lines.append(f"  Arrival:   {fmt_dt(arr_seg.get('arriving_at'))}")
        lines.append(f"  Flight:    {carrier.get('name','')} {dep_seg.get('marketing_carrier_flight_number','')}")
        lines.append(f"  Aircraft:  {(dep_seg.get('aircraft') or {}).get('name','')}")
        lines.append(f"  Duration:  {dep_seg.get('duration','')}")
        baggage = dep_seg.get("passengers", [{}])[0].get("baggages", []) if dep_seg.get("passengers") else []
        if baggage:
            lines.append("  Baggage:  " + "; ".join([f"{b.get('quantity','')} {b.get('type','')}" for b in baggage]))
        lines.append("")

    if hotel:
        hotel_raw = hotel.get("raw") or {}
        hotel_info = hotel_raw.get("hotel", {}) or hotel_raw.get("hotel_info", {}) or {}
        lines.append("Hotel Summary:")
        lines.append(f" - Reference: {hotel_raw.get('reference') or hotel.get('booking_reference') or ''}")
        lines.append(f" - Name: {hotel_info.get('name') or hotel_raw.get('name') or ''}")
        lines.append(f" - Destination: {hotel_info.get('destinationName') or hotel_info.get('destinationCode') or ''}")
        lines.append(f" - Check-in: {hotel_info.get('checkIn') or hotel.get('check_in','')}")
        lines.append(f" - Check-out: {hotel_info.get('checkOut') or hotel.get('check_out','')}")
        lines.append(f" - Total: {hotel.get('total_net') or hotel_raw.get('totalNet') or ''} {hotel.get('currency') or hotel_raw.get('currency') or ''}".strip())

    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Your Nomada booking {ref or order_id}"
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"Sent booking email to {', '.join(recipients)} for {ref}")
    except Exception as e:
        print(f"Failed to send booking email: {e}")
