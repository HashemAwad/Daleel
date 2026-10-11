"""The per-turn pipeline. Owner: A.

transcribe (voice) -> safety -> redact -> route -> ground -> Answer.
Nothing reaches the model before redaction; nothing leaves without tool support.
"""
from __future__ import annotations
import os
import re
import urllib.parse
import httpx
from shared.contracts import Inquiry, Answer, Source, ToolResult, Facility
from core import safety, router, providers, memory, stubs, understanding
from core.prompts import SYSTEM_PROMPT, build_context
from data import transcripts
from core.language import of as reply_lang


def handle(inq: Inquiry) -> Answer:
    """Answer one turn, then record it (D's module: scrubs, stores, never raises).
    Wrapping here means the early returns (emergency, refusal, unreadable) are recorded too.
    Voice notes are transcribed first, so the recorded turn has their text and caza as well."""
    inq = _ensure_text(inq)
    answer = _annotate_debug(_handle(inq))
    # General short-term context: keep the redacted user turn and assistant
    # response so the next semantic interpretation can resolve follow-ups,
    # corrections and clarification choices without phrase-specific rules.
    memory.remember_turn(inq.user_ref, providers.redact(inq.text), answer.text)
    transcripts.record(inq, answer)
    return answer


def _llm_name() -> str:
    """Identifier of the engine that produced an answer (for the model field / debug)."""
    return getattr(providers.llm, "name", type(providers.llm).__name__)


def _known_cazas() -> list[str]:
    """Closed list of cazas for the understanding layer to normalise towns to."""
    try:
        from data.directory import known_cazas
        return known_cazas()
    except Exception:
        return []


def _chat_reply(inq: Inquiry, interp: dict) -> Answer:
    """Greeting / small-talk / unclear message: reply conversationally (the model wrote
    the reply while interpreting), instead of routing it to the hotline fallback.
    'unclear' stays outcome=unanswered so the metrics don't count gibberish as answered."""
    lang = interp.get("reply_language") or reply_lang(inq)
    text = interp.get("reply") or _chat_default(lang)
    answered = interp["intent"] in ("greeting", "assistant_info")
    return Answer(text=text, tool="none", grounded=False,
                  outcome="answered" if answered else "unanswered",
                  lang=lang, model=interp.get("model"))


def _chat_default(lang: str) -> str:
    """Last-resort line if the model didn't include a reply for a non-question."""
    msgs = {
        "ar": "أهلاً! اسألني عن معاملة صحية، سعر دواء، أو أقرب صيدلية أو مستشفى.",
        "arabizi": "Ahlan! Es2alne 3an mu3amale se7iye, se3er dawa, aw a2rab saydaliye aw mustashfa.",
        "fr": "Bonjour ! Posez-moi une question sur une démarche de santé, le prix d'un médicament, ou l'établissement le plus proche.",
        "en": "Hello! Ask me about a health procedure, a medicine price, or the nearest pharmacy or hospital.",
    }
    return msgs.get(lang, msgs["en"])


def _annotate_debug(answer: Answer) -> Answer:
    """With DALEEL_DEBUG set, append the answering API to the visible text.
    Off by default — real users never see it."""
    if os.getenv("DALEEL_DEBUG", "").strip().lower() not in ("1", "true", "yes"):
        return answer
    return answer.model_copy(update={"text": f"{answer.text}\n\n— via {answer.model or 'deterministic'}"})


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

    # 3. UNDERSTAND the message with the model: intent, the tool that answers it, and
    #    the entities to query with (town->caza, facility type, drug) — tolerant of
    #    typos and transliteration, in any of the four languages. This replaces brittle
    #    keyword matching. The model only INTERPRETS here —
    #    every fact still comes from the tools below, so grounding is unchanged.
    previous = memory.last_context(inq.user_ref)
    model_context = dict(previous)
    model_context["conversation"] = memory.conversation_history(inq.user_ref)
    model_context["user_location_available"] = inq.lat is not None and inq.lon is not None
    interp = understanding.interpret(inq.text, _known_cazas(), model_context)

    # API-only understanding: never silently reuse legacy routing or stale
    # conversation state when the semantic API is unavailable.
    if interp is None:
        return _understanding_unavailable(inq)

    safety_category = interp.get("safety", "none")
    if safety_category == "none" and interp.get("intent") in {"unclear", "out_of_scope"}:
        safety_category = understanding.reassess_safety(inq.text, model_context)
    semantic_safety = safety.from_semantic_category(inq, safety_category)
    if semantic_safety:
        return semantic_safety

    # 3c. Greeting / small-talk / gibberish -> reply conversationally, unless we just
    #     recognised the message as a directory refinement.
    needs_clarification = bool(interp and interp.get("needs_clarification"))
    if (needs_clarification and interp.get("clarification_kind") == "location"
            and inq.lat is not None and inq.lon is not None):
        needs_clarification = False
    if interp and needs_clarification:
        question = interp.get("clarification_question", "").strip()
        if question:
            return Answer(text=question, tool=interp.get("tool") or "none",
                          grounded=False, outcome="unanswered",
                          lang=interp.get("reply_language") or reply_lang(inq),
                          model=interp.get("model"))

    if interp and interp["intent"] in ("greeting", "assistant_info", "out_of_scope", "unclear"):
        return _chat_reply(inq, interp)

    # Retrieval needs a complete semantic query, not a fragment such as "2",
    # "yes", or a misspelled phrase. The schema-driven interpreter expands the
    # current turn against pending clarification/context without inventing facts.
    tool_inq = inq
    if interp and interp.get("resolved_query", "").strip():
        tool_inq = inq.model_copy(update={"text": interp["resolved_query"].strip()})

    # 4. Route to exactly one tool (model's choice, else keywords). A tool may raise
    #    (missing dependency, DB down, bug) — never 500; degrade to the hotline fallback.
    chosen_tool = interp.get("tool")
    if not chosen_tool:
        return _understanding_unavailable(inq)
    hints = understanding.resolved_hints(interp, previous)

    # Ownership is absent from the verified facility dataset. This is a
    # data-capability decision, not language matching: any wording/language reaches
    # the same honest result through the structured interpretation.
    if (interp and interp.get("ownership_filter") and
            (chosen_tool == "directory" or previous.get("tool") == "directory")):
        return _ownership_unavailable(inq, interp)
    try:
        result: ToolResult = router.run_tool(chosen_tool, tool_inq, **hints)
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
        kind = hints.get("facility_type") or router._directory_kind(inq.text)
        if kind:
            memory.remember_directory_kind(inq.user_ref, kind)
            memory.remember_context(inq.user_ref, {
                "tool": "directory", "facility_type": kind,
                "caza": hints.get("caza"),
            })
    elif result.tool == "medicine":
        memory.remember_context(inq.user_ref, {"tool": "medicine", "drug": hints.get("drug")})
    elif result.tool in {"procedure", "hotline"}:
        memory.remember_context(inq.user_ref, {"tool": result.tool})

    # 5. Build grounded answer from tool results only.
    #    If the model is unavailable (not pulled yet, down mid-demo), we still have
    #    REAL retrieved facts — render them plainly instead of dumping to 1787.
    #    This keeps the platform useful under all conditions.
    context = build_context(result)
    lang = reply_lang(inq)
    if isinstance(providers.llm, stubs.StubLLM):
        return _understanding_unavailable(inq)
    try:
        text = providers.llm.generate(SYSTEM_PROMPT, tool_inq.text, context)
    except Exception:
        return _understanding_unavailable(inq)
    # The retrieved passage can be a weak/near-miss match (e.g. a "health card"
    # question that only reaches the "vaccination card" page). When that happens the
    # model follows the grounding rule and declines. Return a CLEAN hotline fallback
    # (outcome=unanswered, no mismatched source) instead of a half-refusal that still
    # trails the wrong page's title and is miscounted as "answered".
    if _looks_like_refusal(text):
        return _fallback(inq, result.tool)
    text = _strip_unsourced_urls(text, result)   # A17: no made-up links
    text += _maps_block(result)                  # then add accurate map links
    return Answer(text=text, sources=_sources(result), tool=result.tool,
                  grounded=True, outcome="answered", lang=inq.lang, model=_llm_name())


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


def _ownership_unavailable(inq: Inquiry, interp: dict | None = None) -> Answer:
    lang = (interp or {}).get("reply_language") or reply_lang(inq)
    messages = {
        "ar": "لا تتضمن بيانات المرافق الحالية تصنيفاً موثوقاً للمرافق كخاصة أو حكومية. يمكنني ترتيبها حسب المسافة فقط.",
        "arabizi": "Ma 3enna tasnif mawthou2 iza hal marafe2 khassa aw 7koumiye. Fina nratteba 7asab l masafe bas.",
        "fr": "Les données actuelles n’indiquent pas de façon fiable si ces établissements sont privés ou publics. Je peux seulement les classer par distance.",
        "en": "The current facility data does not reliably identify facilities as private or public. I can only rank them by distance.",
    }
    return Answer(text=messages[lang], tool="directory", grounded=False,
                  outcome="answered", lang=lang,
                  model=(interp or {}).get("model"))


# ---- refusal detection -----------------------------------------------------
# The system prompt tells the model to "say you don't have an official answer" when
# the context doesn't support one. These are that sentence across our four languages;
# matching them lets us swap a leaky half-refusal for the clean hotline fallback.
_REFUSAL_MARKERS = (
    "don't have an official", "do not have an official", "don't have a verified",
    "no official answer", "ليس لدي", "لا أملك", "لا يوجد لدي", "ليس لدينا",
    "لا تتوفر لدي", "je n'ai pas", "je n’ai pas", "pas de réponse officielle",
)


def _looks_like_refusal(text: str) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in _REFUSAL_MARKERS)


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
# Dataset-level provenance for the structured tools. Per-row source URLs aren't in
# the contract, so a procedure cites its own page while medicine/directory cite the
# official dataset they came from — every answer carries a source.
MEDICINE_SOURCE = Source(title="MoPH public drug price list",
                         url="https://www.moph.gov.lb/en/Drugs/index/3/4848")
DIRECTORY_SOURCE = Source(title="Health facilities — OpenStreetMap / HOT via HDX (ODbL)",
                          url="https://data.humdata.org/dataset/hotosm_lbn_health_facilities")


def _sources(result: ToolResult) -> list[Source]:
    if result.docs:
        return [d.source for d in result.docs if d.source]
    if result.drugs:
        return [MEDICINE_SOURCE]
    if result.facilities:
        return [DIRECTORY_SOURCE]
    return []


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


def _understanding_unavailable(inq: Inquiry) -> Answer:
    """Expose an API outage safely instead of reusing an unrelated old intent."""
    lang = reply_lang(inq)
    messages = {
        "ar": "تعذّر فهم الطلب الآن بسبب انقطاع مؤقت في خدمة المساعد. حاول مجدداً بعد قليل. في الحالة الطارئة اتصل على 140.",
        "arabizi": "Ma 2derna nefham talabak halla2 la2an khidmet l musa3ed ma2tou3a mou2akkatan. Jarreb ba3den. Bel tawari2 2ettsel 3a 140.",
        "fr": "Le service de compréhension est temporairement indisponible. Réessayez dans un instant. En cas d’urgence, appelez le 140.",
        "en": "The assistant's understanding service is temporarily unavailable. Please try again shortly. In an emergency, call 140.",
    }
    return Answer(text=messages.get(lang, messages["en"]), tool="none", grounded=False,
                  outcome="unanswered", lang=lang, model=_llm_name())


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
