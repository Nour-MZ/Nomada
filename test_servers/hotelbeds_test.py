#!/usr/bin/env python3
"""
Minimal Hotelbeds test script for the test environment.

Steps:
1) Checks for HOTELBEDS_API_KEY and HOTELBEDS_SECRET.
2) Searches availability for a known test destination (default PMI).

Note: Booking requires a rateKey from a search result; this script only
performs the search to validate connectivity and payload shape.
"""

from __future__ import annotations

import os
import sys
from pprint import pprint
from typing import Dict, Any

# Allow running from test_servers/
sys.path.insert(0, "..")

from map_servers.hotelbeds_server import search_hotels_impl


def ensure_creds() -> None:
    if not os.getenv("HOTELBEDS_API_KEY") or not os.getenv("HOTELBEDS_SECRET"):
        print("Missing HOTELBEDS_API_KEY or HOTELBEDS_SECRET; add them to .env or environment.")
        sys.exit(1)


def run_search(destination: str = "PMI") -> Dict[str, Any]:
    print(f"Searching hotels in {destination} (test env)...")
    return search_hotels_impl(
        destination_code=destination,
        check_in="2025-12-25",
        check_out="2025-12-26",
        rooms=[{"adults": 2, "children": 0}],
        limit=3,
    )


def main() -> None:
    ensure_creds()
    result = run_search()
    pprint(result)


if __name__ == "__main__":
    main()
