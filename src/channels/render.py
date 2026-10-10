"""Turning an Answer into channel-shaped text. Owner: C.

WhatsApp has no markup and a hard per-message limit, so replies are plain text
split into parts. The web widget renders the Answer itself and only uses
`sources_lines` for its link list.
"""
from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape  # re-exported for whatsapp.py

from shared.contracts import Answer

# Twilio accepts 1600 chars per message body; stay under it.
WHATSAPP_LIMIT = 1500

# Facility data comes from OpenStreetMap, which is ODbL: attribution is a
# licence condition, not a courtesy, so it rides with every directory answer.
OSM_CREDIT = "© OpenStreetMap contributors"

__all__ = ["xml_escape", "for_whatsapp", "sources_lines", "chunk", "OSM_CREDIT"]


def sources_lines(answer: Answer) -> list[str]:
    """One line per source, de-duplicated by URL, newest check first."""
    lines, seen = [], set()
    for src in answer.sources:
        if not src.url or src.url in seen:
            continue
        seen.add(src.url)
        checked = f" (checked {src.checked_on})" if src.checked_on else ""
        lines.append(f"↗ {src.title}{checked}\n{src.url}")
    return lines


def chunk(text: str, limit: int = WHATSAPP_LIMIT) -> list[str]:
    """Split on paragraph, then line, then hard-cut — so steps stay readable."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    buf = ""
    for block in text.split("\n"):
        candidate = f"{buf}\n{block}" if buf else block
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            parts.append(buf)
            buf = ""
        while len(block) > limit:
            cut = block.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            parts.append(block[:cut].strip())
            block = block[cut:].strip()
        buf = block
    if buf:
        parts.append(buf)
    return [p for p in parts if p]


def for_whatsapp(answer: Answer) -> list[str]:
    """Full reply as WhatsApp message parts: answer text, sources, attribution."""
    body = (answer.text or "").strip()
    srcs = sources_lines(answer)
    if srcs:
        body = f"{body}\n\n" + "\n\n".join(srcs)
    if answer.tool == "directory" and OSM_CREDIT not in body:
        body = f"{body}\n\n{OSM_CREDIT}"
    parts = chunk(body)
    return parts or ["…"]
