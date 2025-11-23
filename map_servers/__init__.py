# map_servers/__init__.py

from .base import ServerParams

from .duffel_server import (
    search_flights,
    create_order,
    create_payment,
    get_order,
    cancel_order,
    get_offer,
    request_order_change_offers,
    confirm_order_change,
)

from .hotelbeds_server import (
    search_hotels,
    book_hotel,
    get_booking,
    cancel_booking,
)

__all__ = [
    "ServerParams",
    "search_flights",
    "create_order",
    "create_payment",
    "get_order",
    "cancel_order",
    "get_offer",
    "request_order_change_offers",
    "confirm_order_change",
    "search_hotels",
    "book_hotel",
    "get_booking",
    "cancel_booking",
]
