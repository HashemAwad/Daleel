"""Schema-constrained, model-driven message understanding.

One hosted-model call produces a validated action plan. The model interprets
language and conversation; tools remain the only source of factual answers.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from core import providers
from core.stubs import StubLLM


class Interpretation(BaseModel):
    intent: Literal["health_question", "greeting", "assistant_info",
                    "out_of_scope", "unclear"]
    relation: Literal["new", "follow_up", "none"]
    safety: Literal["none", "emergency", "medical_advice"] = "none"
    tool: Literal["procedure", "directory", "medicine", "hotline"] | None = None
    facility_type: Literal["pharmacy", "hospital", "phc"] | None = None
    location: str | None = None
    drug: str | None = None
    result_limit: int = Field(default=3, ge=1, le=3)
    ownership_filter: Literal["private", "public"] | None = None
    reply_language: Literal["ar", "arabizi", "fr", "en"]
    needs_clarification: bool = False
    clarification_kind: Literal["location", "facility_type", "meaning", "none"] = "none"
    clarification_question: str = ""
    resolved_query: str = ""
    reply: str = ""
    confidence: float = Field(ge=0, le=1)


_SYSTEM = """You interpret messages for Daleel, Lebanon's Ministry of Public Health
assistant. You never answer health questions and never invent facts. Produce only the
requested structured action plan. Understand Arabic, Lebanese Arabizi, French and English,
including typos and transliteration. Any conversational reply or clarification must be
plain text without emojis, pictograms or decorative icons."""

_SAFETY_SYSTEM = """You are the safety-intent reviewer for a Lebanese public-health
assistant. Classify meaning, not keywords. Mentally correct likely spelling mistakes and
understand Arabic, Lebanese Arabizi, French and English. Return only the requested schema.
Choose emergency when the message may indicate immediate danger to life or an urgent
medical emergency. Choose medical_advice only for individualized diagnosis, dosing,
contraindication or treatment decisions. Official schedules and general public-health
information are none. When uncertain between emergency and none, choose emergency."""

_PROMPT = """Interpret the current message using its meaning and the structured previous
context. Decide whether it is a new request or a follow-up; never let old context override
an explicit new facility, medicine, location or procedure.

Product scope:
- procedure: requirements/steps/rights/licences/how to obtain, register, open or renew a
  Ministry-related service. Asking how to open a pharmacy is a procedure, not a directory.
- directory: locate a nearby pharmacy, hospital or primary-health centre.
- medicine: only official price, alternatives, or free-list status of a named medicine.
- hotline: emergency or request for an official phone number/human.
- assistant_info: who Daleel is or what services it offers.
- out_of_scope: understandable but unrelated to health/Ministry services.

Safety is semantic, not keyword-based. Set safety=emergency for a possible urgent danger
to life or immediate medical emergency, even with typos, dialect or transliteration.
Set safety=medical_advice only for an individualized diagnosis, medicine dose, treatment
choice, contraindication, or a recommendation that depends on the person's symptoms or
medical history. Official schedules, required-vaccine lists, eligibility rules, preventive
health programmes, medicine prices, and Ministry procedures are factual public information,
not medical advice—even when the user asks about their own child or family member. Route
those requests to the appropriate grounded tool. Safety always overrides conversation
history and the previously active tool.

If the request has multiple plausible meanings that require different official sources,
set needs_clarification=true and ask one short clarification in the user's language—but
only when there is no dominant, ordinary interpretation in context. Do not manufacture
unlikely alternatives to a clear request. Prefer the natural meaning of the user's words;
minor spelling mistakes or transliteration are not ambiguity. Ask a clarification only
when choosing an interpretation would materially change the requested service and the
conversation genuinely provides no reasonable way to choose.

The previous context includes an ordered, recent conversation. Interpret references,
corrections, selections and follow-ups from that complete conversation, unless the user
clearly starts a new request. Resolve an ambiguity only when the reply actually selects
one meaning. A reply such as 'yes', 'okay' or 'sure' does not select between alternatives:
keep needs_clarification=true and ask the choice again more clearly.

For greeting/assistant_info/out_of_scope/unclear, put a concise helpful response in reply.
For health_question, reply must be empty because a verified tool will answer it.
For every health_question that does not need clarification, resolved_query must be a
standalone, concise search request in the user's language. It must preserve the user's
chosen meaning while correcting obvious spelling/transliteration errors. Never put facts
or an answer in resolved_query. For a clarification reply such as '2', expand it using the
pending clarification so retrieval never searches for the literal number or fragment.
Map a stated Lebanese place to one exact caza from the allowed list; otherwise use null.
Use result_limit=1 only when the user asks for one/the closest result.

Previous structured context: {context}
The context may contain user_location_available=true when the web/WhatsApp channel already
provided coordinates. In that case, never request a town/caza merely to run a nearest search.
Allowed cazas: {cazas}
Current message: {text}"""


def _schema(cazas: list[str]) -> dict:
    # generateContent's legacy Schema uses `nullable: true` rather than JSON
    # Schema's type union. Keep this intentionally simple for API compatibility.
    nullable_string = {"type": "string", "nullable": True}
    location = ({"type": "string", "nullable": True, "enum": cazas}
                if cazas else nullable_string)
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["health_question", "greeting",
                       "assistant_info", "out_of_scope", "unclear"]},
            "relation": {"type": "string", "enum": ["new", "follow_up", "none"]},
            "safety": {"type": "string", "enum": ["none", "emergency", "medical_advice"]},
            "tool": {"type": "string", "nullable": True,
                     "enum": ["procedure", "directory", "medicine", "hotline"]},
            "facility_type": {"type": "string", "nullable": True,
                              "enum": ["pharmacy", "hospital", "phc"]},
            "location": location,
            "drug": nullable_string,
            "result_limit": {"type": "integer", "minimum": 1, "maximum": 3},
            "ownership_filter": {"type": "string", "nullable": True,
                                 "enum": ["private", "public"]},
            "reply_language": {"type": "string", "enum": ["ar", "arabizi", "fr", "en"]},
            "needs_clarification": {"type": "boolean"},
            "clarification_kind": {"type": "string",
                                   "enum": ["location", "facility_type", "meaning", "none"]},
            "clarification_question": {"type": "string"},
            "resolved_query": {"type": "string"},
            "reply": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["intent", "relation", "safety", "tool", "facility_type", "location", "drug",
                     "result_limit", "ownership_filter", "reply_language",
                     "needs_clarification", "clarification_kind",
                     "clarification_question", "resolved_query", "reply", "confidence"],
    }


def interpret(text: str, cazas: list[str], context: dict | None = None) -> dict | None:
    llm = providers.llm
    if isinstance(llm, StubLLM):
        return None
    prompt = _PROMPT.format(context=json.dumps(context or {}, ensure_ascii=False),
                            cazas=", ".join(cazas), text=text)
    try:
        if hasattr(llm, "generate_structured"):
            raw = llm.generate_structured(_SYSTEM, prompt, _schema(cazas))
        else:
            raw = json.loads(llm.generate(_SYSTEM, prompt))
        parsed = Interpretation.model_validate(raw)
    # Provider/network/quota failures are not interpretation results. Returning
    # None lets the pipeline show its explicit API-unavailable response rather
    # than leaking an exception as a 500 or falling into legacy keyword routing.
    except Exception:
        return None
    out = parsed.model_dump()
    # The API schema can constrain this only to the 1..3 range. Collapse any
    # middle value to the product's supported list size instead of discarding an
    # otherwise valid interpretation and silently reverting to legacy routing.
    out["result_limit"] = 1 if parsed.result_limit == 1 else 3
    out["model"] = getattr(llm, "name", type(llm).__name__)
    return out


def reassess_safety(text: str, context: dict | None = None) -> str:
    """Focused semantic safety review for unclear/out-of-scope first-pass results."""
    llm = providers.llm
    if isinstance(llm, StubLLM) or not hasattr(llm, "generate_structured"):
        return "none"
    schema = {
        "type": "object",
        "properties": {"safety": {"type": "string",
                                      "enum": ["none", "emergency", "medical_advice"]}},
        "required": ["safety"],
    }
    prompt = ("Recent conversation: " + json.dumps(context or {}, ensure_ascii=False)
              + "\nCurrent message: " + text)
    try:
        raw = llm.generate_structured(_SAFETY_SYSTEM, prompt, schema)
        value = raw.get("safety")
        return value if value in {"none", "emergency", "medical_advice"} else "none"
    except Exception:
        return "none"


def resolved_hints(interp: dict | None, previous: dict | None = None) -> dict:
    """Tool arguments, inheriting context only for an explicit follow-up."""
    if not interp:
        return {}
    prior = previous or {}
    inherit = prior if interp.get("relation") == "follow_up" else {}
    values = {
        "facility_type": interp.get("facility_type") or inherit.get("facility_type"),
        "caza": interp.get("location") or inherit.get("caza"),
        "drug": interp.get("drug") or inherit.get("drug"),
        "limit": interp.get("result_limit", 3),
    }
    return {k: v for k, v in values.items() if v is not None}
