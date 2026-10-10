"""Tool router: pick ONE tool for an inquiry and run it. Owner: A.

A4: the model classifies the question into a tool; keyword rules are the
fallback (used when no real model is configured, or if the model errors or
returns something invalid). Model-agnostic — works with Anthropic or Ollama
via LLMClient.classify.
"""
from __future__ import annotations
import os
from shared.contracts import Inquiry, ToolResult
from core import providers
from core.stubs import StubLLM

TOOLS = ["procedure", "directory", "medicine", "hotline"]

DIRECTORY_TERMS = ["pharmacy", "saydaliyye", "saydaliye", "saydaliyeh", "farmashia", "صيدلية",
                   "hospital", "mostashfa", "mosta2fa", "mustashfa", "mستشفى", "مستشفى",
                   "phc", "mustawsaf", "clinic", "3yede", "عيادة", "مركز",
                   "nearest", "2arib", "2areeb", "arib", "قريب", "2a2rab", "a2rab", "أقرب", "اقرب"]
# Medicine = PRICE/COST/FREE intent only (not the bare word "medicine", which
# also appears in procedure questions). A4 lets the model override this.
MEDICINE_TERMS = ["price", "cost", "how much", "سعر", "كم سعر", "combien",
                  "coûte", "prix", "free", "مجاني", "مجانا"]


def _resolve_caza(text: str):
    """Extract a canonical caza (town) from the question using D's helper, if
    available. Guarded so the stub path still works when data isn't present."""
    try:
        from data.directory import resolve_caza
        return resolve_caza(text)
    except Exception:
        return None


def _directory_kind(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ("hospital", "مستشفى", "mostashfa", "mosta2fa", "mustashfa")):
        return "hospital"
    if any(w in t for w in ("phc", "مركز", "clinic", "عيادة", "3yede", "mustawsaf")):
        return "phc"
    return "pharmacy"


def route_keywords(inq: Inquiry) -> str:
    t = inq.text.lower()
    if any(w in t for w in DIRECTORY_TERMS):
        return "directory"
    if any(w in t for w in MEDICINE_TERMS):
        return "medicine"
    return "procedure"


def route_model(inq: Inquiry) -> str:
    """Ask the model to choose a tool; fall back to keywords if it's unsure."""
    label = providers.llm.classify(inq.text, TOOLS).strip().lower()
    return label if label in TOOLS else route_keywords(inq)


def choose_tool(inq: Inquiry) -> str:
    # Keyword-first and DETERMINISTIC. A strong signal (directory/medicine terms)
    # wins; otherwise "procedure" is the catch-all (RAG + its own grounding
    # threshold decide whether there's a real answer). The small local model
    # misroutes and is non-deterministic, so model routing is OFF unless
    # MODEL_ROUTER=1 is set (enable it only with a capable model).
    kw = route_keywords(inq)
    if kw in ("directory", "medicine"):
        return kw
    if os.getenv("MODEL_ROUTER") == "1" and not isinstance(providers.llm, StubLLM):
        try:
            return route_model(inq)
        except Exception:
            return kw
    return kw


def run_tool(tool: str, inq: Inquiry) -> ToolResult:
    if tool == "directory":
        return ToolResult(tool="directory",
                          facilities=providers.directory.nearest(_directory_kind(inq.text),
                                                                  caza=_resolve_caza(inq.text)))
    if tool == "medicine":
        return ToolResult(tool="medicine", drugs=providers.medicine.find(inq.text))
    if tool == "hotline":
        return ToolResult(tool="hotline", hotlines=providers.HOTLINES)
    return ToolResult(tool="procedure", docs=providers.procedures.search(inq.text, lang=inq.lang))


def route(inq: Inquiry) -> ToolResult:
    return run_tool(choose_tool(inq), inq)
