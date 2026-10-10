"""Deterministic tool router. Owner: A.

Keyword rules choose the tool by default. Optional model routing is used only
when MODEL_ROUTER=1; any model error falls back to these deterministic rules.
"""
from __future__ import annotations
from difflib import SequenceMatcher
import re
from shared.contracts import Inquiry, ToolResult
from core import providers
from core.stubs import StubLLM

TOOLS = ["procedure", "directory", "medicine", "hotline"]

DIRECTORY_TERMS = ["pharmacy", "pharmacie", "صيدلية",
                   "hospital", "مستشفى",
                   "hôpital", "hopital", "centre de santé", "centre de sante",
                   "phc", "mustawsaf", "clinic", "3yede", "عيادة", "مركز",
                   "nearest", "closest", "nearby", "plus proche", "proche", "près de", "pres de",
                   "near", "قريب", "أقرب", "اقرب"]
# Medicine = PRICE/COST/FREE intent only (not the bare word "medicine", which
# also appears in procedure questions). A4 lets the model override this.
MEDICINE_TERMS = ["price", "cost", "how much", "سعر", "كم سعر", "combien",
                  "coûte", "prix", "free", "مجاني", "مجانا",
                  "se3er", "se3r", "adde", "addeh", "2adde", "2addeh", "kam"]

ONE_ONLY_TERMS = (
    "closest one", "nearest one", "only one", "the closest",
    "الأقرب فقط", "اقرب واحد", "أقرب واحد", "le plus proche seulement",
)

# One canonical transliteration per concept, matched phonetically. This is not a
# spelling whitelist: `mestashfa`, `mostashfe`, etc. can match `mustashfa`
# without being added individually.
_ARABIZI_FACILITY = {"hospital": "mustashfa", "pharmacy": "saydaliye", "phc": "mustawsaf"}
_ARABIZI_NEAR = ("a2rab", "2arib")
_ARABIZI_ONE = "wa7de"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _fuzzy_token(text: str, canonical: str, threshold: float = 0.72) -> bool:
    return any(SequenceMatcher(None, token, canonical).ratio() >= threshold for token in _tokens(text))


def _arabizi_facility_kind(text: str) -> str | None:
    scores = {
        kind: max((SequenceMatcher(None, token, word).ratio() for token in _tokens(text)), default=0)
        for kind, word in _ARABIZI_FACILITY.items()
    }
    kind, score = max(scores.items(), key=lambda item: item[1])
    return kind if score >= 0.72 else None


def _semantic_label(text: str, labels: list[str], instruction: str) -> str | None:
    """Constrained semantic understanding; never used to generate facts."""
    if isinstance(providers.llm, StubLLM):
        return None
    try:
        value = providers.llm.classify(f"{instruction}\nMessage: {text}", labels).strip().lower()
        return value if value in labels else None
    except Exception:
        return None


def _resolve_caza(text: str):
    """Extract a canonical caza (town) from the question using D's helper, if
    available. Guarded so the stub path still works when data isn't present."""
    try:
        from data.directory import resolve_caza
        return resolve_caza(text)
    except Exception:
        return None


def _directory_kind(text: str) -> str | None:
    t = text.lower()
    if any(w in t for w in ("hospital", "hôpital", "hopital", "مستشفى")):
        return "hospital"
    if any(w in t for w in ("phc", "مركز", "clinic", "عيادة")):
        return "phc"
    if any(w in t for w in ("pharmacy", "pharmacie", "صيدلية")):
        return "pharmacy"
    fuzzy_kind = _arabizi_facility_kind(text)
    if fuzzy_kind:
        return fuzzy_kind
    label = _semantic_label(
        text, ["unknown", "hospital", "pharmacy", "phc"],
        "Identify the facility type explicitly requested, in any language or transliteration. "
        "Use unknown when no facility type is stated.")
    return None if label in (None, "unknown") else label


def directory_followup_action(text: str) -> str:
    t = text.strip().lower()
    if any(term in t for term in ONE_ONLY_TERMS):
        return "closest_one"
    if any(_fuzzy_token(text, near) for near in _ARABIZI_NEAR) and _fuzzy_token(text, _ARABIZI_ONE):
        return "closest_one"
    if any(term in t for term in ("private", "public", "government", "خاص", "خاصة", "حكومي",
                                  "privé", "prive", "publique", "publics")):
        return "ownership_filter"
    return (_semantic_label(
        text, ["other", "closest_one", "ownership_filter"],
        "Classify this short follow-up about facility results. closest_one means the user wants "
        "only the nearest result; ownership_filter means private/public/government facilities.")
        or "other")


def route_keywords(inq: Inquiry) -> str:
    t = inq.text.lower()
    if any(w in t for w in DIRECTORY_TERMS):
        return "directory"
    if (_arabizi_facility_kind(t) and
            any(_fuzzy_token(t, near) for near in _ARABIZI_NEAR)):
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
    # threshold decide whether there's a real answer). Ambiguous wording is
    # semantically classified into a closed label set; the model never supplies facts.
    kw = route_keywords(inq)
    if kw in ("directory", "medicine"):
        return kw
    semantic = _semantic_label(
        inq.text, TOOLS,
        "Choose the single tool matching the user's intent in any language or transliteration.")
    return semantic or kw


def run_tool(tool: str, inq: Inquiry) -> ToolResult:
    if tool == "directory":
        text = inq.text.lower()
        one_only = any(term in text for term in ONE_ONLY_TERMS)
        kind = _directory_kind(inq.text)
        if kind is None:
            return ToolResult(tool="directory", clarification="facility_type")
        return ToolResult(tool="directory",
                          facilities=providers.directory.nearest(
                              kind,
                              caza=_resolve_caza(inq.text),
                              lat=inq.lat, lon=inq.lon,
                              k=1 if one_only else 3))
    if tool == "medicine":
        return ToolResult(tool="medicine", drugs=providers.medicine.find(inq.text))
    if tool == "hotline":
        return ToolResult(tool="hotline", hotlines=providers.HOTLINES)
    return ToolResult(tool="procedure", docs=providers.procedures.search(inq.text, lang=inq.lang))


def route(inq: Inquiry) -> ToolResult:
    return run_tool(choose_tool(inq), inq)
