"""Web channel endpoints + static pages. Owner: C.

`POST /chat` itself lives in core (A owns it). This module adds only what the
widget and the dashboard need around it:

    GET /api/session        mint an opaque session id for a new browser
    GET /api/hotlines       the hotline list, so numbers aren't hardcoded in HTML
    GET /health/channels    demo-time diagnostics (what's wired, what isn't);
                            also the deploy's stub guard — see A20 note below
    GET /dashboard, /join   serve the other two pages in /web
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from shared.config import settings

from channels import identity
from channels.settings_extra import channel_settings

router = APIRouter(tags=["web"])

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@router.get("/api/session")
def session() -> dict:
    """A fresh pseudonymous ref for a browser with no stored session."""
    return {"user_ref": identity.new_web_session()}


@router.get("/api/hotlines")
def hotlines() -> dict:
    from core import providers  # late import: keeps module import cheap

    return {"hotlines": [h.model_dump() for h in providers.HOTLINES]}


@router.get("/health/channels")
def channel_health() -> JSONResponse:
    """Is each channel actually wired? Read on stage to see what is live.

    No page fetches this — the widget has no status dot. The consumers are
    `tests/test_channels.py` and `infra/vm_setup.sh`, which greps the response
    for `"Stub` and fails the deploy when a provider silently fell back to a
    fake one (open item A19).

    That grep is why the `providers` block is still public, which open item A20
    wants closed along with `/docs` and `/openapi.json`. Narrowing it needs the
    matching change in `vm_setup.sh` (D) in the same breath, or the deploy stops
    catching stubs and nobody notices. Behind the server's reverse proxy every
    request arrives from 127.0.0.1, so a loopback check would not gate anything
    — it needs a token.
    """
    from core import providers

    whatsapp_ready = bool(settings.twilio_auth_token and settings.public_base_url)
    body = {
        "ok": True,
        "web": True,
        "whatsapp": {
            "configured": whatsapp_ready,
            "has_auth_token": bool(settings.twilio_auth_token),
            "has_public_url": bool(settings.public_base_url),
            "from_number": settings.twilio_whatsapp_from or None,
            "signature_enforced": channel_settings.require_twilio_signature,
        },
        "whatsapp_meta": {
            # Twilio's trial blocks inbound webhooks; Meta's test number is the
            # fallback provider. Either one being ready is enough to demo.
            "configured": channel_settings.meta_configured,
            "has_access_token": bool(channel_settings.meta_access_token),
            "has_phone_number_id": bool(channel_settings.meta_phone_number_id),
            "has_app_secret": bool(channel_settings.meta_app_secret),
            "verify_token_set": bool(channel_settings.meta_verify_token),
            "signature_enforced": channel_settings.require_meta_signature,
        },
        "privacy": {
            # loud flag: a placeholder salt means user_refs are guessable
            "salt_configured": not identity.salt_is_weak(),
        },
        "providers": {
            "llm": type(providers.llm).__name__,
            "transcriber": type(providers.transcriber).__name__,
            "procedures": type(providers.procedures).__name__,
            "directory": type(providers.directory).__name__,
            "medicine": type(providers.medicine).__name__,
        },
    }
    return JSONResponse(body)


@router.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "dashboard.html")


@router.get("/join", include_in_schema=False)
def join() -> FileResponse:
    return FileResponse(WEB_DIR / "join.html")
