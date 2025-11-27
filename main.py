from __future__ import annotations

import json
import os
from typing import Any, Dict, Callable, List, Optional
from datetime import datetime, date, timedelta
import openai
from agents import function_tool

# Import the Duffel functions (these should already be written and available)
from map_servers.flight_server import (
    search_flights,
    create_order,
    create_payment,
    get_order,
    cancel_order,
    get_offer,
    request_order_change_offers,
    confirm_order_change,
)
from map_servers.hotelbeds_server import (
    search_hotels,
    book_hotel,
    get_booking,
    cancel_booking,
)
from map_servers.hotelbeds_store import load_hotel_search
from map_servers.flight_store import save_flight_choice, load_flight_choices, save_flight_search_results, load_latest_search_offers
from map_servers.utils import send_booking_email
from booking_store import save_booking, cancel_booking_record

# ----------------------------------------------------------------------
# Dedup cache to avoid repeated create_order on the same offer (per process)
_recent_orders: Dict[str, float] = {}

# ----------------------------------------------------------------------
# 1. Configure OpenAI LLM
# ----------------------------------------------------------------------

# OPTION A (recommended): read from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "Please set OPENAI_API_KEY as an environment variable or "
        "hard-code it in agent_app.py before running."
    )

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Create OpenAI client for newer API
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------------------------------------------
# 2. Tool registry: names -> description + Python callables
# ----------------------------------------------------------------------

def _tool_schema() -> Dict[str, Dict[str, Any]]:
    """
    Describe tools in natural language + argument info.
    This is what the LLM sees when deciding which tool to call.
    """
    return {
        "search_flights": {
            "description": "Search for flight offers based on the provided origin, destination, and dates.",
            "args": {
                "slices": "list of { origin: string (IATA Form), destination: string, departure_date: string (YYYY‑MM‑DD) } (required)",
                "passengers": "list of { type: string ('adult'/'child'/'infant') or age: integer } (required)",
                "cabin_class": "string (optional) - 'economy'/'premium_economy'/'business'/'first'",
                "max_connections": "integer (optional) - maximum number of stops per journey",
                "max_offers": "integer (optional)"  
            }
        },
        "generate_passenger_template": {
            "description": "Use whenever a user chooses a flight number after getting the `recent flight offers:` message and only after search_flights have been called. Run before the create_order function",
            "args": {
                "selection": "integer (required) - 1-based index of the flight from the latest search results"
            }
        },
        "create_order": {
            "description": "Create a flight order from a selected offer. Requires passenger identities and contact details.",
            "args": {
                "offer_id": "string (required) - the Duffel offer ID (e.g., 'off_12345').",
                "payment_type": "string (optional) - The payment method to use (default is 'balance').",
                "passengers": "list (required) - A list of passenger details with id, title, gender type: string ('m'/'f'), given_name, family_name, born_on, email, phone_number.",
                "mode": "string (optional) - The order type: 'instant' or 'hold' (default is 'instant').",
                "create_hold": "boolean (optional) - If True, create a hold order without taking payment (default is False).",
            },
        },
        "create_payment": {
            "description": "Create a payment for an existing order. Supports balance payments and experimental card payments (via payment_source). If amount/currency are missing, it will use the order total.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "amount": "string (optional) - amount to pay; defaults to order total.",
                "currency": "string (optional) - currency code; defaults to order currency.",
                "payment_type": "string (optional) - payment method, defaults to 'balance'. Use 'card' when providing payment_source for card payments.",
                "payment_source": "object (optional) - provider-specific fields (e.g., token/payment_method_id) for non-balance payments.",
            },
        },
        "get_order": {
            "description": "Fetch order details including passengers, itinerary, and payments.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...)."
            },
        },
        "get_offer": {
            "description": "Fetch detailed offer of a flight info including segments, baggage, cabin, fare brand, and pricing.",
            "args": {
                "offer_id": "string (required) - Duffel offer ID (off_...)."
            },
        },
        "cancel_order": {
            "description": "Request and (optionally) confirm cancellation of an order. Returns refund info when available.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "auto_confirm": "boolean (optional) - confirm the cancellation immediately, default true.",
            },
        },
        "request_order_change_offers": {
            "description": "Request change offers for an order (e.g., new dates/routes). Returns priced change offers.",
            "args": {
                "order_id": "string (required) - Duffel order ID (ord_...).",
                "slices": "list (optional) - new journey slices {origin, destination, departure_date} to reprice changes.",
                "max_offers": "integer (optional) - max change offers to return (default 5).",
            },
        },
        "confirm_order_change": {
            "description": "Confirm a change offer. If amount/currency are omitted, it will fetch the change offer to fill them.",
            "args": {
                "order_change_offer_id": "string (required) - Duffel order change offer ID.",
                "payment_type": "string (optional) - payment method (default 'balance').",
                "amount": "string (optional) - change total to pay; defaults from change offer.",
                "currency": "string (optional) - currency; defaults from change offer.",
            },
        },
        "search_hotels": {
            "description": "Search hotel availability via Hotelbeds (test environment by default). Use Hotelbeds destination codes (e.g., PMI, BCN, LON).",
            "args": {
                "destination_code": "string (required) - Hotelbeds destination code (e.g., 'PMI').",
                "check_in": "string (required) - check-in date YYYY-MM-DD.",
                "check_out": "string (required) - check-out date YYYY-MM-DD.",
                "rooms": "list (optional) - occupancy details, e.g., [{'adults':2,'children':0}] or with paxes.",
                "limit": "integer (optional) - max hotels to return (default 5).",
                "min_rate": "float (optional) - minimum rate to filter hotels.",
                "max_rate": "float (optional) - maximum rate to filter hotels.",
                "keywords": "list (optional) - keyword codes to filter hotels. you can extract this from prompt example (sea, mountain, city, etc.)",
                "categories": "list (optional) - category codes to filter hotels.",
            },
        },
        "book_hotel": {
            "description": "Create a hotel booking via Hotelbeds. Requires rateKey(s) from a search.",
            "args": {
                "holder": "object (required) - {name, surname} of lead guest.",
                "rooms": "list (required) - [{rateKey, paxes: [{roomId, type:'AD'/'CH', name, surname, age}]}].",
                "client_reference": "string (required) - your booking reference.",
                "remark": "string (optional) - special notes.",
            },
        },
        "get_booking": {
            "description": "Retrieve a hotel booking by reference.",
            "args": {
                "reference": "string (required) - booking reference returned by Hotelbeds.",
            },
        },
        "cancel_booking": {
            "description": "Cancel a hotel booking by reference.",
            "args": {
                "reference": "string (required) - booking reference returned by Hotelbeds.",
            },
        },
        "save_flight_choice": {
            "description": "Persist a selected flight offer to local storage for later recall.",
            "args": {
                "choice": "object (required) - flight choice with fields like offer_id, airline, price, currency, cabin_class, origin, destination, departure_date, return_date, passenger_ids",
                "db_path": "string (optional) - sqlite file path, default flight_choices.sqlite"
            },
        },
        "load_flight_choices": {
            "description": "Retrieve recently saved flight choices.",
            "args": {
                "limit": "integer (optional) - number of rows to return (default 10)",
                "db_path": "string (optional) - sqlite file path, default flight_choices.sqlite"
            },
        },
        "plan_trip_first": {
            "description": "Plan a full travel package with flights, hotels, and activities within a budget.",
            "args": {
                "origin": "string (required) - origin IATA code",
                "destination": "string (required) - destination IATA code",
                "departure_date": "string (required) - YYYY-MM-DD",
                "return_date": "string (optional) - YYYY-MM-DD",
                "budget": "float (required) - total trip budget",
                "passengers": "integer or list (optional) - number of travelers or pax list",
                "cabin_class": "string (optional) - flight cabin class",
                "hotel_min_rate": "float (optional) - min hotel rate",
                "hotel_max_rate": "float (optional) - max hotel rate",
                "hotel_keywords": "list (optional) - hotel keyword codes",
                "hotel_categories": "list (optional) - hotel category codes",
                "interests": "list (optional) - activities interests (e.g., hiking, food)",
            },
        },
        "plan_things_to_do": {
            "description": "Suggest activities/things to do at a destination based on interests.",
            "args": {
                "destination": "string (required) - city or place",
                "interests": "list (optional) - interests such as hiking, food, culture",
                "days": "integer (optional) - length of stay",
                "budget_per_day": "float (optional) - activity budget per day",
            },
        },
        
    }
# Removed duplicate TOOL_FUNCTIONS definition

# ----------------------------------------------------------------------
# 3. Agent logic: decide tool vs direct answer, then explain
# ----------------------------------------------------------------------

# Initialize the conversation memory list
conversation_history = []

def _truncate(text: str, max_chars: int = 4000) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def generate_passenger_template(selection: int, db_path: str = "databases/flights.sqlite") -> Dict[str, Any]:
    """
    Return the raw offer for a selected flight index from the most recent search,
    suitable for prompting the passenger template on the frontend.
    """
    offers = load_latest_search_offers(db_path=db_path)
    if not offers:
        return {"error": "No recent flight search found. Please run a flight search and choose a number."}
    if selection < 1 or selection > len(offers):
        return {
            "error": f"Selection {selection} is out of range. Latest search has {len(offers)} offer(s).",
            "count": len(offers),
        }
    chosen = offers[selection - 1].get("raw") or {}

    # Trim to only the fields needed by the frontend template
    passengers = []
    for pax in chosen.get("passengers", []) or []:
        passengers.append({"id": pax.get("id") or ""})
    if not passengers:
        passengers = [{"id": ""}]

    passenger_template = {
        # Duplicate id for frontend compatibility
        "id": chosen.get("id"),
        "offer_id": chosen.get("id"),
        "passengers": passengers,
        "required_fields": ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number", "id"],
    }

    return {"passenger_template": passenger_template, "selection": selection}


def plan_things_to_do(
    destination: str,
    interests: Optional[List[str]] = None,
    days: Optional[int] = None,
    budget_per_day: Optional[float] = None,
) -> Dict[str, Any]:
    suggestions: List[Dict[str, Any]] = []
    interests = interests or ["food", "culture", "outdoors"]
    base = [
        {"name": "City walking tour", "type": "culture", "cost": "low", "notes": "Explore old town and landmarks"},
        {"name": "Local food crawl", "type": "food", "cost": "medium", "notes": "Sample street food and markets"},
        {"name": "Sunset viewpoint", "type": "outdoors", "cost": "low", "notes": "Easy hike or cable car"},
        {"name": "Museum visit", "type": "culture", "cost": "medium", "notes": "Top-rated museum in the city"},
    ]
    for item in base:
        if any(kw in item["type"] for kw in interests):
            suggestions.append(item)
    return {
        "destination": destination,
        "days": days,
        "budget_per_day": budget_per_day,
        "suggestions": suggestions,
    }


def plan_trip_first(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    budget: Optional[float] = None,
    passengers: Optional[Any] = None,
    cabin_class: str = "economy",
    hotel_min_rate: Optional[float] = None,
    hotel_max_rate: Optional[float] = None,
    hotel_keywords: Optional[List[str]] = None,
    hotel_categories: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    def _unspecified(val: Optional[str]) -> bool:
        if val is None:
            return True
        if isinstance(val, str):
            return val.strip().lower() in {"any", "anywhere", "n/a", "none", ""}
        return False
    print("test")
    missing = []
    if _unspecified(origin):
        missing.append("origin (IATA code)")
    if _unspecified(destination):
        missing.append("destination (IATA code)")
    if _unspecified(departure_date):
        missing.append("departure_date (YYYY-MM-DD)")
    if budget is None:
        missing.append("budget")
    if missing:
        numbered = "\n".join([f"{idx+1}. {field}" for idx, field in enumerate(missing)])
        return {
            "error": "Missing required fields",
            "missing_fields": missing,
            "prompt": "Please provide the following (you can say 'any' if no preference):\n" + numbered + "\nOptional: return_date, passengers, cabin_class, hotel_min_rate/max_rate, hotel_keywords/categories, interests."
        }
    print("test2")
    def _parse_date(val: str) -> Optional[date]:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None

    dep = _parse_date(departure_date)
    ret = _parse_date(return_date) if return_date else None
    nights = (ret - dep).days if dep and ret else None

    # Perform fresh searches to populate DB
    try:
        pax_list = None
        if isinstance(passengers, int):
            pax_list = [{"type": "adult"} for _ in range(max(1, passengers))]
        elif isinstance(passengers, list):
            pax_list = passengers
        else:
            pax_list = [{"type": "adult"}]

        search_flights(
            slices=[{"origin": origin.upper(), "destination": destination.upper(), "departure_date": departure_date}],
            passengers=pax_list,
            cabin_class=cabin_class,
        )
    except Exception as e:
        print(f"plan_trip_first: flight search failed {e}")
        print("Test3")

    

    flights = load_latest_search_offers(db_path="databases/flights.sqlite")
    best_flight = None
    if flights:
        flights_sorted = sorted(flights, key=lambda x: x.get("raw", {}).get("total_amount", float("inf")))
        best_flight = flights_sorted[0].get("raw")
    if not best_flight:
        return {
            "error": "No flights found for the provided criteria. Try different dates or routes.",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
        }
    print("Test4")

    def _arrival_date_from_flight(raw_flight: Dict[str, Any]) -> Optional[str]:
        """Pick the arrival date of the last segment in the first slice, as YYYY-MM-DD."""
        try:
            slices = raw_flight.get("slices") or []
            if not slices:
                return None
            last_seg = (slices[0].get("segments") or [])[-1]
            arriving_at = last_seg.get("arriving_at")
            if not arriving_at:
                return None
            # Normalize ISO strings with trailing Z for fromisoformat
            ts = arriving_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            return dt.date().isoformat()
        except Exception:
            return None

    try:
        # Align hotel check-in with flight arrival date instead of departure date
        flight_arrival_date = _arrival_date_from_flight(best_flight) or departure_date
        check_in = flight_arrival_date
        check_out = return_date or (
            datetime.fromisoformat(check_in).date() + timedelta(days=3)
        ).isoformat()

        hotelresults = search_hotels(
            destination_code=destination.upper(),
            check_in=check_in,
            check_out=check_out,
            # rooms = [{"adults": 2, "children": 0}],
            limit=5,
        )
    except Exception as e:
        print(f"plan_trip_first: hotel search failed {e}")
        
    hotels = []
    try:
        loaded = load_hotel_search(db_path="databases/hotelbeds.sqlite")
        hotels = loaded.get("hotels", []) if isinstance(loaded, dict) else []
    except Exception:
        hotels = []
    best_hotel = None
    if hotels:
        def rate_val(h):
            try:
                return float(h.get("min_rate") or h.get("max_rate") or 0)
            except Exception:
                return float("inf")
        hotels_sorted = sorted(hotels, key=rate_val)
        best_hotel = hotels_sorted[0]
    if not best_hotel:
        return {
            "error": "No hotels found for the provided destination/dates. Try adjusting destination or dates.",
            "destination": destination,
            "check_in": departure_date,
            "check_out": ret.isoformat() if ret else departure_date,
        }

    activities = plan_things_to_do(destination=destination, interests=interests)

    estimate = {}
    if best_flight and best_hotel:
        try:
            flight_cost = float(best_flight.get("total_amount") or best_flight.get("price") or 0)
            hotel_cost = float(best_hotel.get("min_rate") or best_hotel.get("max_rate") or 0)
            total_est = flight_cost + (hotel_cost * nights if nights else hotel_cost)
            estimate = {"total_estimated": total_est, "currency": best_hotel.get("currency") or "USD"}
        except Exception:
            pass

    return {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "budget": budget,
        "passengers": passengers,
        "flight": best_flight,
        "hotel": best_hotel,
        "activities": activities,
        "estimate": estimate,
        "nights": nights,
    }
TOOL_FUNCTIONS = {
    "search_flights": search_flights,
    "generate_passenger_template": generate_passenger_template, 
    "create_order" : create_order,
    "create_payment": create_payment,
    "get_order": get_order,
    "cancel_order": cancel_order,
    "get_offer": get_offer,
    "request_order_change_offers": request_order_change_offers,
    "confirm_order_change": confirm_order_change,
    "search_hotels": search_hotels,
    "book_hotel": book_hotel,
    "get_booking": get_booking,
    "cancel_booking": cancel_booking,
    "save_flight_choice": save_flight_choice,
    "load_flight_choices": load_flight_choices,
    "plan_trip_first": plan_trip_first,  # set after definition
    "plan_things_to_do": plan_things_to_do,  # set after definition
}


def build_system_prompt() -> str:
    tools_desc = _tool_schema()
    tools_text_parts = []
    for name, spec in tools_desc.items():
        tools_text_parts.append(
            f"- {name}:\n"
            f"  description: {spec['description']}\n"
            f"  args: {json.dumps(spec['args'], indent=2)}"
        )
    tools_text = "\n".join(tools_text_parts)

    return (
        "You are a travel assistant that can call a set of tools (Duffel API functions).\n"
        "YOU ONLY ANSWER TRAVEL RELATED QUESTIONS!\n"
        "DONT ANSWER ANYTHING NOT TRAVEL/TOURSIM RELATED!\n"
        "If the user Say plan full trip/jounrye use the plan_trip_first tool\n"
        "If the user uses search_flights tool then provides a flight selection number, you MUST call generate_passenger_template with that number before creating any order.\n"
        "Do not call create_order until you have collected passenger details via the passenger template.\n"
        "Tools available:\n"
        f"{tools_text}\n\n"
        "You MUST decide if you need to call a tool.\n"
        "If you need a tool, respond ONLY with a JSON object of the form:\n"
        '{\n'
        '  "tool": "<tool_name>",\n'
        '  "args": { ... }\n'
        '}\n'
        "where <tool_name> is one of the tools above, and args contains only simple JSON types.\n"
        "If you can answer directly without tools (e.g., conceptual explanation), respond ONLY with:\n"
        '{ "answer": "<your natural language answer>" }\n'
        "Do not add any extra text outside the JSON. The JSON must be the entire response.\n"
        f"today is{datetime.now()}"
    )

def load_prompt_from_file(prompt_key: str, file_path: str = 'prompts.json') -> str:
    try:
        with open(file_path, 'r') as f:
            prompts = json.load(f)
        return prompts.get(prompt_key, "")
    except FileNotFoundError:
        raise Exception(f"Prompt file '{file_path}' not found.")
    except json.JSONDecodeError:
        raise Exception(f"Error decoding JSON from the prompt file.")

def ask_llm_for_tool_or_answer(user_message: str) -> Dict[str, Any]:
    """
    Step 1: Ask the LLM whether to call a tool, and which one.
    
    Returns parsed JSON dict, either:
      { "answer": "..." }
    or
      { "tool": "<name>", "args": { ... } }
    """
    # Add current user message to conversation history
    conversation_history.append({"role": "user", "content": user_message})

    # Build the system prompt to guide the LLM's behavior
    system_prompt = build_system_prompt()

    # Send the full conversation history + system prompt as context
    messages = [{"role": "system", "content": system_prompt}] + conversation_history[-25:]  # Limit context to last few messages

    # Make the API request with conversation history + system prompt
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Use a valid model
        messages=messages,
        max_tokens=3000,
    )

    # Extract the response text
    text = response.choices[0].message.content.strip()

    # Add assistant's response to conversation history
    conversation_history.append({"role": "assistant", "content": text})

    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        # Fallback: wrap whatever the model said as a direct answer
        data = {"answer": text}

    return data

def llm_post_tool_response(
    user_message: str,
    tool_name: str,
    args: Dict[str, Any],
    result: Any,
    prompt_key: str = "explain_decision",
    prompt_file: str = "prompts.json"
) -> str:
    """
    Step 3: After calling the tool, ask the LLM to explain the result.
    """
    prompter = load_prompt_from_file(prompt_key, prompt_file)
    print(user_message, tool_name, args, result )
    if not prompter:
        raise ValueError(f"No prompt found with key '{prompt_key}' in {prompt_file}")
    
    # Pre-process variables
    tool_desc = _tool_schema().get(tool_name, {})
    tool_description = tool_desc.get('description', '') if isinstance(tool_desc, dict) else ''
    
    # ✅ FIX: Actually format the prompt with the variables
    formatted_prompt = prompter.format(
        user_message=user_message,
        tool_name=tool_name,
        tool_description=tool_description,
        formatted_args=_truncate(json.dumps(args, indent=2), max_chars=2000),
        formatted_result=_truncate(json.dumps(result, indent=2), max_chars=4000)
    )
    
    messages = [{"role": "system", "content": "You are a helpful flight booking assistant."}] + conversation_history[-25:] + [
        {"role": "user", "content": formatted_prompt},  # ✅ Use formatted_prompt, not raw prompter
    ]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=3000,
    )

    text = response.choices[0].message.content.strip()
    # ❌ REMOVE this print to avoid duplicate output
    # print ("this is the text habibi", text)
    conversation_history.append({"role": "assistant", "content": text})
    return text

def handle_user_message(user_message: str) -> str:
    """
    Full agent flow for one user message:
    1. Ask LLM whether to use a tool or answer directly.
    2. If tool: run the Python function, then ask LLM to explain result.
    """
    # Fast-path: if frontend sends structured booking payload, bypass LLM and create order directly
    try:
        data = json.loads(user_message)
        if isinstance(data, dict) and data.get("offer_id") and isinstance(data.get("passengers"), list):
            order_payload = {
                "offer_id": data["offer_id"],
                "passengers": [p for p in data["passengers"] if isinstance(p, dict)],
                "payment_type": data.get("payment_type", "balance"),
                "mode": data.get("mode", "instant"),
                "create_hold": data.get("create_hold", False),
            }
            # Dedup guard: avoid rebooking same offer id immediately
            from time import time
            now = time()
            last = _recent_orders.get(order_payload["offer_id"])
            if last and (now - last) < 120:
                return f"Order for offer {order_payload['offer_id']} was already submitted recently. Please search again to book a new offer."
            try:
                # Record user payload in history for context
                conversation_history.append({"role": "user", "content": json.dumps(order_payload)})
                result = create_order(**order_payload)
                _recent_orders[order_payload["offer_id"]] = now
                user_email = data.get("user_email") or data.get("email")
                if user_email:
                    ref = result.get("order_id") or result.get("booking_reference") or data.get("offer_id")
                    title = f"Flight booking {ref}"
                    print("the title", ref)
                    # save_booking(user_email, "flight", ref=ref, title=title, details=result)
                send_booking_email( result)    
                print(result)
                conversation_history.append({"role": "assistant", "content": json.dumps(result)})
                # Fast-path handled; skip downstream tool invocation by returning early
                return llm_post_tool_response(user_message, "create_order", order_payload, result)
            except Exception as e:
                return llm_post_tool_response(user_message, "create_order", order_payload, e)
        if isinstance(data, dict) and data.get("order_id") and data.get("cancel_booking"):
            conversation_history.append({"role": "user", "content": json.dumps(data)})
            result = cancel_order(data["order_id"], auto_confirm=True)
            user_email = data.get("user_email") or data.get("email")
            if user_email:
                try:
                    cancel_booking_record(user_email, data["order_id"],db_path="databases/bookings.sqlite")
                except Exception as e:
                    print(f"Failed to mark booking cancelled: {e}")
            formatted_result = json.dumps(result, indent=2)
            if len(formatted_result) > 500:
                formatted_result = formatted_result[:500] + "\n... [truncated]"
            conversation_history.append({"role": "assistant", "content": formatted_result})
            return llm_post_tool_response(user_message, "cancel_order", {"order_id": data["order_id"]}, result)
    except Exception:
        # Not a structured booking payload; continue with normal flow
        pass

    decision = ask_llm_for_tool_or_answer(user_message)
   
    # Direct answer path
    if "answer" in decision and "tool" not in decision:
        return decision["answer"]

    # Tool path
    tool_name = decision.get("tool")
    args = decision.get("args", {}) or {}
    print(decision)
    if tool_name not in TOOL_FUNCTIONS:
        return f"I tried to call an unknown tool '{tool_name}'. Please refine your request."

    tool_fn = TOOL_FUNCTIONS[tool_name]

    try:
        result = tool_fn(**args)
        formatted_result = json.dumps(result, indent=2)
        # Keep tool result in memory, but cap size to avoid blowing context window
        max_chars = 500
        if len(formatted_result) > max_chars:
            formatted_result = formatted_result[:max_chars] + "\n... [truncated]"
        conversation_history.append({"role": "assistant", "content": formatted_result})
        print(result)
        if tool_name == "search_hotels":
            # Return hotel results as JSON for frontend templates; fall back to LLM on errors
            if isinstance(result, dict) and result.get("error"):
                return llm_post_tool_response(user_message, tool_name, args, result)
            try:
                loaded = load_hotel_search(db_path="databases/hotelbeds.sqlite")
                hotels = loaded.get("hotels", []) if isinstance(loaded, dict) else []
            except Exception:
                hotels = result.get("results", []) if isinstance(result, dict) else []
            booking_hint = (
                "To book a hotel, provide holder {name, surname}, rooms [{rateKey, paxes:[{roomId, type:'AD'/'CH', name, surname, age}]}], "
                "client_reference, and optional remark."
            )
            conversation_history.append({"role": "assistant", "content": booking_hint})
            print(hotels)
            return json.dumps({"hotels": hotels}, indent=2)
        if tool_name == "search_flights":
            # Return raw flight offer JSON so the caller (e.g., frontend) can display all offers,
            # including those saved to the database, without truncation.
            print("search flights was used")
            try:
                if isinstance(result, dict) and result.get("error"):
                    return llm_post_tool_response(user_message, tool_name, args, result)
                offers = load_latest_search_offers(db_path="databases/flights.sqlite")
                if offers:
                    lines = []
                    for idx, offer in enumerate(offers, start=1):
                        pax_str = ", ".join(offer.get("passenger_ids") or []) or "n/a"
                        lines.append(f"{idx}. offer_id={offer.get('offer_id')} passengers=[{pax_str}]")
                    summary = "Recent flight offers:\n" + "\n".join(lines)
                    print(summary)
                    conversation_history.append({"role": "assistant", "content": summary})
                return json.dumps(result, indent=2)
            except Exception:
                return llm_post_tool_response(user_message, tool_name, args, result)
        if tool_name =="generate_passenger_template":
            # Return the passenger template directly to the user
            passenger_template = result.get("passenger_template")
            if passenger_template:
                return json.dumps(passenger_template, indent=2)
            return result.get("error", "No passenger template available. Please rerun flight search and select a valid number.")
        if tool_name == "plan_trip_first":
            if isinstance(result, dict) and result.get("missing_fields"):
                return llm_post_tool_response(user_message, tool_name, args, result, prompt_key="ask_for_missing_fields")
            if isinstance(result, dict) and result.get("error"):
                return llm_post_tool_response(user_message, tool_name, args, result, prompt_key="explain_decision")
            try:
                return json.dumps(result, indent=2)
            except Exception:
                return str(result)
        # if tool_name == "plan_trip_first":
        #     if isinstance(result, dict) and result.get("missing_fields"):
        #         return llm_post_tool_response(user_message, tool_name, args, result)
        #     else:
        #         try:
        #             return json.dumps(result, indent=2)
        #         except Exception:
        #             return str(result)
    except TypeError as e:
        return f"There was an error calling tool '{tool_name}' with arguments {args}: {e}"
    except Exception as e:
        return f"Tool '{tool_name}' failed with an exception: {e}"
    return llm_post_tool_response(user_message, tool_name, args, result)
# ----------------------------------------------------------------------
# 4. Simple REPL
# ----------------------------------------------------------------------

def main() -> None:
    print("Flight Assistant (OpenAI model: gpt-3.5-turbo)")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye.")
            return

        if not user_input:
            continue

        answer = handle_user_message(user_input)
        print("\nAssistant:\n")
        print(answer)
        
        print("\n---\n")


if __name__ == "__main__":
    main()
