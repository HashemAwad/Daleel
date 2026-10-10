"""Prompt scaffolding. A owns the baseline; B refines wording + multilingual tone.
Keep the grounding instruction strict — the model answers ONLY from context."""
from __future__ import annotations
from shared.contracts import ToolResult

SYSTEM_PROMPT = (
    "You are Daleel, a health-information assistant for Lebanon's Ministry of Public Health. "
    "Answer ONLY from the provided context. If the context does not contain the answer, say you "
    "don't have an official answer and suggest calling 1787. Never give medical or dosing advice. "
    "Reply in the SAME language the user wrote in (Arabic, Lebanese Arabizi, French, or English). "
    "Keep it to 2-4 short lines, then list steps or items, then cite the source."
)


def build_context(result: ToolResult) -> str:
    parts: list[str] = []
    for d in result.docs:
        src = f" (source: {d.source.url})" if d.source else ""
        parts.append(f"[procedure] {d.title}: {d.content}{src}")
    for f in result.facilities:
        parts.append(f"[facility] {f.name}, {f.type}, {f.caza or ''}, {f.address or ''}, {f.phone or ''}")
    for dr in result.drugs:
        free = "free" if dr.is_free else ("not free" if dr.is_free is False else "unknown")
        parts.append(f"[medicine] {dr.name}: price {dr.price} {dr.currency}, {free}, list {dr.list_date}")
    for h in result.hotlines:
        parts.append(f"[hotline] {h.name} {h.number} — {h.purpose}")
    return "\n".join(parts)
