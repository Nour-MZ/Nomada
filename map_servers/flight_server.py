# map_servers/flight_server.py


from __future__ import annotations

import logging
import os
import json
from pathlib import Path
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
        "get_order": "/air/orders/{order_id}",
        "create_payment": "/air/payments",
        "create_order_cancellation": "/air/order_cancellations",
        "confirm_order_cancellation": "/air/order_cancellations/{order_cancellation_id}/actions/confirm",
        "create_order_change_request": "/air/order_change_requests",
        "list_order_change_offers": "/air/order_change_offers",
        "get_order_change_offer": "/air/order_change_offers/{order_change_offer_id}",
        "create_order_change": "/air/order_changes",
    },
)
from .flight_store import save_flight_search_results

# Resolve flights DB path relative to repo root (databases/flights.sqlite)
_FLIGHT_DB_PATH = (Path(__file__).resolve().parent.parent / "databases" / "flights.sqlite")
_FLIGHT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

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
    *,
    slices: List[Dict[str, Any]],
    passengers: List[Dict[str, Any]] = None,
    cabin_class: str = "economy",
    max_offers: int = 5
) -> List[Dict[str, Any]]:
    """
    Search flight offers using Duffel API.

    Args:
        slices: List of journey legs (each dict includes "origin", "destination", "departure_date").
        passengers: List of passenger dictionaries (each dict includes "type": "adult"/"child"/"infant").
        cabin_class: "economy", "premium_economy", "business", or "first".
        max_offers: Maximum number of offers to return.

    Returns:
        A list of flight offers with:
         - id: Offer ID
         - airline: Airline name
         - price: Total price
         - currency: Currency code
         - cabin_class: Cabin class
         - passenger_ids: List of passenger IDs
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot search flights")
        return []

    # Validate slices
    if not isinstance(slices, list) or len(slices) == 0:
        raise ValueError("`slices` must be a non‑empty list of journey leg dicts")

    # Normalize passengers list - handle both integer and list inputs for backward compatibility
    if passengers is None:
        passenger_list = [{"type": "adult"}]
    elif isinstance(passengers, int):
        num = max(1, passengers)
        passenger_list = [{"type": "adult"} for _ in range(num)]
    elif isinstance(passengers, list):
        if len(passengers) == 0:
            passenger_list = [{"type": "adult"}]
        else:
            passenger_list = passengers
    else:
        raise ValueError("`passengers` must be an integer or a list of passenger dictionaries")

    # Validate cabin_class
    cabin_class_lower = cabin_class.lower()
    if cabin_class_lower not in {"economy", "premium_economy", "business", "first"}:
        raise ValueError(f"Invalid cabin_class: {cabin_class}")

    # Limit max_offers
    max_offers = max(1, min(max_offers, 20))

    # Build request body
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["search_offers"]
    body: Dict[str, Any] = {
        "data": {
            "slices": slices,
            "passengers": passenger_list,
            "cabin_class": cabin_class_lower,
        }
    }

    logger.debug("Creating offer request: %s %s", url, body)
    resp = None
    try:
        resp = requests.post(url, headers=_duffel_headers(token), json=body, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
        logger.error("Offer request failed: %s", e)
        return {
            "error": f"Duffel offer request failed: {e}",
            "status": status_code,
            "response": error_payload,
            "payload_sent": body,
        }
    offer_request = resp.json()
    

    request_id = offer_request.get("data", {}).get("id")
    if not request_id:
        logger.error("No request_id in offer request response: %s", offer_request)
        return []

    offers_url = DUFFEL_PARAMS.base_url + "/air/offers"
    params = {"offer_request_id": request_id}
    logger.debug("Fetching offers: %s %s", offers_url, params)
    resp = None
    try:
        resp = requests.get(offers_url, headers=_duffel_headers(token), params=params, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
        logger.error("Fetching offers failed: %s", e)
        return {
            "error": f"Failed to fetch offers: {e}",
            "status": status_code,
            "response": error_payload,
            "payload_sent": params,
        }
    offers_data = resp.json()

    all_offers = offers_data.get("data", []) or []
    top_offers = all_offers[:10]
    try:
        save_flight_search_results(top_offers, query=slices, db_path=str(_FLIGHT_DB_PATH))
    except Exception as e:
        print("Failed to save flight search results: %s", e)
    # Return capped set to keep responses manageable
    return top_offers

def create_order_impl(
    offer_id: str,
    payment_type: str = "balance",
    passengers: Optional[List[Dict[str, Any]]] = None,
    mode: str = "instant",
    create_hold: bool = False,
    payment_source: Optional[Dict[str, Any]] = None,
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
        A dictionary containing the order details or error information.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot create order")
        return {"error": "Missing Duffel API token"}

    # Step 1: Get the offer details
    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_offer"].format(offer_id=offer_id)
    resp = None
    try:
        resp = requests.get(url, headers=_duffel_headers(token), timeout=30)
        resp.raise_for_status()  # Raises an HTTPError for bad responses (4xx, 5xx)
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
        logger.error("Failed to fetch offer details: %s", e)
        return {"error": f"Failed to retrieve offer details: {e}", "status": status_code, "response": error_payload}

    offer = resp.json().get("data", {})
    if not offer:
        logger.error("No offer data found in the response")
        return {"error": "No offer data found in the response"}

    total_amount = offer.get("total_amount")
    total_currency = offer.get("total_currency")
    offer_passengers = offer.get("passengers", [])

    # Step 2: Prepare the passengers data (Duffel requires the key personal fields)
    required_fields = ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number"]

    def _build_pax_payload(pax: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a passenger payload and keep only fields Duffel accepts. This also
        allows us to surface which mandatory fields are missing before hitting the API.
        """
        payload: Dict[str, Any] = {}
        if pax.get("id"):
            payload["id"] = pax["id"]
        for field in required_fields:
            value = pax.get(field)
            if value:
                payload[field] = value
        return payload

    def _merge_passenger_sources() -> List[Dict[str, Any]]:
        """
        Combine user-provided passengers with the IDs returned in the offer so we
        always send the Duffel passenger IDs while honoring any extra details the
        user supplied.
        """
        if passengers and offer_passengers:
            merged: List[Dict[str, Any]] = []
            for idx, pax in enumerate(passengers):
                offer_pax = offer_passengers[idx] if idx < len(offer_passengers) else {}
                merged.append({**offer_pax, **pax})
            return merged
        return passengers or offer_passengers

    passengers_source = _merge_passenger_sources() or []

    passengers_payload: List[Dict[str, Any]] = []
    missing_fields: List[Dict[str, Any]] = []

    for idx, pax in enumerate(passengers_source):
        payload = _build_pax_payload(pax)
        passengers_payload.append(payload)

        missing = [field for field in ["id", *required_fields] if not payload.get(field)]
        if missing:
            missing_fields.append({"passenger_index": idx, "missing_fields": missing})

    if not passengers_payload:
        return {"error": "No passenger data available to create the order"}

    if missing_fields:
        return {
            "error": "Missing required passenger details",
            "required_fields": ["id", *required_fields],
            "missing": missing_fields,
            "hint": "Provide passengers with all required fields or share the missing details so I can retry.",
        }

    # Step 3: Build the order creation payload
    order_type = "hold" if create_hold or mode == "hold" else "instant"

    order_payload: Dict[str, Any] = {
        "data": {
            "selected_offers": [offer_id],
            "passengers": passengers_payload,
            "type": order_type,
        }
    }

    # Include payment information unless it's a hold order
    if order_type == "instant":
        payment_body: Dict[str, Any] = {
            "type": payment_type,
            "amount": total_amount,
            "currency": total_currency,
        }
        if payment_source and isinstance(payment_source, dict):
            # Allow card/gateway details (e.g., token/payment_method_id) to pass through
            payment_body.update(payment_source)
        order_payload["data"]["payments"] = [payment_body]

    # Step 4: Create the order
    create_order_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_order"]
    resp = None
    try:
        resp = requests.post(create_order_url, headers=_duffel_headers(token), json=order_payload, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
                print(error_payload)
                print(order_payload)
        logger.error("Failed to create order: %s", e)
        print(error_payload)
        return {
            "error": f"Order creation failed: {e}",
            "status": status_code,
            "response": error_payload,
            "payload_sent": order_payload,
        }

    # Parse the response
    order_data = resp.json().get("data", {})
    if not order_data:
        logger.error("Order created but response parsing failed")
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

def get_offer_impl(offer_id: str) -> Dict[str, Any]:
    """
    Fetch detailed information about a specific offer, including segments,
    cabin, baggage, and pricing.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot fetch offer")
        return {"error": "Missing Duffel API token"}

    url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_offer"].format(offer_id=offer_id)
    resp = None
    try:
        resp = requests.get(url, headers=_duffel_headers(token), timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
        logger.error("Failed to fetch offer: %s", e)
        return {"error": f"Failed to fetch offer: {e}", "status": status_code, "response": payload}

    data = resp.json().get("data", {})
    owner = data.get("owner", {}) or {}
    slices_out: List[Dict[str, Any]] = []
    for sl in data.get("slices", []):
        segments_out: List[Dict[str, Any]] = []
        for seg in sl.get("segments", []):
            segments_out.append({
                "origin": seg.get("origin", {}).get("iata_code"),
                "destination": seg.get("destination", {}).get("iata_code"),
                "departing_at": seg.get("departing_at"),
                "arriving_at": seg.get("arriving_at"),
                "marketing_carrier": seg.get("marketing_carrier", {}).get("name"),
                "marketing_flight_number": seg.get("marketing_carrier_flight_number"),
                "operating_carrier": seg.get("operating_carrier", {}).get("name"),
                "operating_flight_number": seg.get("operating_carrier_flight_number"),
                "aircraft": seg.get("aircraft", {}).get("name"),
                "duration": seg.get("duration"),
                "stops": seg.get("stops", []),
                "baggage": seg.get("passengers", [{}])[0].get("baggages", []) if seg.get("passengers") else [],
                "cabin_class": seg.get("passengers", [{}])[0].get("cabin_class") if seg.get("passengers") else None,
                "seat": seg.get("passengers", [{}])[0].get("seat") if seg.get("passengers") else None,
            })
        slices_out.append({
            "origin": sl.get("origin", {}).get("iata_code"),
            "destination": sl.get("destination", {}).get("iata_code"),
            "departing_at": sl.get("segments", [{}])[0].get("departing_at") if sl.get("segments") else None,
            "arriving_at": sl.get("segments", [{}])[-1].get("arriving_at") if sl.get("segments") else None,
            "duration": sl.get("duration"),
            "fare_brand_name": sl.get("fare_brand_name"),
            "segments": segments_out,
        })

    return {
        "offer_id": data.get("id"),
        "owner": owner.get("name"),
        "cabin_class": data.get("cabin_class"),
        "total_amount": data.get("total_amount"),
        "total_currency": data.get("total_currency"),
        "allowed_passenger_identity_document_required": data.get("passenger_identity_documents_required"),
        "slices": slices_out,
        "raw": data,
    }

def request_order_change_offers_impl(
    order_id: str,
    slices: Optional[List[Dict[str, Any]]] = None,
    max_offers: int = 5,
) -> Dict[str, Any]:
    """
    Request change offers for an order. Provide new slices to change dates/routes.
    Returns a set of change offers with pricing/penalties.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot request change offers")
        return {"error": "Missing Duffel API token"}

    max_offers = max(1, min(max_offers, 10))

    body: Dict[str, Any] = {"data": {"order_id": order_id}}
    if slices:
        body["data"]["slices"] = slices

    # Create change request
    create_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_order_change_request"]
    create_resp = None
    try:
        create_resp = requests.post(create_url, headers=_duffel_headers(token), json=body, timeout=30)
        create_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        payload: Any = {}
        status_code = None
        if create_resp is not None:
            status_code = create_resp.status_code
            try:
                payload = create_resp.json()
            except Exception:
                payload = {"text": create_resp.text}
        logger.error("Failed to create order change request: %s", e)
        return {"error": f"Failed to create order change request: {e}", "status": status_code, "response": payload, "payload_sent": body}

    change_request_id = create_resp.json().get("data", {}).get("id")
    if not change_request_id:
        return {"error": "Change request created but id missing", "response": create_resp.json()}

    # Fetch change offers
    offers_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["list_order_change_offers"]
    params = {"order_change_request_id": change_request_id}
    list_resp = None
    try:
        list_resp = requests.get(offers_url, headers=_duffel_headers(token), params=params, timeout=30)
        list_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        payload: Any = {}
        status_code = None
        if list_resp is not None:
            status_code = list_resp.status_code
            try:
                payload = list_resp.json()
            except Exception:
                payload = {"text": list_resp.text}
        logger.error("Failed to fetch order change offers: %s", e)
        return {"error": f"Failed to fetch order change offers: {e}", "status": status_code, "response": payload}

    change_offers = list_resp.json().get("data", [])[:max_offers]
    simplified: List[Dict[str, Any]] = []
    for offer in change_offers:
        simplified.append({
            "order_change_offer_id": offer.get("id"),
            "change_total_amount": offer.get("change_total_amount"),
            "change_total_currency": offer.get("change_total_currency"),
            "penalty_amount": offer.get("penalty_amount"),
            "penalty_currency": offer.get("penalty_currency"),
            "refund_to": offer.get("refund_to"),
            "new_total_amount": offer.get("new_total_amount"),
            "new_total_currency": offer.get("new_total_currency"),
            "slices": offer.get("slices"),
        })

    return {
        "order_change_request_id": change_request_id,
        "offers": simplified,
        "raw": change_offers,
    }

def confirm_order_change_impl(
    order_change_offer_id: str,
    payment_type: str = "balance",
    amount: Optional[str] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Confirm an order change offer. If amount/currency are omitted, fetch the
    offer to determine change_total.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot confirm change offer")
        return {"error": "Missing Duffel API token"}

    resolved_amount = amount
    resolved_currency = currency

    if amount is None or currency is None:
        offer_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_order_change_offer"].format(order_change_offer_id=order_change_offer_id)
        offer_resp = None
        try:
            offer_resp = requests.get(offer_url, headers=_duffel_headers(token), timeout=30)
            offer_resp.raise_for_status()
            offer_data = offer_resp.json().get("data", {})
            resolved_amount = resolved_amount or offer_data.get("change_total_amount")
            resolved_currency = resolved_currency or offer_data.get("change_total_currency")
        except requests.exceptions.RequestException as e:
            payload: Any = {}
            status_code = None
            if offer_resp is not None:
                status_code = offer_resp.status_code
                try:
                    payload = offer_resp.json()
                except Exception:
                    payload = {"text": offer_resp.text}
            logger.error("Failed to fetch order change offer before confirming: %s", e)
            return {"error": f"Could not fetch change offer {order_change_offer_id}", "status": status_code, "response": payload}

    change_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_order_change"]
    payload = {
        "data": {
            "order_change_offer_id": order_change_offer_id,
        }
    }
    if resolved_amount and resolved_currency:
        payload["data"]["payment"] = {
            "type": payment_type,
            "amount": str(resolved_amount),
            "currency": resolved_currency,
        }

    resp = None
    try:
        resp = requests.post(change_url, headers=_duffel_headers(token), json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
        logger.error("Failed to confirm order change: %s", e)
        return {"error": f"Order change confirmation failed: {e}", "status": status_code, "response": error_payload, "payload_sent": payload}

    data = resp.json().get("data", {})
    return {
        "order_change_id": data.get("id"),
        "order_id": data.get("order_id"),
        "payment_status": data.get("payment_status"),
        "refund_to": data.get("refund_to"),
        "refund_amount": data.get("refund_amount"),
        "refund_currency": data.get("refund_currency"),
        "new_total_amount": data.get("new_total_amount"),
        "new_total_currency": data.get("new_total_currency"),
        "raw": data,
    }

def create_payment_impl(
    order_id: str,
    amount: Optional[str] = None,
    currency: Optional[str] = None,
    payment_type: str = "balance",
    payment_source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a payment for an existing order. If amount or currency are omitted,
    the order is fetched and its total is used.

    For non-balance payments (e.g., cards via Duffel Payments), pass
    payment_type (e.g., \"card\") and any provider-specific fields in
    payment_source (e.g., token/payment_method_id). These are sent through
    to Duffel as-is so integrators can experiment with supported types.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot create payment")
        return {"error": "Missing Duffel API token"}

    resolved_amount = amount
    resolved_currency = currency
    order_data: Dict[str, Any] = {}

    order_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["get_order"].format(order_id=order_id)
    order_resp = None
    try:
        order_resp = requests.get(order_url, headers=_duffel_headers(token), timeout=30)
        order_resp.raise_for_status()
        order_data = order_resp.json().get("data", {})
        resolved_amount = resolved_amount or order_data.get("total_amount")
        resolved_currency = resolved_currency or order_data.get("total_currency")
    except requests.exceptions.RequestException as e:
        payload: Any = {}
        status_code = None
        if order_resp is not None:
            status_code = order_resp.status_code
            try:
                payload = order_resp.json()
            except Exception:
                payload = {"text": order_resp.text}
        logger.error("Failed to fetch order before payment: %s", e)
        return {"error": f"Could not fetch order {order_id} to determine payment amount", "status": status_code, "response": payload}

    if (order_data.get("type") == "instant") and (order_data.get("payment") or order_data.get("payments")):
        return {
            "error": "Order is instant and already includes payment; cannot create a separate payment",
            "order_id": order_id,
            "hint": "Create the order as a hold (type='hold' or create_hold=True) if you want to pay later.",
        }

    if not resolved_amount or not resolved_currency:
        return {"error": "Payment amount or currency is missing and could not be resolved"}

    payment_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_payment"]
    payment_body: Dict[str, Any] = {
        "type": payment_type,
        "amount": str(resolved_amount),
        "currency": resolved_currency,
    }
    if payment_source and isinstance(payment_source, dict):
        # Allow caller to pass gateway-specific fields (e.g., token/payment_method_id for card payments)
        payment_body.update(payment_source)

    payload = {"data": {"order_id": order_id, "payment": payment_body}}

    resp = None
    try:
        resp = requests.post(payment_url, headers=_duffel_headers(token), json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if resp is not None:
            status_code = resp.status_code
            try:
                error_payload = resp.json()
            except Exception:
                error_payload = {"text": resp.text}
        logger.error("Failed to create payment: %s", e)
        return {"error": f"Payment creation failed: {e}", "status": status_code, "response": error_payload, "payload_sent": payload}

    payment_data = resp.json().get("data", {})
    return {
        "payment_id": payment_data.get("id"),
        "order_id": payment_data.get("order_id"),
        "amount": payment_data.get("amount"),
        "currency": payment_data.get("currency"),
        "type": payment_data.get("type"),
        "created_at": payment_data.get("created_at"),
        "raw": payment_data,
    }

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

def cancel_order_impl(order_id: str, auto_confirm: bool = True) -> Dict[str, Any]:
    """
    Request and optionally confirm a Duffel order cancellation.

    Args:
        order_id: The Duffel order ID to cancel (e.g., "ord_...").
        auto_confirm: If True, confirm the cancellation immediately to finalize refund.
    """
    token = _get_duffel_token()
    if not token:
        logger.warning("DUFFEL_ACCESS_TOKEN not set, cannot cancel order")
        return {"error": "Missing Duffel API token"}

    create_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["create_order_cancellation"]
    create_payload = {"data": {"order_id": order_id}}

    create_resp = None
    try:
        create_resp = requests.post(create_url, headers=_duffel_headers(token), json=create_payload, timeout=30)
        create_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if create_resp is not None:
            status_code = create_resp.status_code
            try:
                error_payload = create_resp.json()
            except Exception:
                error_payload = {"text": create_resp.text}
        logger.error("Failed to create cancellation request: %s", e)
        return {"error": f"Failed to create cancellation request: {e}", "status": status_code, "response": error_payload, "payload_sent": create_payload}

    cancellation_data = create_resp.json().get("data", {})
    cancellation_id = cancellation_data.get("id")

    if not cancellation_id:
        return {"error": "Cancellation request created but no ID returned", "raw": cancellation_data}

    result: Dict[str, Any] = {
        "order_id": order_id,
        "cancellation_id": cancellation_id,
        "refund_amount": cancellation_data.get("refund_amount"),
        "refund_currency": cancellation_data.get("refund_currency"),
        "requires_action": cancellation_data.get("requires_action"),
        "raw": cancellation_data,
    }

    if not auto_confirm:
        return result

    confirm_url = DUFFEL_PARAMS.base_url + DUFFEL_PARAMS.commands["confirm_order_cancellation"].format(order_cancellation_id=cancellation_id)
    confirm_resp = None
    try:
        confirm_resp = requests.post(confirm_url, headers=_duffel_headers(token), json={"data": {}}, timeout=30)
        confirm_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_payload: Any = {}
        status_code = None
        if confirm_resp is not None:
            status_code = confirm_resp.status_code
            try:
                error_payload = confirm_resp.json()
            except Exception:
                error_payload = {"text": confirm_resp.text}
        logger.error("Failed to confirm cancellation: %s", e)
        result["confirmation_error"] = {"error": str(e), "status": status_code, "response": error_payload}
        return result

    confirm_data = confirm_resp.json().get("data", {})
    result["confirmed"] = True
    result["refund_amount"] = confirm_data.get("refund_amount", result.get("refund_amount"))
    result["refund_currency"] = confirm_data.get("refund_currency", result.get("refund_currency"))
    result["raw_confirmation"] = confirm_data
    return result

# ------------------------
# Tool-wrapped APIs
# ------------------------

search_flights = search_flights_impl
create_order = create_order_impl
create_payment = create_payment_impl
get_order = get_order_impl
cancel_order = cancel_order_impl
get_offer = get_offer_impl
request_order_change_offers = request_order_change_offers_impl
confirm_order_change = confirm_order_change_impl
