"""WhatsApp join link + QR code. Owner: C.

A judge should be able to scan one code and be chatting with Daleel. The Twilio
sandbox needs a pairing message first ("join <code>"), so the QR encodes a
wa.me deep link that pre-fills exactly that text.

QR rendering uses segno (pure Python, BSD-3). If it isn't installed the
endpoint returns 501 and /join falls back to showing the link — the demo never
hard-depends on it.
"""
from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from shared.config import settings

from channels.settings_extra import channel_settings

router = APIRouter(tags=["join"])

MAX_QR_CHARS = 512


def sandbox_number() -> str:
    """Digits of the Twilio WhatsApp sender, e.g. '14155238886'."""
    raw = (settings.twilio_whatsapp_from or "").replace("whatsapp:", "")
    return "".join(ch for ch in raw if ch.isdigit())


def join_link() -> str:
    """wa.me deep link that pre-fills the sandbox join message."""
    number = sandbox_number()
    if not number:
        return ""
    code = channel_settings.sandbox_join_code
    if code:
        text = code if code.lower().startswith("join") else f"join {code}"
        return f"https://wa.me/{number}?text={quote(text)}"
    return f"https://wa.me/{number}"


@router.get("/api/whatsapp-info")
def whatsapp_info() -> dict:
    """Everything /join needs to render itself."""
    number = sandbox_number()
    code = channel_settings.sandbox_join_code
    return {
        "configured": bool(number),
        "number": f"+{number}" if number else None,
        "join_code": code or None,
        "join_message": (f"join {code}" if code and not code.lower().startswith("join") else code) or None,
        "deep_link": join_link() or None,
        "qr_available": _segno() is not None,
    }


def _segno():
    try:
        import segno

        return segno
    except Exception:
        return None


@router.get("/qr.svg", include_in_schema=False)
def qr_svg(text: str | None = None, scale: int = 6) -> Response:
    """QR for `text`, or for the sandbox join link by default."""
    segno = _segno()
    if segno is None:
        return JSONResponse(
            {"error": "QR rendering unavailable: pip install segno"}, status_code=501
        )

    payload = (text or join_link()).strip()
    if not payload:
        return JSONResponse(
            {"error": "no join link yet: set TWILIO_WHATSAPP_FROM in .env"},
            status_code=503,
        )

    buf = io.BytesIO()  # segno's svg writer emits bytes
    segno.make(payload[:MAX_QR_CHARS], error="m").save(
        buf, kind="svg", scale=max(1, min(scale, 20)), border=2, dark="#0F5C4A"
    )
    return Response(
        content=buf.getvalue().decode("utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )
