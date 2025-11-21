# map_servers/duffel_server.py


from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, List, Optional

import requests
from agents import function_tool

from .base import ServerParams


from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Duffel API configuration
DUFFEL_PARAMS = ServerParams(
    name="duffel_flights",
    base_url="https://api.duffel.com",
    description="Duffel API for flight search and booking.",
    commands={
        "search_offers": "/air/offer_requests",
        "get_offer": "/air/offers/{offer_id}",
        "create_order": "/air/orders",
        "get_order": "/air/orders/{order_id}"
    },
)


def _duffel_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Duffel-Version": "v2",
    }


def _get_duffel_token() -> Optional[str]:
    return os.getenv("DUFFEL_ACCESS_TOKEN") or os.getenv("DUFFEL_API_TOKEN")


# ------------------------
# Pure implementation APIs
# ------------------------

def search_flights_impl(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    cabin_class: str = "economy",
    max_offers: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search flight offers using Duffel API.

    Args:
        origin: IATA code of origin airport (e.g., "LHR").
        destination: IATA code of destination airport (e.g., "JFK").
        departure_date: ISO date YYYY-MM-DD.
        return_date: Optional return date YYYY-MM-DD for round trip.
        passengers: Number of adult passengers.
        cabin_class: "economy", "premium_economy", "business", or "first".
        max_offers: Maximum number of offers to return.

    Returns:
        A list of flight offers with:
        - id: Offer ID
        - airline: Airline name
        - price: Total price
        - currency: Currency code
        - cabin_class: Cabin class
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot search flights")
        return []

    origin = origin.upper().strip()
    destination = destination.upper().strip()
    passengers = max(1, passengers)
    max_offers = max(1, min(max_offers, 20))

    # Build slices
    slices = [{
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date
    }]
    if return_date:
        slices.append({
            "origin": destination,
            "destination": origin,
            "departure_date": return_date
        })

    # Create offer request
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["search_offers"]
    body = {
        "data": {
            "slices": slices,
            "passengers": [{"type": "adult"}] * passengers,
            "cabin_class": cabin_class,
        }
    }

    logger.debug("Creating offer request: %s %s", url, body)
    resp = requests.post(url, headers=_duffel_headers(token), json=body, timeout=30)
    resp.raise_for_status()
    offer_request = resp.json()

    request_id = offer_request.get("data", {}).get("id")
    if not request_id:
        logger.error("No request_id in offer request response")
        return []

    # Get offers for the request
    offers_url = DUFFEL_PARAMS.base_url + "/air/offers"
    params = {"offer_request_id": request_id}

    logger.debug("Fetching offers: %s %s", offers_url, params)
    resp = requests.get(offers_url, headers=_duffel_headers(token), params=params, timeout=30)
    resp.raise_for_status()
    offers_data = resp.json()

    offers = offers_data.get("data", [])[:max_offers]

    results: List[Dict[str, Any]] = []
    for offer in offers:
        owner = offer.get("owner", {})
        results.append({
            "id": offer.get("id"),
            "airline": owner.get("name") or "Unknown",
            "price": float(offer.get("total_amount", 0)),
            "currency": offer.get("total_currency", "USD"),
            "cabin_class": cabin_class,
        })

    return results

def create_order_impl(
    offer_id: str,
    payment_type: str = "balance",
    passengers: List[Dict[str, Any]] = [],
    mode: str = "instant",
    create_hold: bool = False,
) -> Dict[str, Any]:
    """
    Create a flight order using the Duffel API from the selected offer.

    Args:
        offer_id: The Duffel offer ID (e.g., "off_...").
        payment_type: The payment method (default: "balance").
        passengers: A list of passenger details.
        mode: "instant" or "hold" (default: "instant").
        create_hold: If True, creates a hold order without taking payment.

    Returns:
        A dictionary containing the order details.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot create order")
        return {"error": "Missing Duffel API token"}

    # Step 1: Get the offer details
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_offer"].format(offer_id=offer_id)
    resp = requests.get(url, headers=_duffel_headers(token), timeout=30)
    if resp.status_code != 200:
        logger.error(f"Failed to fetch offer details, status code {resp.status_code}")
        return {"error": "Failed to retrieve offer details"}

    offer = resp.json().get("data", {})
    total_amount = offer.get("total_amount")
    total_currency = offer.get("total_currency")
    offer_passengers = offer.get("passengers", [])

    # Step 2: Prepare the passengers data
    passengers_payload = []
    if passengers:
        for pax in passengers:
            pax_details = {"id": pax.get("id")}
            for field in ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number"]:
                if pax.get(field):
                    pax_details[field] = pax.get(field)
            passengers_payload.append(pax_details)
    else:
        # Default to the passengers in the offer if no custom passenger details are provided
        for pax in offer_passengers:
            passengers_payload.append({"id": pax.get("id")})

    # Step 3: Build the order creation payload
    order_payload: Dict[str, Any] = {
        "data": {
            "selected_offers": [offer_id],
            "passengers": passengers_payload,
            "type": "hold" if create_hold else "instant",  # Create hold order if specified
        }
    }

    # Include payment information unless it's a hold order
    if not create_hold:
        order_payload["data"]["payments"] = [
            {
                "type": payment_type,
                "amount": total_amount,
                "currency": total_currency,
            }
        ]

    # Step 4: Create the order
    create_order_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_order"]
    resp = requests.post(create_order_url, headers=_duffel_headers(token), json=order_payload, timeout=60)
    if resp.status_code != 201:
        logger.error(f"Failed to create order, status code {resp.status_code}")
        return {"error": "Order creation failed"}

    # Parse the response
    order_data = resp.json().get("data", {})
    if not order_data:
        return {"error": "Order created but response parsing failed"}

    # Step 5: Return the order details
    order_details = {
        "order_id": order_data.get("id"),
        "booking_reference": order_data.get("booking_reference"),
        "total": order_data.get("total_amount"),
        "currency": order_data.get("total_currency"),
        "order_type": order_data.get("type"),
        "payment_required_by": order_data.get("payment_required_by"),
        "passengers": order_data.get("passengers"),
        "itinerary": order_data.get("slices"),
    }

    return order_details

def get_order_impl(order_id: str) -> Dict[str, Any]:
    """
    Get the details of a specific order using Duffel API.

    Args:
        order_id: Duffel order ID (e.g., "ord_...").

    Returns:
        A dictionary containing the order details, such as passengers, itinerary, and payment info.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot retrieve order details")
        return {"error": "Missing Duffel API token"}

    # Define the URL for retrieving order details
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_order"].format(order_id=order_id)

    # Make the request to retrieve the order
    logger.debug("Retrieving order details: %s", url)
    resp = requests.get(url, headers=_duffel_headers(token), timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to retrieve order, status code %d: %s", resp.status_code, resp.text)
        return {"error": "Failed to retrieve order", "status_code": resp.status_code, "response": resp.json()}

    try:
        order = resp.json().get("data", {})
    except Exception as e:
        logger.error("Error parsing order response: %s", e)
        return {"error": "Could not parse order response"}

    # Structure the order details in a user-friendly format
    order_details = {
        "order_id": order.get("id"),
        "booking_reference": order.get("booking_reference"),
        "total": order.get("total_amount"),
        "currency": order.get("total_currency"),
        "created_at": order.get("created_at"),
        "offer_id": order.get("offer_id"),
    }

    # Passengers
    passengers = []
    for passenger in order.get("passengers", []):
        passengers.append({
            "id": passenger.get("id"),
            "given_name": passenger.get("given_name"),
            "family_name": passenger.get("family_name"),
            "born_on": passenger.get("born_on"),
            "email": passenger.get("email"),
            "phone_number": passenger.get("phone_number"),
        })
    order_details["passengers"] = passengers

    # Itinerary (Flight details)
    itinerary = []
    for slice in order.get("slices", []):
        for segment in slice.get("segments", []):
            itinerary.append({
                "origin": segment.get("origin", {}).get("iata_code"),
                "destination": segment.get("destination", {}).get("iata_code"),
                "departing_at": segment.get("departing_at"),
                "arriving_at": segment.get("arriving_at"),
                "flight": f"{segment.get('marketing_carrier', {}).get('name', '')} {segment.get('marketing_carrier_flight_number', '')}",
                "aircraft": segment.get("aircraft", {}).get("name"),
                "duration": segment.get("duration"),
            })
    order_details["itinerary"] = itinerary

    # Payment (if present)
    if isinstance(order.get("payment"), dict):
        payment = order["payment"]
        order_details["payment"] = {
            "amount": payment.get("amount"),
            "currency": payment.get("currency"),
            "type": payment.get("type"),
        }

    order_details["raw_order"] = order

    return order_details

def cancel_order_impl(order_id: str) -> Dict[str, Any]:
    """
    Cancel a flight order using the Duffel API.

    Args:
        order_id: The Duffel order ID to cancel (e.g., "ord_...").

    Returns:
        A dictionary containing the cancellation result.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot cancel order")
        return {"error": "Missing Duffel API token"}

    # Define the URL for cancelling the order
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["cancel_order"].format(order_id=order_id)

    # Send the request to cancel the order
    logger.debug("Cancelling order: %s", url)
    resp = requests.post(url, headers=_duffel_headers(token), timeout=30)
    if resp.status_code != 200:
        logger.error(f"Failed to cancel order, status code {resp.status_code}: {resp.text}")
        return {"error": "Failed to cancel order"}

    # Parse the response
    cancellation_data = resp.json().get("data", {})
    if not cancellation_data:
        return {"error": "Order cancellation failed, no data returned"}

    # Return the cancellation result
    return {
        "order_id": cancellation_data.get("id"),
        "status": cancellation_data.get("status"),
        "cancellation_date": cancellation_data.get("cancellation_date"),
        "raw_response": cancellation_data,
    }



# ------------------------
# Tool-wrapped APIs
# ------------------------

@function_tool
def cancel_order(order_id: str) -> Dict[str, Any]:
    """Tool wrapper for cancel_order_impl."""
    return cancel_order_impl(order_id=order_id)

@function_tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    cabin_class: str = "economy",
    max_offers: int = 5,
) -> List[Dict[str, Any]]:
    """Tool wrapper for search_flights_impl."""
    return search_flights_impl(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        passengers=passengers,
        cabin_class=cabin_class,
        max_offers=max_offers,
    )



# @function_tool
# def create_order(
#     offer_id: str,
#     payment_type: str = "balance",
#     passengers: List[Dict[str, Any]] = [],
#     mode: str = "instant",
#     create_hold: bool = False,
# ) -> Dict[str, Any]:
#     """Tool wrapper for create_order_impl."""
#     return create_order_impl(
#         offer_id=offer_id,
#         payment_type=payment_type,
#         passengers=passengers,
#         mode=mode,
#         create_hold=create_hold,
#     )

@function_tool
def get_order(
    order_id: str,
) -> Dict[str, Any]:
    """Tool wrapper for get_order_impl."""
    return get_order_impl(order_id=order_id)