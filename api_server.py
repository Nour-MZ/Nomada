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

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Relay chat messages to the existing backend.handle_user_message while
    keeping per-session histories in memory.
    """
    history = _sessions.get(req.session_id, [])
    # Patch backend's conversation_history for this request
    backend.conversation_history[:] = history

    reply = backend.handle_user_message(req.message)
    
    # Persist updated history back into session store
    _sessions[req.session_id] = backend.conversation_history.copy()
    print(backend.conversation_history[-1])
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
