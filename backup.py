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
    missing = []
    if not origin:
        missing.append("origin (IATA code)")
    if not destination:
        missing.append("destination (IATA code)")
    if not departure_date:
        missing.append("departure_date (YYYY-MM-DD)")
    if budget is None:
        missing.append("budget")
    if missing:
        return {
            "error": "Missing required fields",
            "missing_fields": missing,
            "prompt": f"Please provide: {', '.join(missing)}. Optional: return_date, passengers, cabin_class, hotel_min_rate/max_rate, hotel_keywords/categories, interests."
        }

    def _parse_date(val: str) -> Optional[date]:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None

    dep = _parse_date(departure_date)
    ret = _parse_date(return_date) if return_date else None
    nights = (ret - dep).days if dep and ret else None

    flights = load_latest_search_offers(db_path="databases/flights.sqlite")
    best_flight = None
    if flights:
        flights_sorted = sorted(flights, key=lambda x: x.get("raw", {}).get("total_amount", float("inf")))
        best_flight = flights_sorted[0].get("raw")

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
