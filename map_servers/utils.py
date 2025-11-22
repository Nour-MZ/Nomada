import json
import os
from typing import Any, Dict, Optional

from agents import function_tool

# File to store user decisions (you can adjust this path as needed)
DECISIONS_FILE_PATH = "user_decisions.json"


def _load_decisions() -> Dict[str, Any]:
    """
    Helper function to load existing user decisions from a local JSON file.
    Returns an empty dictionary if no data is available.
    """
    if os.path.exists(DECISIONS_FILE_PATH):
        with open(DECISIONS_FILE_PATH, "r") as f:
            return json.load(f)
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
