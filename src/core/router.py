"""Tool router: pick ONE tool for an inquiry and run it. Owner: A.
MVP uses keyword rules; upgrade to LLM tool-calling once the vertical slice works."""
from __future__ import annotations
from shared.contracts import Inquiry, ToolResult
from core import providers

DIRECTORY_TERMS = ["pharmacy", "saydaliyye", "صيدلية", "hospital", "مستشفى", "phc", "clinic", "مركز", "nearest", "2arib", "قريب"]
MEDICINE_TERMS = ["price", "cost", "سعر", "كم سعر", "combien", "prix", "free", "مجاني", "دوا", "medicine", "drug"]


def route(inq: Inquiry) -> ToolResult:
    t = inq.text.lower()
    if any(w in t for w in DIRECTORY_TERMS):
        kind = "hospital" if ("hospital" in t or "مستشفى" in t) else ("phc" if "phc" in t or "مركز" in t else "pharmacy")
        return ToolResult(tool="directory", facilities=providers.directory.nearest(kind))
    if any(w in t for w in MEDICINE_TERMS):
        # naive: use the whole text as the drug name; B/A can improve extraction
        return ToolResult(tool="medicine", drugs=providers.medicine.find(inq.text))
    # default: procedure retrieval
    docs = providers.procedures.search(inq.text, lang=inq.lang)
    return ToolResult(tool="procedure", docs=docs)
