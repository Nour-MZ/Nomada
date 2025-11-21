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
from map_servers.duffel_server import search_flights_impl


def demo_search_flights() -> None:
    print("=== Duffel Flight Search Demo ===")
    results = search_flights_impl(
        origin="LHR",
        destination="JFK",
        departure_date="2025-12-25",
        return_date="2026-01-05",
        passengers=2,
        cabin_class="economy",
        max_offers=3,
    )
    pprint(results)


def demo_search_flights_no_token() -> None:
    print("=== Duffel Flight Search Demo (No Token) ===")
    # This should return empty list if no token
    results = search_flights_impl("BEY", "FRA", "2025-12-01")
    pprint(results)


if __name__ == "__main__":
    demo_search_flights_no_token()
    demo_search_flights()
