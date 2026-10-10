"""The per-turn pipeline. Owner: A.
normalize (done by channels) -> safety -> redact -> route -> ground -> Answer.
Nothing reaches the model before redaction; nothing leaves without tool support."""
from __future__ import annotations
from shared.contracts import Inquiry, Answer, Source, ToolResult
from core import safety, router, providers
from core.prompts import SYSTEM_PROMPT, build_context


def handle(inq: Inquiry) -> Answer:
    # 1. Safety rules (may short-circuit)
    early = safety.check(inq)
    if early:
        return early

    # 2. Redact before any model call
    safe_text = providers.redact(inq.text)
    inq = inq.model_copy(update={"text": safe_text})

    # 3. Route to exactly one tool
    result: ToolResult = router.route(inq)

    # 4. Grounding gate — no tool support => fallback to a hotline, never guess
    if result.is_empty():
        return _fallback(inq)

    # 5. Build grounded answer from tool results only
    context = build_context(result)
    text = providers.llm.generate(SYSTEM_PROMPT, inq.text, context)
    sources = _sources(result)
    return Answer(text=text, sources=sources, tool=result.tool, grounded=True,
                  outcome="answered", lang=inq.lang)


def _sources(result: ToolResult) -> list[Source]:
    return [d.source for d in result.docs if d.source]


def _fallback(inq: Inquiry) -> Answer:
    h = next(x for x in providers.HOTLINES if x.number == "1787")
    return Answer(
        text=f"I don't have an official answer for that yet. Please call {h.name} on {h.number}.",
        tool="hotline", grounded=False, outcome="unanswered", lang=inq.lang)
