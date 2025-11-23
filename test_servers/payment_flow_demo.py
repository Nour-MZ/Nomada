#!/usr/bin/env python3
"""
Quick Duffel payment flow demo:
1) search for offers
2) pick first offer
3) create HOLD order (so payment is separate)
4) create payment (balance by default; card if you provide payment_source)

Update the PASSENGERS block and optionally SLICES before running.
Requires DUFFEL_API_TOKEN in environment.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Any, List
sys.path.insert(0, "..")
from map_servers.duffel_server import search_flights_impl, create_order_impl

from map_servers.duffel_server import (
    search_flights_impl,
    create_order_impl,
    create_payment_impl,
)

# Adjust these if you want to test different itineraries
SLICES = [
    {"origin": "BEY", "destination": "RUH", "departure_date": "2025-12-25"},
]

# Fill with your passenger details
PASSENGERS: List[Dict[str, Any]] = [
    {
        "title": "Mr",
        "gender": "m",
        "given_name": "Nouredine",
        "family_name": "Mezher",
        "born_on": "2002-02-11",
        "email": "nourmezher5@gmail.com",
        "phone_number": "+96178887063",
    }
]


def ensure_token() -> None:
    if not os.getenv("DUFFEL_API_TOKEN") and not os.getenv("DUFFEL_ACCESS_TOKEN"):
        print("DUFFEL_API_TOKEN not set; please add it to your environment or .env", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ensure_token()

    print("=== 1) Searching offers ===")
    offers = search_flights_impl(slices=SLICES, passengers=[{"type": "adult"}], max_offers=3)
    if not offers:
        print("No offers returned; check token or try different search params")
        return

    offer = offers[0]
    print("Using offer:", offer)

    print("\n=== 2) Creating HOLD order ===")
    order = create_order_impl(
        offer_id=offer["id"],
        passengers=PASSENGERS,
        payment_type="balance",
        mode="hold",
        create_hold=True,
    )
    print("Order response:", order)

    if isinstance(order, dict) and order.get("error"):
        print("Order failed; aborting payment.")
        return

    order_id = order.get("order_id")
    if not order_id:
        print("No order_id returned; aborting payment.")
        return

    print("\n=== 3) Creating payment ===")
    payment = create_payment_impl(
        order_id=order_id,
        payment_type="balance",
        # For Duffel Pay card tests, supply payment_source fields (e.g., {"payment_method_id": "pm_xxx"})
        # payment_type="card",
        # payment_source={"payment_method_id": "pm_xxx"},
    )
    print("Payment response:", payment)


if __name__ == "__main__":
    main()
