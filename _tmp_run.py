import json, traceback
from map_servers.duffel_server import create_order_impl, create_payment_impl

offer_id = "off_0000B0WBG5X7i1tiBk3r6g"
passengers = [{
    "title": "Mr",
    "gender": "m",
    "given_name": "Nouredine",
    "family_name": "Mezher",
    "born_on": "2002-02-11",
    "email": "nourmezher5@gmail.com",
    "phone_number": "+96178887063",
}]

try:
    order = create_order_impl(offer_id=offer_id, passengers=passengers, payment_type="balance", mode="instant", create_hold=False)
    print("ORDER_RESULT", json.dumps(order, indent=2))
except Exception:
    traceback.print_exc()
    raise

try:
    if isinstance(order, dict) and not order.get("error"):
        order_id = order.get("order_id")
        pay = create_payment_impl(order_id=order_id, payment_type="balance")
        print("PAYMENT_RESULT", json.dumps(pay, indent=2))
    else:
        print("Skipping payment due to order error")
except Exception:
    traceback.print_exc()
    raise
