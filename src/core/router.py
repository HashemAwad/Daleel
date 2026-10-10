"""Tool router: pick ONE tool for an inquiry and run it. Owner: A.

A4: the model classifies the question into a tool; keyword rules are the
fallback (used when no real model is configured, or if the model errors or
returns something invalid). Model-agnostic — works with Anthropic or Ollama
via LLMClient.classify.
"""
from __future__ import annotations
from shared.contracts import Inquiry, ToolResult
from core import providers
from core.stubs import StubLLM

TOOLS = ["procedure", "directory", "medicine", "hotline"]

DIRECTORY_TERMS = ["pharmacy", "saydaliyye", "صيدلية", "hospital", "مستشفى", "phc",
                   "clinic", "مركز", "nearest", "2arib", "قريب"]
# Medicine = PRICE/COST/FREE intent only (not the bare word "medicine", which
# also appears in procedure questions). A4 lets the model override this.
MEDICINE_TERMS = ["price", "cost", "how much", "سعر", "كم سعر", "combien",
                  "coûte", "prix", "free", "مجاني", "مجانا"]


def _directory_kind(text: str) -> str:
    t = text.lower()
    if "hospital" in t or "مستشفى" in t:
        return "hospital"
    if "phc" in t or "مركز" in t or "clinic" in t:
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
    # No real model configured -> deterministic keyword routing (keeps tests + the
    # stub path predictable). Real model -> model routing with keyword fallback.
    if isinstance(providers.llm, StubLLM):
        return route_keywords(inq)
    try:
        return route_model(inq)
    except Exception:
        return route_keywords(inq)


def run_tool(tool: str, inq: Inquiry) -> ToolResult:
    if tool == "directory":
        return ToolResult(tool="directory",
                          facilities=providers.directory.nearest(_directory_kind(inq.text)))
    if tool == "medicine":
        return ToolResult(tool="medicine", drugs=providers.medicine.find(inq.text))
    if tool == "hotline":
        return ToolResult(tool="hotline", hotlines=providers.HOTLINES)
    return ToolResult(tool="procedure", docs=providers.procedures.search(inq.text, lang=inq.lang))


def route(inq: Inquiry) -> ToolResult:
    return run_tool(choose_tool(inq), inq)
