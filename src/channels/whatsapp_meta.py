"""Meta WhatsApp Cloud API webhook. Owner: C.

Second WhatsApp provider, alongside `whatsapp.py` (Twilio). Twilio's trial
account blocks inbound webhooks outright — the console exposes no callback
field and the Senders API answers `20003 not available on a Trial account` —
so Meta's free test number is how we get a live WhatsApp demo. Both handlers
are mounted; whichever is configured is the one that receives traffic.

Flow for one inbound message:
    verify X-Hub-Signature-256 -> normalise to Inquiry (salted-hash user_ref)
    -> voice note? resolve media id, download, transcribe -> pipeline.handle
    -> POST the reply back to the Graph API

Differences from Twilio that shape this module:
  * the payload is JSON, deeply nested, and batched (entry[] > changes[] >
    value.messages[]) — one POST can carry several messages;
  * delivery receipts arrive on the same endpoint as `value.statuses`, and
    must be ignored rather than answered;
  * replies are a separate outbound POST, not the response body, so sending
    needs a token and can fail independently of receiving;
  * Meta retries any non-200, so we answer 200 for anything we understood and
    reserve non-200 for "this was not a request we accept".

Privacy rules this module must never break (same as the Twilio handler):
  * the raw phone number is hashed at the edge (identity.user_ref) and never
    reaches an Inquiry, a log line, or an error message;
  * `contacts[].profile.name` (the sender's WhatsApp display name) is ignored;
  * message text and audio bytes are never logged — only lengths and outcomes.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from core import pipeline
from shared.contracts import Answer, Inquiry

from channels import render
from channels.identity import user_ref
from channels.settings_extra import channel_settings

log = logging.getLogger("daleel.channels.whatsapp_meta")

router = APIRouter(tags=["whatsapp-meta"])

WEBHOOK_PATH = "/webhook/meta"

# Voice notes are OGG/Opus and small; cap the download so a bad or hostile
# media URL can't exhaust memory. Same cap as the Twilio path.
MAX_AUDIO_BYTES = 16 * 1024 * 1024

GRAPH = "https://graph.facebook.com"

VALID_LANGS = {"ar", "arabizi", "fr", "en"}


def _graph(path: str) -> str:
    return f"{GRAPH}/{channel_settings.meta_graph_version}/{path}"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {channel_settings.meta_access_token}"}


# ---- signature verification ------------------------------------------------
def signature_ok(raw_body: bytes, header: str) -> bool:
    """True when the body carries a valid X-Hub-Signature-256.

    Meta signs the *raw* request bytes with the app secret, so this must run
    before any JSON parsing or re-encoding.

    No app secret configured => we cannot verify. We allow the request through
    for local development but log a warning, unless REQUIRE_META_SIGNATURE is
    set, which makes an unverifiable request fail closed (use that in deploy).
    """
    secret = channel_settings.meta_app_secret
    if not secret:
        if channel_settings.require_meta_signature:
            log.error("rejecting webhook: signature required but no WHATSAPP_APP_SECRET")
            return False
        log.warning("WHATSAPP_APP_SECRET unset — webhook is UNVERIFIED (dev mode only)")
        return True

    if not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256=") :])


# ---- verification handshake ------------------------------------------------
@router.get(WEBHOOK_PATH, include_in_schema=False)
def verify(request: Request) -> Response:
    """Meta's subscription handshake: echo hub.challenge when the token matches.

    Returning the challenge as plain text is required — a JSON-wrapped body is
    rejected and the webhook stays unverified.
    """
    params = request.query_params
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    expected = channel_settings.meta_verify_token
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        log.info("meta webhook verification handshake succeeded")
        return PlainTextResponse(challenge)

    log.warning("meta webhook verification failed (mode=%s, token_match=False)", mode or "none")
    return PlainTextResponse("verification failed", status_code=403)


# ---- voice notes -----------------------------------------------------------
def fetch_media(media_id: str) -> tuple[bytes, str]:
    """Resolve a media id to bytes. Two hops: id -> signed url -> download.

    Both hops need the bearer token; the second is a different host, so the
    header has to be sent again explicitly.
    """
    meta = httpx.get(_graph(media_id), headers=_auth_headers(), timeout=20)
    meta.raise_for_status()
    info = meta.json()
    url, mime = info.get("url", ""), info.get("mime_type", "")
    if not url:
        raise ValueError("media id resolved to no url")

    with httpx.stream("GET", url, headers=_auth_headers(), timeout=30) as resp:
        resp.raise_for_status()
        chunks, total = [], 0
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                raise ValueError("media exceeds size cap")
            chunks.append(chunk)
    return (b"".join(chunks), mime)


def transcribe_voice_note(media_id: str) -> tuple[str, Optional[str]]:
    """Download + transcribe a voice note. ("", None) on failure, so the
    pipeline produces its "couldn't read that" reply rather than a 500."""
    from core import providers  # late import: picks up B's real transcriber

    try:
        audio, mime = fetch_media(media_id)
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


# ---- payload parsing -------------------------------------------------------
def iter_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every inbound message in the payload.

    Defensive about shape: Meta batches, and the same endpoint also receives
    `statuses` (delivery receipts) with no `messages` key at all.
    """
    found: list[dict[str, Any]] = []
    for entry in payload.get("entry") or ():
        for change in entry.get("changes") or ():
            value = change.get("value") or {}
            for msg in value.get("messages") or ():
                if isinstance(msg, dict):
                    found.append(msg)
    return found


def _safe_lang(lang: Optional[str]) -> Optional[str]:
    """Drop anything outside the Lang literal, so a transcriber reporting
    'arabic' or 'ar-LB' can't turn into a 500 on the webhook."""
    return lang if lang in VALID_LANGS else None


def build_inquiry(msg: dict[str, Any]) -> Inquiry:
    """Normalise one Meta message into an Inquiry. Never returns raw PII."""
    sender = msg.get("from", "")  # bare digits, e.g. "96170123456" — hashed below
    mtype = msg.get("type", "")
    text, lang = "", None

    if mtype == "text":
        text = ((msg.get("text") or {}).get("body") or "").strip()
    elif mtype in ("audio", "voice"):
        media_id = (msg.get(mtype) or {}).get("id", "")
        if media_id:
            text, lang = transcribe_voice_note(media_id)
    else:
        log.info("unsupported message type received: %s", mtype or "unknown")

    return Inquiry(
        id=msg.get("id", "") or "meta-msg",
        channel="whatsapp",
        text=text,
        lang=_safe_lang(lang),  # type: ignore[arg-type]
        # normalise to +E.164 so a sender hashes to the same ref as on Twilio,
        # whose `From` arrives as "whatsapp:+961...".
        user_ref=user_ref(f"whatsapp:+{sender.lstrip('+')}", prefix="wa"),
    )


# ---- replying --------------------------------------------------------------
def send_text(to: str, body: str) -> bool:
    """POST one text message back. Returns success; never raises at the caller."""
    if not channel_settings.meta_configured:
        # no token/phone id yet: receiving still works, so say so plainly
        # instead of surfacing an httpx error about an empty Bearer header
        log.warning("cannot reply: WHATSAPP_ACCESS_TOKEN / PHONE_NUMBER_ID unset")
        return False
    try:
        r = httpx.post(
            _graph(f"{channel_settings.meta_phone_number_id}/messages"),
            headers={**_auth_headers(), "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                # preview_url lets the MoPH source link render as a card
                "text": {"preview_url": True, "body": body},
            },
            timeout=20,
        )
        if r.status_code >= 400:
            # body can echo the message text, so log only the Graph error code
            code = (r.json().get("error", {}) or {}).get("code") if r.text else None
            log.warning("reply rejected: http=%s graph_code=%s", r.status_code, code)
            return False
        return True
    except Exception as exc:
        log.warning("reply failed to send: %s", type(exc).__name__)
        return False


# ---- the webhook -----------------------------------------------------------
@router.post(WEBHOOK_PATH)
async def meta_webhook(request: Request) -> Response:
    raw = await request.body()

    if not signature_ok(raw, request.headers.get("X-Hub-Signature-256", "")):
        log.warning("rejected webhook with bad/missing Meta signature")
        return JSONResponse({"error": "invalid signature"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        log.warning("rejected webhook with unparseable JSON body")
        return JSONResponse({"error": "bad payload"}, status_code=400)

    messages = iter_messages(payload)
    if not messages:
        # delivery receipt or a field we don't subscribe to — 200 or Meta retries
        return JSONResponse({"status": "ignored"})

    for msg in messages:
        inq = build_inquiry(msg)
        answer: Answer = pipeline.handle(inq)

        sender = msg.get("from", "")
        sent = all(send_text(sender, part) for part in render.for_whatsapp(answer))

        # metadata only: no text, no number, no transcript
        log.info(
            "meta whatsapp turn: tool=%s outcome=%s grounded=%s chars=%d sent=%s",
            answer.tool, answer.outcome, answer.grounded, len(answer.text or ""), sent,
        )

    return JSONResponse({"status": "ok", "handled": len(messages)})
