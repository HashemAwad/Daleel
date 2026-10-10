"""The per-turn pipeline. Owner: A.

transcribe (voice) -> safety -> redact -> route -> ground -> Answer.
Nothing reaches the model before redaction; nothing leaves without tool support.
"""
from __future__ import annotations
import httpx
from shared.contracts import Inquiry, Answer, Source, ToolResult
from core import safety, router, providers
from core.prompts import SYSTEM_PROMPT, build_context


def handle(inq: Inquiry) -> Answer:
    # 0. Voice notes: turn audio into text before anything else
    inq = _ensure_text(inq)
    if not inq.text.strip():
        return _cannot_read(inq)

    # 1. Safety rules (may short-circuit) — run on the real text
    early = safety.check(inq)
    if early:
        return early

    # 2. Redact before any model call
    safe_text = providers.redact(inq.text)
    inq = inq.model_copy(update={"text": safe_text})

    # 3. Route to exactly one tool. A tool may raise (missing dependency, DB
    #    down, bug in another module) — never let that 500 the request; degrade
    #    to the hotline fallback so the user always gets a reply.
    try:
        result: ToolResult = router.route(inq)
    except Exception:
        return _fallback(inq)

    # 4. Grounding gate — no tool support => fallback to a hotline, never guess
    if result.is_empty():
        return _fallback(inq)

    # 5. Build grounded answer from tool results only.
    #    If the model is unavailable (not pulled yet, down mid-demo), degrade
    #    gracefully to a hotline fallback instead of 500-ing.
    context = build_context(result)
    try:
        text = providers.llm.generate(SYSTEM_PROMPT, inq.text, context)
    except Exception:
        return _fallback(inq)
    return Answer(text=text, sources=_sources(result), tool=result.tool,
                  grounded=True, outcome="answered", lang=inq.lang)


# ---- voice ----------------------------------------------------------------
def _fetch_audio(url: str) -> bytes:
    """Fetch audio bytes from a URL. Channels may instead pre-transcribe
    (auth-protected WhatsApp media) and leave audio_url empty."""
    return httpx.get(url, timeout=20, follow_redirects=True).content


def _ensure_text(inq: Inquiry) -> Inquiry:
    if inq.text and inq.text.strip():
        return inq
    if inq.audio_url:
        try:
            audio = _fetch_audio(inq.audio_url)
            text, lang = providers.transcriber.transcribe(audio, "audio/ogg")
            return inq.model_copy(update={"text": text, "lang": inq.lang or lang})
        except Exception:
            return inq  # handled by _cannot_read upstream
    return inq


# ---- helpers --------------------------------------------------------------
def _sources(result: ToolResult) -> list[Source]:
    return [d.source for d in result.docs if d.source]


def _hotline(number: str):
    return next(x for x in providers.HOTLINES if x.number == number)


def _fallback(inq: Inquiry) -> Answer:
    h = _hotline("1787")
    return Answer(
        text=f"I don't have an official answer for that yet. Please call {h.name} on {h.number}.",
        tool="hotline", grounded=False, outcome="unanswered", lang=inq.lang)


def _cannot_read(inq: Inquiry) -> Answer:
    h = _hotline("1787")
    return Answer(
        text=f"Sorry, I couldn't read that message. Please type your question, or call {h.name} on {h.number}.",
        tool="hotline", grounded=False, outcome="unanswered", lang=inq.lang)
