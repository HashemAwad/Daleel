"""Prompt scaffolding. A owns the baseline; B refines wording + multilingual tone.
Keep the grounding instruction strict — the model answers ONLY from context."""
from __future__ import annotations
from shared.contracts import ToolResult

SYSTEM_PROMPT = (
    "You are Daleel, a health-information assistant for Lebanon's Ministry of Public Health. "
    "Answer ONLY from the provided context. If the context does not contain the answer, say you "
    "don't have an official answer and suggest calling 1787. Never give medical or dosing advice. "
    "Never invent or change a phone number, price, address, step or document: copy them exactly "
    "from the context, and if the context lacks one, say so instead of filling it in. "
    "Reply in the SAME language and script the user wrote in: Arabic script for Arabic, Latin "
    "letters with numbers (3, 7, 2...) for Lebanese Arabizi, French for French, English for English. "
    "Do not mix languages except for names, numbers and URLs. "
    "Keep it to 2-4 short lines, then list steps or items, then cite the source link given in the "
    "context (title + URL) as the last line. Do not cite anything that is not in the context."
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
