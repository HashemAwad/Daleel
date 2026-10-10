"""Twilio WhatsApp webhook. Owner: C.

Flow for one inbound message:
    verify Twilio signature -> normalise to Inquiry (salted-hash user_ref)
    -> voice note? download with auth + transcribe -> pipeline.handle
    -> reply as TwiML

Privacy rules this module must never break:
  * the raw phone number is hashed at the edge (identity.user_ref) and the raw
    value never goes into an Inquiry, a log line, or an error message;
  * `ProfileName` (the sender's WhatsApp display name) is ignored entirely;
  * message text and audio bytes are never logged — only lengths and outcomes.

Replies are TwiML, so the sandbox needs no outbound credentials: Twilio posts
to us and sends whatever we return.

Twilio drops a webhook that has not answered in about 15 seconds, and the user
then gets nothing. A voice note (download + Whisper + the model) can take longer,
so the turn runs in a worker thread with a budget (WEBHOOK_BUDGET_SECONDS,
default 12). Past it we answer "still working" at once and send the real reply
through Twilio's REST API when it is ready; without REST credentials we say so
and ask for a shorter note or a typed question.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Optional
from urllib.parse import parse_qsl

import httpx
from fastapi import APIRouter, Request, Response

from core import pipeline
from shared.config import settings
from shared.contracts import Answer, Inquiry

from channels import render
from channels.identity import user_ref
from channels.settings_extra import channel_settings

log = logging.getLogger("daleel.channels.whatsapp")

router = APIRouter(tags=["whatsapp"])

WEBHOOK_PATH = "/webhook/whatsapp"

# WhatsApp voice notes are OGG/Opus and small; cap the download so a bad or
# hostile media URL can't exhaust memory.
MAX_AUDIO_BYTES = 16 * 1024 * 1024

REPLY_BUDGET_SECONDS = float(os.getenv("WEBHOOK_BUDGET_SECONDS", "12"))
STILL_WORKING = ("⏳ لحظة، عم نحضّر الجواب وبيوصلك بعد شوي.\n"
                 "One moment, your answer is on its way.")
TOO_SLOW = ("عذراً، أخذ الجواب وقتاً أطول من اللازم. جرّب رسالة صوتية أقصر أو اكتب سؤالك، أو اتصل على 1787.\n"
            "Sorry, that took too long. Please send a shorter voice note or type your question, or call 1787.")
BROKEN = ("عذراً، صار في خطأ. جرّب مرة تانية أو اتصل على 1787.\n"
          "Sorry, something went wrong. Please try again or call 1787.")

try:  # twilio is in requirements, but a broken import must not take the app down
    from twilio.request_validator import RequestValidator
    from twilio.twiml.messaging_response import MessagingResponse

    TWILIO_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when twilio is missing
    RequestValidator = None  # type: ignore[assignment]
    MessagingResponse = None  # type: ignore[assignment]
    TWILIO_AVAILABLE = False


# ---- signature verification ------------------------------------------------
def webhook_url(request: Request) -> str:
    """The URL Twilio signed.

    Twilio signs the exact URL configured in the console. Behind ngrok or a
    proxy the request we see is often http://internal-host/..., which would
    fail validation, so PUBLIC_BASE_URL wins when it is set.
    """
    base = settings.public_base_url.strip().rstrip("/")
    if base:
        return f"{base}{request.url.path}"
    return str(request.url)


def signature_ok(request: Request, form: dict[str, str]) -> bool:
    """True when the request carries a valid Twilio signature.

    No auth token configured => we cannot verify. We allow the request through
    for local development but log a warning, unless REQUIRE_TWILIO_SIGNATURE is
    set, which makes an unverifiable request fail closed (use that in deploy).
    """
    token = settings.twilio_auth_token.strip()
    if not token or not TWILIO_AVAILABLE:
        if channel_settings.require_twilio_signature:
            log.error("rejecting webhook: signature required but no TWILIO_AUTH_TOKEN")
            return False
        log.warning("TWILIO_AUTH_TOKEN unset — webhook is UNVERIFIED (dev mode only)")
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    return RequestValidator(token).validate(webhook_url(request), form, signature)


# ---- voice notes (C3) ------------------------------------------------------
def _media_auth(form: dict[str, str]) -> Optional[tuple[str, str]]:
    """Basic-auth pair for Twilio media. The AccountSid arrives in the webhook
    payload; the token comes from our env. Both are needed when the account has
    'require HTTP auth for media' enabled."""
    account_sid = form.get("AccountSid", "") or channel_settings.twilio_account_sid
    token = settings.twilio_auth_token.strip()
    if account_sid and token:
        return (account_sid, token)
    return None


def fetch_media(url: str, form: dict[str, str]) -> bytes:
    """Download media from Twilio, authenticated, size-capped."""
    with httpx.stream(
        "GET", url, auth=_media_auth(form), timeout=20, follow_redirects=True
    ) as resp:
        resp.raise_for_status()
        chunks, total = [], 0
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                raise ValueError("media exceeds size cap")
            chunks.append(chunk)
    return b"".join(chunks)


def transcribe_voice_note(url: str, mime: str, form: dict[str, str]) -> tuple[str, Optional[str]]:
    """Download + transcribe a voice note here in the channel.

    We pre-transcribe instead of handing core an `audio_url` because Twilio
    media can require auth that core has no credentials for (core's own
    docstring says channels may do this). Returns ("", None) on failure so the
    pipeline produces its "couldn't read that" reply.
    """
    from core import providers  # late import: picks up B's real transcriber

    try:
        audio = fetch_media(url, form)
    except Exception as exc:
        log.warning("voice note download failed: %s", type(exc).__name__)
        return ("", None)

    try:
        text, lang = providers.transcriber.transcribe(audio, mime or "audio/ogg")
    except Exception as exc:
        log.warning("transcription failed: %s", type(exc).__name__)
        return ("", None)

    # length only — never the transcript itself
    log.info("voice note transcribed: %d bytes -> %d chars", len(audio), len(text or ""))
    return (text or "", lang)


def _first_media(form: dict[str, str]) -> tuple[Optional[str], str]:
    """(url, mime) of the first attachment, if any."""
    try:
        count = int(form.get("NumMedia", "0") or 0)
    except ValueError:
        count = 0
    if count <= 0:
        return (None, "")
    return (form.get("MediaUrl0"), form.get("MediaContentType0", ""))


# ---- the webhook -----------------------------------------------------------
VALID_LANGS = {"ar", "arabizi", "fr", "en"}


def _safe_lang(lang: Optional[str]) -> Optional[str]:
    """Drop anything outside the Lang literal. A transcriber that reports
    'arabic' or 'ar-LB' must not turn into a 500 on the webhook."""
    return lang if lang in VALID_LANGS else None


def _coords(form: dict[str, str]) -> tuple[Optional[float], Optional[float]]:
    """A shared WhatsApp location pin arrives as Latitude/Longitude form fields."""
    try:
        return float(form["Latitude"]), float(form["Longitude"])
    except (KeyError, ValueError, TypeError):
        return None, None


def build_inquiry(form: dict[str, str]) -> Inquiry:
    """Normalise a Twilio form payload into an Inquiry. Never returns raw PII."""
    sender = form.get("From", "")  # e.g. "whatsapp:+9617xxxxxx" — hashed below, never stored
    text = (form.get("Body", "") or "").strip()
    lang: Optional[str] = None

    media_url, mime = _first_media(form)
    if media_url and not text:
        if mime.startswith("audio"):
            text, lang = transcribe_voice_note(media_url, mime, form)
        else:
            log.info("unsupported media type received: %s", mime or "unknown")

    lat, lon = _coords(form)
    # A bare location pin (no text) means "what's near me" — default to pharmacy
    # so the distance search can run; conversation memory handles the richer case.
    if lat is not None and not text:
        text = "nearest pharmacy"

    return Inquiry(
        id=form.get("MessageSid", "") or "wa-msg",
        channel="whatsapp",
        text=text,
        lang=_safe_lang(lang),  # type: ignore[arg-type]
        user_ref=user_ref(sender, prefix="wa"),
        lat=lat, lon=lon,
    )


def twiml(messages: list[str]) -> Response:
    """Wrap reply parts in TwiML. Twilio sends one WhatsApp message per part."""
    if TWILIO_AVAILABLE:
        resp = MessagingResponse()
        for part in messages:
            resp.message(part)
        body = str(resp)
    else:  # pragma: no cover - fallback when twilio isn't importable
        joined = "".join(f"<Message>{render.xml_escape(p)}</Message>" for p in messages)
        body = f'<?xml version="1.0" encoding="UTF-8"?><Response>{joined}</Response>'
    return Response(content=body, media_type="application/xml")


async def parse_form(request: Request) -> dict[str, str]:
    """Twilio always posts application/x-www-form-urlencoded, so we decode it
    ourselves — that keeps python-multipart out of requirements and keeps the
    exact key/value pairs the signature was computed over."""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/x-www-form-urlencoded"):
        raw = (await request.body()).decode("utf-8", "replace")
        return dict(parse_qsl(raw, keep_blank_values=True))
    try:  # defensive: a proxy that re-encodes as multipart
        return {k: str(v) for k, v in (await request.form()).items()}
    except Exception:
        return {}


def _turn(form: dict[str, str]) -> list[str]:
    """One whole turn (download, transcribe, pipeline) -> reply parts. Never raises."""
    try:
        answer: Answer = pipeline.handle(build_inquiry(form))
    except Exception as exc:
        log.error("whatsapp turn failed: %s", type(exc).__name__)
        return [BROKEN]
    # metadata only: no text, no number, no transcript
    log.info(
        "whatsapp turn: tool=%s outcome=%s grounded=%s chars=%d",
        answer.tool, answer.outcome, answer.grounded, len(answer.text or ""),
    )
    return render.for_whatsapp(answer)


def _can_send_later(form: dict[str, str]) -> bool:
    return bool(TWILIO_AVAILABLE and _media_auth(form) and form.get("From") and form.get("To"))


def _send_later(form: dict[str, str], parts: list[str]) -> None:
    """Send a reply that missed the webhook budget, through Twilio's REST API."""
    try:
        from twilio.rest import Client

        client = Client(*_media_auth(form))
        for part in parts:
            client.messages.create(from_=form["To"], to=form["From"], body=part)
        log.info("late reply sent: parts=%d", len(parts))
    except Exception as exc:  # the message can echo the number: log the type only
        log.error("late reply NOT sent: %s", type(exc).__name__)


@router.post(WEBHOOK_PATH)
async def whatsapp_webhook(request: Request) -> Response:
    form = await parse_form(request)

    if not signature_ok(request, form):
        log.warning("rejected webhook with bad/missing Twilio signature")
        return Response(status_code=403, content="invalid signature")

    lock, state = threading.Lock(), {"late": False, "parts": None}

    def work() -> None:
        parts = _turn(form)
        with lock:
            state["parts"], late = parts, state["late"]
        if late:
            _send_later(form, parts)

    # in a thread: Whisper and the model block, and the event loop must keep serving
    task = asyncio.get_running_loop().run_in_executor(None, work)
    try:
        await asyncio.wait_for(asyncio.shield(task), REPLY_BUDGET_SECONDS)
    except asyncio.TimeoutError:
        with lock:  # either the worker sees `late` and sends, or we already have its parts
            can_follow_up = _can_send_later(form)
            state["late"] = can_follow_up
            done = state["parts"]
        if done is None:
            log.warning("webhook budget exceeded: follow_up=%s", can_follow_up)
            return twiml([STILL_WORKING if can_follow_up else TOO_SLOW])
    return twiml(state["parts"] or [BROKEN])
