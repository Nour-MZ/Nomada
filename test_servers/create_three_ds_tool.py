import os
import json
from typing import Any, Dict, Optional


def _load_env_upwards() -> None:
    def _find_env() -> Optional[str]:
        cwd = os.getcwd()
        prev = None
        while cwd and cwd != prev:
            p = os.path.join(cwd, ".env")
            if os.path.exists(p):
                return p
            prev, cwd = cwd, os.path.dirname(cwd)
        here = os.path.dirname(os.path.abspath(__file__))
        prev = None
        while here and here != prev:
            p = os.path.join(here, ".env")
            if os.path.exists(p):
                return p
            prev, here = here, os.path.dirname(here)
        return None

    path = _find_env()
    if not path:
        return
    try:  # pragma: no cover
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(path, override=False)
    except Exception:
        pass


_load_env_upwards()


TOOL: Dict[str, Any] = {
    "name": "create_three_d_secure_session",
    "description": "Create a 3-D Secure session for a Duffel card to authenticate a card payment.",
    "parameters": {
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "Card id (tcd_...)"},
            "amount": {"type": "string", "description": "Payment amount to authenticate (e.g., '30.20')"},
            "currency": {"type": "string", "description": "ISO 4217 currency (e.g., 'GBP')"},
            "return_url": {"type": "string", "description": "URL to return to after 3DS challenge"},
        },
        "required": ["card_id", "amount", "currency", "return_url"],
    },
}


def _env_token() -> Optional[str]:
    return (
        os.getenv("DUFFEL_API_TOKEN")
        or os.getenv("DUFFEL_ACCESS_TOKEN")
        or os.getenv("API_TOKEN")
    )


def _env_version() -> str:
    return os.getenv("DUFFEL_VERSION") or "v2"


def _env_base_url() -> str:
    return os.getenv("DUFFEL_BASE_URL") or "https://api.duffel.com"


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import requests  # type: ignore
    except Exception:
        return {"error": "requests not installed. Run: pip install requests"}

    token = _env_token()
    if not token:
        return {"error": "Duffel token missing. Set DUFFEL_API_TOKEN or DUFFEL_ACCESS_TOKEN."}

    card_id = (args.get("card_id") or "").strip()
    amount = (args.get("amount") or "").strip()
    currency = (args.get("currency") or "").strip().upper()
    return_url = (args.get("return_url") or "").strip()
    if not all([card_id, amount, currency, return_url]):
        return {"error": "card_id, amount, currency, and return_url are required"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": _env_version(),
        "Content-Type": "application/json",
    }

    payload = {
        "data": {
            "card_id": card_id,
            "amount": amount,
            "currency": currency,
            "return_url": return_url,
        }
    }

    # Note: Endpoint path based on Duffel payments docs. Adjust if your account/docs specify a different path.
    url = f"{_env_base_url()}/payments/three_d_secure/sessions"
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return {"error": f"Create 3DS session request failed: {str(e)}"}

    status = resp.status_code
    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text}

    if status in (200, 201):
        d = body.get("data") or {}
        # Common fields: id (3ds_...), status, redirect_url, created_at
        return {
            "three_d_secure_session_id": d.get("id"),
            "status": d.get("status"),
            "redirect_url": d.get("redirect_url"),
            "created_at": d.get("created_at"),
            "raw_session": d,
        }

    return {
        "error": "Create 3DS session failed",
        "status": status,
        "response": body,
        "request": payload,
    }


__all__ = ["TOOL", "run"]

