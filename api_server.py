"""
Simple FastAPI wrapper exposing the chat interface for the frontend.

Endpoints:
  POST /chat { "session_id": "abc", "message": "hello" }
Returns:
  { "reply": "<assistant text>" }

Sessions are kept in-memory and keyed by session_id.
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import main as backend  # reuse handle_user_message and globals
from user_store import create_user, authenticate, get_user
from booking_store import list_bookings, cancel_booking_record
from payment_gateway import create_payment_intent, confirm_payment_intent, retrieve_payment_intent
from payment_store import save_payment, get_payment_by_intent_id, get_payment_by_order_id

app = FastAPI(title="Nomada Chat API")

# Allow local dev frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory conversation store keyed by session_id
_sessions: Dict[str, List[Dict[str, str]]] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    name: str | None = None
    email: str | None = None

class BookingsResponse(BaseModel):
    bookings: list

class CancelRequest(BaseModel):
    email: str
    order_id: str

class CreatePaymentIntentRequest(BaseModel):
    amount: str
    currency: str
    offer_id: str
    customer_email: str | None = None

class PaymentIntentResponse(BaseModel):
    success: bool
    client_secret: str | None = None
    payment_intent_id: str | None = None
    error: str | None = None

class ConfirmPaymentRequest(BaseModel):
    payment_intent_id: str

class PaymentDetailsResponse(BaseModel):
    success: bool
    payment: dict | None = None
    error: str | None = None

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Relay chat messages to the existing backend.handle_user_message while
    keeping per-session histories in memory.
    """
    history = _sessions.get(req.session_id, [])
    # Patch backend's conversation_history for this request
    backend.conversation_history[:] = history

    try:
        reply = backend.handle_user_message(req.message)
    except Exception as e:
        reply = f"Backend error: {e}"
    # Persist updated history back into session store
    _sessions[req.session_id] = backend.conversation_history.copy()
    print(history)
    return ChatResponse(reply=reply)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> AuthResponse:
    try:
        existing = get_user(req.email)
        if existing:
            return AuthResponse(success=False, message="Email already registered")
        create_user(req.name, req.email, req.password)
        return AuthResponse(success=True, message="Registered", name=req.name, email=req.email)
    except Exception as e:
        return AuthResponse(success=False, message=f"Registration failed: {e}")


@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    try:
        ok = authenticate(req.email, req.password)
        if not ok:
            return AuthResponse(success=False, message="Invalid credentials")
        user = get_user(req.email) or {}
        return AuthResponse(success=True, message="Logged in", name=user.get("name"), email=user.get("email"))
    except Exception as e:
        return AuthResponse(success=False, message=f"Login failed: {e}")


@app.get("/bookings", response_model=BookingsResponse)
def bookings(email: str) -> BookingsResponse:
    try:
        return BookingsResponse(bookings=list_bookings(email))
    except Exception:
        return BookingsResponse(bookings=[])


@app.post("/bookings/cancel", response_model=AuthResponse)
def cancel_booking(req: CancelRequest) -> AuthResponse:
    try:
        cancel_booking_record(req.email, req.order_id)
        return AuthResponse(success=True, message="Booking marked as cancelled")
    except Exception as e:
        return AuthResponse(success=False, message=f"Cancel failed: {e}")


@app.post("/payments/create-intent", response_model=PaymentIntentResponse)
def create_payment(req: CreatePaymentIntentRequest) -> PaymentIntentResponse:
    """
    Create a Stripe PaymentIntent for collecting payment before booking.
    Frontend will use client_secret to collect card details securely.
    """
    try:
        result = create_payment_intent(
            amount=req.amount,
            currency=req.currency,
            offer_id=req.offer_id,
            customer_email=req.customer_email
        )

        # Save payment record to database
        save_payment(
            stripe_payment_intent_id=result['payment_intent_id'],
            amount=req.amount,
            currency=req.currency,
            status=result['status'],
            offer_id=req.offer_id,
            customer_email=req.customer_email
        )

        return PaymentIntentResponse(
            success=True,
            client_secret=result['client_secret'],
            payment_intent_id=result['payment_intent_id']
        )

    except Exception as e:
        return PaymentIntentResponse(success=False, error=str(e))


@app.post("/payments/confirm", response_model=PaymentDetailsResponse)
def confirm_payment(req: ConfirmPaymentRequest) -> PaymentDetailsResponse:
    """
    Confirm that a payment was successful and retrieve details.
    Should be called after frontend confirms payment with Stripe.
    """
    try:
        payment_details = confirm_payment_intent(req.payment_intent_id)

        # Update payment record with card details
        card_info = payment_details.get('card', {})
        save_payment(
            stripe_payment_intent_id=req.payment_intent_id,
            amount=str(payment_details['amount']),
            currency=payment_details['currency'],
            status='succeeded',
            card_brand=card_info.get('brand'),
            card_last4=card_info.get('last4')
        )

        return PaymentDetailsResponse(success=True, payment=payment_details)

    except Exception as e:
        return PaymentDetailsResponse(success=False, error=str(e))


@app.get("/payments/{payment_intent_id}", response_model=PaymentDetailsResponse)
def get_payment(payment_intent_id: str) -> PaymentDetailsResponse:
    """
    Retrieve payment details from database or Stripe.
    """
    try:
        # Check database first
        db_payment = get_payment_by_intent_id(payment_intent_id)
        if db_payment:
            return PaymentDetailsResponse(success=True, payment=db_payment)

        # Fall back to Stripe
        payment_details = retrieve_payment_intent(payment_intent_id)
        return PaymentDetailsResponse(success=True, payment=payment_details)

    except Exception as e:
        return PaymentDetailsResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
