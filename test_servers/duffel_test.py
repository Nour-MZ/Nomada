# test_servers/duffel_test.py

"""
Very lightweight tests / demo calls for Duffel server tools.

Here we call the pure implementation functions directly, not the tool-wrapped
objects from Agents SDK, to keep tests simple.
"""

from __future__ import annotations

import sys
from pprint import pprint

sys.path.insert(0, "..")
from map_servers.flight_server import search_flights_impl, create_order_impl


def demo_search_flights() -> None:
    print("=== Duffel Flight Search Demo ===")
    results = search_flights_impl(
        slices=[{
            "origin": "LHR",
            "destination": "JFK",
            "departure_date": "2025-12-25"
        }, {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-01-05"
        }],
        passengers=[{"type": "adult"} for _ in range(4)],
        cabin_class="economy",
        max_offers=3,
    )
    pprint(results)


def demo_create_order() -> None:
    print("=== Duffel Create Order Demo ===")
    # First, search for real offers
    offers = search_flights_impl(
        slices=[{
            "origin": "JFK",
            "destination": "LAX",
            "departure_date": "2025-12-01"
        }],
        passengers=[{"type": "adult"}],
        cabin_class="economy",
        max_offers=1
    )

    if not offers:
        print("No offers found, cannot create order")
        return

    offer_id = offers[0]["id"]
    print(f"Using offer: {offer_id}")

    order_details = create_order(
        offer_id=offer_id,
        payment_type="balance",
        passengers=[{
            "id": "pax_001",  # This will need to match actual passenger IDs from offer
            "title": "Mr.",
            "given_name": "John",
            "family_name": "Doe",
            "born_on": "1985-01-15",
            "email": "john.doe@example.com",
            "phone_number": "+1234567890"
        }],
        mode="instant",
        create_hold=False  # Set to True to create a hold order
    )
    pprint(order_details)



if __name__ == "__main__":
    # demo_create_order()
    demo_search_flights()
