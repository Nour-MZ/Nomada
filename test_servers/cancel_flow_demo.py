#!/usr/bin/env python3
"""
Quick Duffel cancel flow demo:
1) search for offers
2) pick first offer
3) create HOLD order
4) cancel the order (auto-confirm)

Update the PASSENGERS block and optionally SLICES before running.
Requires DUFFEL_API_TOKEN in environment.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Any, List

# Allow running from test_servers/ with repo imports
sys.path.insert(0, "..")

from map_servers.duffel_server import (
    search_flights_impl,
    create_order_impl,
    cancel_order_impl,
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
        print("Order failed; aborting cancellation.")
        return

    order_id = order.get("order_id")
    if not order_id:
        print("No order_id returned; aborting cancellation.")
        return

    print("\n=== 3) Cancelling order (auto-confirm) ===")
    cancellation = cancel_order_impl(order_id=order_id, auto_confirm=True)
    print("Cancellation response:", cancellation)


if __name__ == "__main__":
    main()
