# map_servers/planning.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Google API tools
from map_servers.google_server import (
    search_nearby,
    get_place_details,
)

# LLM (OpenAI)
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ------------------------------------------------------
# Helper: Fetch hotel details
# ------------------------------------------------------
def _resolve_hotel(place_id: str) -> Dict[str, Any]:
    data = get_place_details(place_id)

    return {
        "place_id": place_id,
        "name": data.get("name"),
        "rating": data.get("rating"),
        "address": data.get("address"),
        "phone_number": data.get("phone_number"),
        "website": data.get("website"),
        "reviews": data.get("reviews"),
        "review_count": data.get("user_ratings_total"),
        "location": data.get("location"),
        "category": "hotel",
        "summary": f"{data.get('name')} rated {data.get('rating')} located at {data.get('address')}."
    }


# ------------------------------------------------------
# Helper: Fetch top place for each preference
# ------------------------------------------------------
def _get_places_by_preferences(hotel_id: str, preferences: List[str]) -> List[Dict[str, Any]]:
    hotel = get_place_details(hotel_id)
    loc = hotel["location"]
    lat = loc["lat"]
    lng = loc["lng"]

    places = []

    for pref in preferences:

        # map preferences to google types
        if pref.lower() in ["parks", "park"]:
            gtype = "park"
        elif pref.lower() in ["museums", "museum"]:
            gtype = "museum"
        elif pref.lower() in ["cafes", "cafe"]:
            gtype = "cafe"
        elif pref.lower() in ["restaurants", "restaurant"]:
            gtype = "restaurant"
        else:
            continue

        nearby = search_nearby(
            location=f"{lat},{lng}",
            radius=3000,
            type=gtype,
            min_rating=4.2,
        )

        if not nearby:
            continue

        top = nearby[0]
        detail = get_place_details(top["place_id"])

        places.append({
            "place_id": top["place_id"],
            "name": top["name"],
            "rating": top["rating"],
            "address": detail.get("address"),
            "phone_number": detail.get("phone_number"),
            "website": detail.get("website"),
            "reviews": detail.get("reviews"),
            "review_count": detail.get("user_ratings_total"),
            "location": detail.get("location"),
            "category": pref,
            "summary": f"{top['name']} rated {top['rating']} located at {detail.get('address')}."
        })

    return places


# ------------------------------------------------------
# LLM: Generate a detailed itinerary w/ info section
# ------------------------------------------------------
def _generate_itinerary_llm(hotel, preferences, places):
    prompt = f"""
You are an expert travel planner.

Create a **1-day itinerary** using ONLY the following places:

Hotel:
{hotel}

Places:
{places}

Preferences:
{preferences}

⚠️ STRICT RULES:
- Start at **08:00**.
- End the day around **18:00**.
- Itinerary must include:
  1. Breakfast
  2. Morning activity
  3. Lunch
  4. Afternoon activity
  5. Dinner
- Each item MUST include:
    - Time window (e.g. 09:00–10:30)
    - Activity name
    - Location name
    - Short description
    - EXTRA INFO section:
        - Rating
        - Address
        - Phone number (if any)
        - Website or email (if any)
        - #Reviews

Format example:

1. 08:00–09:00 — Breakfast at The Hotel  
   A warm description…

   **Info:**  
   • Rating: 4.5  
   • Reviews: 3200+  
   • Address: 123 Main Street  
   • Phone: +44 0000 000 000  
   • Website: example.com  

Return ONLY the numbered itinerary list.
"""

    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return res.choices[0].message.content.strip()


# ------------------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------------------
def plan_day_itinerary_simple(hotel_place_id: str, preferences: List[str]):
    hotel = _resolve_hotel(hotel_place_id)
    places = _get_places_by_preferences(hotel_place_id, preferences)
    itinerary = _generate_itinerary_llm(hotel, preferences, places)

    return {
        "hotel": hotel,
        "preferences": preferences,
        "places": places,
        "itinerary": itinerary
    }
