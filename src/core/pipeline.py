"""The per-turn pipeline. Owner: A.

transcribe (voice) -> safety -> redact -> route -> ground -> Answer.
Nothing reaches the model before redaction; nothing leaves without tool support.
"""
from __future__ import annotations
import re
import urllib.parse
import httpx
from shared.contracts import Inquiry, Answer, Source, ToolResult, Facility
from core import safety, router, providers, memory, stubs
from core.prompts import SYSTEM_PROMPT, build_context
from data import transcripts
from core.language import of as reply_lang


def handle(inq: Inquiry) -> Answer:
    """Answer one turn, then record it (D's module: scrubs, stores, never raises).
    Wrapping here means the early returns (emergency, refusal, unreadable) are recorded too.
    Voice notes are transcribed first, so the recorded turn has their text and caza as well."""
    inq = _ensure_text(inq)
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

    # 0c. Resolve short directory follow-ups against the previous facility type.
    followup = _apply_directory_followup(inq)
    if isinstance(followup, Answer):
        return followup
    inq = followup

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
    chosen_tool = router.choose_tool(inq)
    try:
        result: ToolResult = router.run_tool(chosen_tool, inq)
    except Exception:
        return _fallback(inq, chosen_tool)

    # 4. Grounding gate — no tool support => fallback to a hotline, never guess.
    #    Special case: a directory question with no results is usually a missing
    #    town — ask for it instead of a dead-end hotline message.
    if result.is_empty():
        if result.tool == "directory":
            if result.clarification == "facility_type":
                return _ask_facility_type(inq)
            memory.remember_pending_town(inq.user_ref, inq.text)
            return _ask_town(inq)
        return _fallback(inq, result.tool)

    if result.tool == "directory":
        kind = router._directory_kind(inq.text)
        if kind:
            memory.remember_directory_kind(inq.user_ref, kind)

    # 5. Build grounded answer from tool results only.
    #    If the model is unavailable (not pulled yet, down mid-demo), we still have
    #    REAL retrieved facts — render them plainly instead of dumping to 1787.
    #    This keeps the platform useful under all conditions.
    context = build_context(result)
    lang = reply_lang(inq)
    # Facility records are already structured. Rendering them directly is both
    # clearer and safer than asking an LLM to repeat names, types and distances.
    if result.tool in {"directory", "medicine"}:
        return Answer(text=_render_facts(result, lang), sources=[], tool=result.tool,
                      grounded=True, outcome="answered", lang=lang)
    if isinstance(providers.llm, stubs.StubLLM):
        return Answer(text=_render_facts(result, lang), sources=_sources(result), tool=result.tool,
                      grounded=True, outcome="answered", lang=lang)
    try:
        text = providers.llm.generate(SYSTEM_PROMPT, inq.text, context)
    except Exception:
        rendered = _render_facts(result, lang)
        if rendered:
            return Answer(text=rendered, sources=_sources(result), tool=result.tool,
                          grounded=True, outcome="answered", lang=inq.lang)
        return _fallback(inq)
    text = _strip_unsourced_urls(text, result)   # A17: no made-up links
    text += _maps_block(result)                  # then add accurate map links
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


def _apply_directory_followup(inq: Inquiry) -> Inquiry | Answer:
    """Make short follow-ups refer to the last directory search.

    The dataset has no ownership field, so a request for private/public entries
    must be answered honestly instead of being routed to an unrelated procedure.
    """
    kind = memory.last_directory_kind(inq.user_ref)
    if not kind:
        return inq
    text = inq.text.strip().lower()
    action = router.directory_followup_action(text) if len(text.split()) <= 10 else "other"
    if action == "ownership_filter":
        lang = reply_lang(inq)
        messages = {
            "ar": "لا تتضمن بيانات المرافق الحالية تصنيفاً موثوقاً للمرافق كخاصة أو حكومية. يمكنني ترتيبها حسب المسافة فقط.",
            "arabizi": "Ma 3enna tasnif mawthou2 iza hal marafe2 khassa aw 7koumiye. Fina nratteba 7asab l masafe bas.",
            "fr": "Les données actuelles n’indiquent pas de façon fiable si ces établissements sont privés ou publics. Je peux seulement les classer par distance.",
            "en": "The current facility data does not reliably identify facilities as private or public. I can only rank them by distance.",
        }
        return Answer(text=messages.get(lang, messages["en"]), tool="directory",
                      grounded=False, outcome="answered", lang=lang)
    if action == "closest_one":
        return inq.model_copy(update={"text": f"closest {kind} only one"})
    return inq


# ---- A17: strip any URL the model invented ---------------------------------
_URL_RE = re.compile(r"https?://[^\s)>\]]+")


def _strip_unsourced_urls(text: str, result: ToolResult) -> str:
    """Strip URLs from generated prose.

    Verified links are rendered once from ``Answer.sources`` by each channel;
    generated URLs are never trusted, and repeating real URLs makes the answer
    noisy. Remove a source-only line left behind after stripping as well.
    """
    cleaned = _URL_RE.sub("", text)
    cleaned = re.sub(r"(?im)^\s*(?:source|official source|المصدر|المصدر الرسمي)\s*:?\s*$", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


# ---- Google Maps links (built from our real coordinates, never fabricated) ----
def _maps_url(f: Facility) -> str | None:
    if f.lat is not None and f.lon is not None:
        return f"https://www.google.com/maps/search/?api=1&query={f.lat},{f.lon}"
    if f.name:                       # no coords -> search by name + area
        q = ", ".join(p for p in (f.name, f.caza, "Lebanon") if p)
        return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)
    return None


def _maps_block(result: ToolResult) -> str:
    """A trailing list of accurate map links for the facilities shown. Appended
    after the model's prose so links are always real (A17-safe)."""
    if result.tool != "directory" or not result.facilities:
        return ""
    lines = []
    for f in result.facilities[:3]:
        u = _maps_url(f)
        if u:
            dist = f" ({f.distance_km} كم)" if f.distance_km is not None else ""
            lines.append(f"{f.name}{dist}: {u}")
    return ("\n\nGoogle Maps:\n" + "\n".join(lines)) if lines else ""


# ---- model-less rendering (robustness: answer from facts if the LLM is down) ----
def _render_facts(result: ToolResult, lang: str = "en") -> str:
    """Clean, readable, grounded answer built directly from retrieved facts (no
    model). Each item is a small labelled block, not a dash-chain. Used when the
    LLM is unavailable, so the bot still helps nicely."""
    if result.docs:
        d = result.docs[0]
        return d.content[:500].strip()

    if result.facilities:
        headings = {"ar": "أقرب الأماكن إليك:", "arabizi": "A2rab amekin elak:",
                    "fr": "Les établissements les plus proches :", "en": "Nearest to you:"}
        blocks = []
        for i, f in enumerate(result.facilities[:3], 1):
            lines = [f"{i}. {f.name}"]
            where = "، ".join(p for p in (f.address, f.caza) if p)
            dist = f" · {f.distance_km} km / كم" if f.distance_km is not None else ""
            if where or dist:
                lines.append(f"   {where}{dist}".rstrip())
            if f.phone:
                lines.append(f"   Phone: {f.phone}")
            u = _maps_url(f)
            if u:
                lines.append(f"   Google Maps: {u}")
            blocks.append("\n".join(lines))
        return headings.get(lang, headings["en"]) + "\n\n" + "\n\n".join(blocks)

    if result.drugs:
        unknown = {"ar": "السعر غير متوفر", "arabizi": "El se3er mesh mawjoud",
                   "fr": "Prix non indiqué", "en": "Price not listed"}
        blocks = []
        for dr in result.drugs[:3]:
            price = (f"{dr.price:.0f} {dr.currency}" if dr.price is not None
                     else unknown.get(lang, unknown["en"]))
            lines = [dr.name, f"   {price}"]
            if dr.is_free:
                lines.append("   مجاني للمرضى المزمنين · free for chronic patients")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    if result.hotlines:
        return "الخطوط الساخنة · Hotlines:\n\n" + "\n".join(
            f"{h.number} — {h.name} ({h.purpose})" for h in result.hotlines)
    return ""


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


def _fallback(inq: Inquiry, tool: str = "none") -> Answer:
    h = _hotline("1787")
    lang = reply_lang(inq)
    messages = {
        "ar": f"لا أملك جواباً رسمياً موثوقاً عن هذا السؤال حالياً. يمكنك الاتصال بوزارة الصحة على {h.number}.",
        "arabizi": f"Ma 3ende jawab rasmi mawthou2 3an hal so2al halla2. Fik tettel b wezaret el sa7a 3a {h.number}.",
        "fr": f"Je n’ai pas encore de réponse officielle vérifiée à cette question. Vous pouvez appeler le ministère au {h.number}.",
        "en": f"I don't have a verified official answer for that yet. You can call the Ministry of Public Health on {h.number}.",
    }
    return Answer(
        text=messages[lang], tool=tool, grounded=False, outcome="unanswered", lang=lang)


def _ask_town(inq: Inquiry) -> Answer:
    lang = reply_lang(inq)
    messages = {
        "ar": "في أي منطقة أو قضاء؟ مثلاً: بيروت، عاليه، أو طرابلس.",
        "arabizi": "Bi aya manta2a aw caza? Masalan Beirut, Aley, aw Tripoli.",
        "fr": "Dans quelle ville ou région ? Par exemple : Beyrouth, Aley ou Tripoli.",
        "en": "Which town or area? For example: Beirut, Aley or Tripoli.",
    }
    return Answer(
        text=messages[lang], tool="directory", grounded=False, outcome="unanswered", lang=lang)


def _ask_facility_type(inq: Inquiry) -> Answer:
    lang = reply_lang(inq)
    messages = {
        "ar": "هل تبحث عن مستشفى، صيدلية، أم مركز رعاية صحية؟",
        "arabizi": "3am tdawwer 3a mostashfa, saydaliye, aw markaz se77e?",
        "fr": "Cherchez-vous un hôpital, une pharmacie ou un centre de santé ?",
        "en": "Are you looking for a hospital, pharmacy or primary healthcare centre?",
    }
    return Answer(text=messages[lang], tool="directory", grounded=False,
                  outcome="unanswered", lang=lang)


def _cannot_read(inq: Inquiry) -> Answer:
    h = _hotline("1787")
    return Answer(
        text=f"Sorry, I couldn't read that message. Please type your question, or call {h.name} on {h.number}.",
        tool="hotline", grounded=False, outcome="unanswered", lang=inq.lang)
