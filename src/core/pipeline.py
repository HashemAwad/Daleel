"""The per-turn pipeline. Owner: A.

transcribe (voice) -> safety -> redact -> route -> ground -> Answer.
Nothing reaches the model before redaction; nothing leaves without tool support.
"""
from __future__ import annotations
import httpx
from shared.contracts import Inquiry, Answer, Source, ToolResult
from core import safety, router, providers, memory
from core.prompts import SYSTEM_PROMPT, build_context
from data import transcripts


def handle(inq: Inquiry) -> Answer:
    """Answer one turn, then record it (D's module: scrubs, stores, never raises).
    Wrapping here means the early returns (emergency, refusal, unreadable) are recorded too."""
    answer = _handle(inq)
    transcripts.record(inq, answer)
    return answer


def _handle(inq: Inquiry) -> Answer:
    # 0. Voice notes: turn audio into text before anything else
    inq = _ensure_text(inq)
    if not inq.text.strip():
        return _cannot_read(inq)

    # 0b. Follow-up: if we previously asked this user for a town and they just
    #     replied with a place, stitch it onto the original question.
    inq = _apply_pending_town(inq)

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

    # 4. Grounding gate — no tool support => fallback to a hotline, never guess.
    #    Special case: a directory question with no results is usually a missing
    #    town — ask for it instead of a dead-end hotline message.
    if result.is_empty():
        if result.tool == "directory":
            memory.remember_pending_town(inq.user_ref, inq.text)
            return _ask_town(inq)
        return _fallback(inq)

    # 5. Build grounded answer from tool results only.
    #    If the model is unavailable (not pulled yet, down mid-demo), we still have
    #    REAL retrieved facts — render them plainly instead of dumping to 1787.
    #    This keeps the platform useful under all conditions.
    context = build_context(result)
    try:
        text = providers.llm.generate(SYSTEM_PROMPT, inq.text, context)
    except Exception:
        rendered = _render_facts(result)
        if rendered:
            return Answer(text=rendered, sources=_sources(result), tool=result.tool,
                          grounded=True, outcome="answered", lang=inq.lang)
        return _fallback(inq)
    return Answer(text=text, sources=_sources(result), tool=result.tool,
                  grounded=True, outcome="answered", lang=inq.lang)


# ---- follow-up memory ------------------------------------------------------
def _apply_pending_town(inq: Inquiry) -> Inquiry:
    """If we earlier asked this user for a town and they now reply with a place,
    stitch it onto the original question. Otherwise leave the message as-is
    (and the stale pending is simply discarded)."""
    prev = memory.take_pending_town(inq.user_ref)
    if prev and len(inq.text.split()) <= 4 and router._resolve_caza(inq.text):
        return inq.model_copy(update={"text": f"{prev} {inq.text}"})
    return inq


# ---- model-less rendering (robustness: answer from facts if the LLM is down) ----
def _render_facts(result: ToolResult) -> str:
    """Plain, grounded answer built directly from retrieved facts, no model.
    Used only when the LLM call fails, so the bot still helps instead of
    redirecting to a hotline."""
    lines: list[str] = []
    if result.docs:
        d = result.docs[0]
        lines.append(d.content[:500].strip())
        if d.source:
            lines.append(f"المصدر · source: {d.source.url}")
    elif result.facilities:
        lines.append("أقرب المرافق · Nearest facilities:")
        for f in result.facilities[:3]:
            parts = [f.name] + [p for p in (f.caza, f.address, f.phone) if p]
            lines.append("• " + " — ".join(parts))
    elif result.drugs:
        for dr in result.drugs[:3]:
            price = f"{dr.price} {dr.currency}" if dr.price is not None else "السعر غير متوفر · price not listed"
            free = " — مجاني · free list" if dr.is_free else ""
            lines.append(f"• {dr.name}: {price}{free}")
    elif result.hotlines:
        for h in result.hotlines:
            lines.append(f"• {h.name}: {h.number} — {h.purpose}")
    return "\n".join(lines)


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


def _ask_town(inq: Inquiry) -> Answer:
    return Answer(
        text="أي منطقة أو قضاء؟ مثلاً: بيروت، عاليه، طرابلس.\n"
             "Which town or area? e.g. Beirut, Aley, Tripoli.",
        tool="directory", grounded=False, outcome="unanswered", lang=inq.lang)


def _cannot_read(inq: Inquiry) -> Answer:
    h = _hotline("1787")
    return Answer(
        text=f"Sorry, I couldn't read that message. Please type your question, or call {h.name} on {h.number}.",
        tool="hotline", grounded=False, outcome="unanswered", lang=inq.lang)
