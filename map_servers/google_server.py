# map_servers/google_server.py

from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, List, Optional

import requests

try:
    from agents import function_tool
except ImportError:
    def function_tool(func):
        return func


from .base import ServerParams

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# --------------------------------------
# Google Maps API Configuration
# --------------------------------------

GOOGLE_PARAMS = ServerParams(
    name="google_maps",
    base_url="https://maps.googleapis.com/maps/api",
    description="Google Maps API for places search, geocoding, routing, and elevation.",
    commands={
        "nearby_search": "/place/nearbysearch/json",
        "place_details": "/place/details/json",
        "autocomplete": "/place/autocomplete/json",
        "geocode": "/geocode/json",
        "reverse_geocode": "/geocode/json",
        "distance_matrix": "/distancematrix/json",
        "directions": "/directions/json",
        "elevation": "/elevation/json",
    },
)


def _google_key() -> Optional[str]:
    """Retrieve Google Maps API key from environment."""
    return os.getenv("GOOGLE_MAPS_API_KEY")


def _google_params(extra: Dict[str, Any] = None) -> Dict[str, Any]:
    """Standard query params for all Google API calls."""
    key = _google_key()
    if not key:
        logger.warning("GOOGLE_MAPS_API_KEY not set in environment")
        return {}

    params = {"key": key}

    if extra:
        params.update(extra)

    return params


# ---------------------------------------
# Google Maps Pure Implementation Methods
# ---------------------------------------

def search_nearby_impl(
    location: str,
    radius: int = 1500,
    keyword: Optional[str] = None,
    type: Optional[str] = None,
    open_now: bool = False,
    min_rating: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Search for nearby places around a given location (lat,lng).
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["nearby_search"]

    params = {
        "location": location,      # "lat,lng"
        "radius": radius,
    }
    if keyword:
        params["keyword"] = keyword
    if type:
        params["type"] = type
    if open_now:
        params["opennow"] = "true"

    resp = requests.get(url, params=_google_params(params), timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for place in data.get("results", []):
        if min_rating and place.get("rating", 0) < min_rating:
            continue

        results.append({
            "place_id": place.get("place_id"),
            "name": place.get("name"),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total"),
            "address": place.get("vicinity"),
            "location": place.get("geometry", {}).get("location"),
            "types": place.get("types"),
            "open_now": place.get("opening_hours", {}).get("open_now"),
        })

    return results


def get_place_details_impl(place_id: str) -> Dict[str, Any]:
    """
    Fetch full details for a specific place using its place_id.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["place_details"]
    params = {"place_id": place_id, "fields": "name,rating,formatted_address,formatted_phone_number,"
                                              "opening_hours,website,geometry,price_level,review,user_ratings_total"}

    resp = requests.get(url, params=_google_params(params), timeout=20)
    resp.raise_for_status()
    data = resp.json().get("result", {})

    return {
        "place_id": place_id,
        "name": data.get("name"),
        "rating": data.get("rating"),
        "user_ratings_total": data.get("user_ratings_total"),
        "address": data.get("formatted_address"),
        "phone_number": data.get("formatted_phone_number"),
        "website": data.get("website"),
        "price_level": data.get("price_level"),
        "location": data.get("geometry", {}).get("location"),
        "opening_hours": data.get("opening_hours"),
        "reviews": data.get("reviews"),
    }


def maps_autocomplete_impl(input_text: str) -> List[Dict[str, Any]]:
    """
    Provide autocomplete predictions for user text input.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["autocomplete"]
    params = {"input": input_text}

    resp = requests.get(url, params=_google_params(params), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    predictions = []
    for p in data.get("predictions", []):
        predictions.append({
            "description": p.get("description"),
            "place_id": p.get("place_id"),
            "types": p.get("types"),
        })

    return predictions


def maps_geocode_impl(address: str) -> Dict[str, Any]:
    """
    Convert an address into latitude and longitude.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["geocode"]
    params = {"address": address}

    resp = requests.get(url, params=_google_params(params), timeout=15)
    resp.raise_for_status()
    data = resp.json().get("results", [])

    if not data:
        return {}

    result = data[0]
    return {
        "address": result.get("formatted_address"),
        "location": result.get("geometry", {}).get("location"),
        "place_id": result.get("place_id"),
    }


def maps_reverse_geocode_impl(lat: float, lng: float) -> Dict[str, Any]:
    """
    Convert coordinates (lat, lng) into a readable address.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["reverse_geocode"]
    params = {"latlng": f"{lat},{lng}"}

    resp = requests.get(url, params=_google_params(params), timeout=15)
    resp.raise_for_status()
    data = resp.json().get("results", [])

    if not data:
        return {}

    result = data[0]
    return {
        "address": result.get("formatted_address"),
        "place_id": result.get("place_id"),
        "types": result.get("types"),
    }


def maps_distance_matrix_impl(
    origins: List[str],
    destinations: List[str],
    mode: str = "driving",
) -> Dict[str, Any]:
    """
    Calculate distance and duration between multiple origins and destinations.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["distance_matrix"]
    params = {
        "origins": "|".join(origins),
        "destinations": "|".join(destinations),
        "mode": mode,
    }

    resp = requests.get(url, params=_google_params(params), timeout=20)
    resp.raise_for_status()
    return resp.json()


def maps_directions_impl(
    origin: str,
    destination: str,
    mode: str = "driving",
) -> Dict[str, Any]:
    """
    Get turn-by-turn directions between two locations.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["directions"]
    params = {"origin": origin, "destination": destination, "mode": mode}

    resp = requests.get(url, params=_google_params(params), timeout=20)
    resp.raise_for_status()
    return resp.json()


def maps_elevation_impl(locations: List[str]) -> Dict[str, Any]:
    """
    Get elevation data (height above sea level) for one or more locations.
    """
    url = GOOGLE_PARAMS.base_url + GOOGLE_PARAMS.commands["elevation"]
    params = {"locations": "|".join(locations)}

    resp = requests.get(url, params=_google_params(params), timeout=20)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------
# Tool-Wrapped API Functions
# ---------------------------------------

@function_tool
def search_nearby(
    location: str,
    radius: int = 1500,
    keyword: Optional[str] = None,
    type: Optional[str] = None,
    open_now: bool = False,
    min_rating: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Tool wrapper for search_nearby_impl."""
    return search_nearby_impl(
        location=location,
        radius=radius,
        keyword=keyword,
        type=type,
        open_now=open_now,
        min_rating=min_rating,
    )


@function_tool
def get_place_details(place_id: str) -> Dict[str, Any]:
    """Tool wrapper for get_place_details_impl."""
    return get_place_details_impl(place_id)


@function_tool
def maps_autocomplete(input_text: str) -> List[Dict[str, Any]]:
    """Tool wrapper for maps_autocomplete_impl."""
    return maps_autocomplete_impl(input_text)


@function_tool
def maps_geocode(address: str) -> Dict[str, Any]:
    """Tool wrapper for maps_geocode_impl."""
    return maps_geocode_impl(address)


@function_tool
def maps_reverse_geocode(lat: float, lng: float) -> Dict[str, Any]:
    """Tool wrapper for maps_reverse_geocode_impl."""
    return maps_reverse_geocode_impl(lat, lng)


@function_tool
def maps_distance_matrix(
    origins: List[str],
    destinations: List[str],
    mode: str = "driving",
) -> Dict[str, Any]:
    """Tool wrapper for maps_distance_matrix_impl."""
    return maps_distance_matrix_impl(origins, destinations, mode)


@function_tool
def maps_directions(
    origin: str,
    destination: str,
    mode: str = "driving",
) -> Dict[str, Any]:
    """Tool wrapper for maps_directions_impl."""
    return maps_directions_impl(origin, destination, mode)


@function_tool
def maps_elevation(locations: List[str]) -> Dict[str, Any]:
    """Tool wrapper for maps_elevation_impl."""
    return maps_elevation_impl(locations)
