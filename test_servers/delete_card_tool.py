import os
from typing import Any, Dict, Optional


def _load_env_upwards() -> None:
    def _find_env() -> Optional[str]:
        import os as _os
        cwd = _os.getcwd()
        prev = None
        while cwd and cwd != prev:
            p = _os.path.join(cwd, ".env")
            if _os.path.exists(p):
                return p
            prev, cwd = cwd, _os.path.dirname(cwd)
        here = _os.path.dirname(_os.path.abspath(__file__))
        prev = None
        while here and here != prev:
            p = _os.path.join(here, ".env")
            if _os.path.exists(p):
                return p
            prev, here = here, _os.path.dirname(here)
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
    "name": "delete_card",
    "description": "Delete a Duffel card record by id (api.duffel.cards).",
    "parameters": {
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "Card id (tcd_...)"},
        },
        "required": ["card_id"],
    },
}


def _env_token() -> Optional[str]:
    import os as _os
    return (
        _os.getenv("DUFFEL_API_TOKEN")
        or _os.getenv("DUFFEL_ACCESS_TOKEN")
        or _os.getenv("API_TOKEN")
    )


def _env_version() -> str:
    import os as _os
    return _os.getenv("DUFFEL_VERSION") or "v2"


def _env_cards_base_url() -> str:
    import os as _os
    return _os.getenv("DUFFEL_CARDS_BASE_URL") or "https://api.duffel.cards"


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import requests  # type: ignore
    except Exception:
        return {"error": "requests not installed. Run: pip install requests"}

    token = _env_token()
    if not token:
        return {"error": "Duffel token missing. Set DUFFEL_API_TOKEN or DUFFEL_ACCESS_TOKEN."}

    card_id = (args.get("card_id") or "").strip()
    if not card_id:
        return {"error": "card_id is required"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": _env_version(),
        "Accept": "application/json",
    }

    try:
        resp = requests.delete(f"{_env_cards_base_url()}/payments/cards/{card_id}", headers=headers, timeout=45)
    except Exception as e:
        return {"error": f"Delete card request failed: {str(e)}"}

    if resp.status_code in (200, 204):
        return {"deleted": True, "card_id": card_id}

    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text}
    return {"error": "Delete card failed", "status": resp.status_code, "response": body}


__all__ = ["TOOL", "run"]

