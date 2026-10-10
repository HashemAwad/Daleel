"""Safety rules that fire BEFORE the model. Owner: A.
Return an Answer to short-circuit the pipeline, or None to continue.
Keyword lists are a starting point — expand with B's eval set findings."""
from __future__ import annotations
from typing import Optional
from shared.contracts import Inquiry, Answer, Source
from core import providers

EMERGENCY_TERMS = [
    "not breathing", "can't breathe", "heart attack", "unconscious", "bleeding badly",
    "ما عم يتنفس", "نوبة قلبية", "overdose", "suicide", "بدي موت", "نزيف",
]
ADVICE_TERMS = [
    "dose", "dosage", "how much", "mg", "جرعة", "كم حبة", "diagnose", "شو عندي",
]


def check(inq: Inquiry) -> Optional[Answer]:
    t = inq.text.lower()
    if any(term in t for term in EMERGENCY_TERMS):
        rc = next(h for h in providers.HOTLINES if h.number == "140")
        return Answer(text=f"This may be an emergency. Call the Red Cross now: {rc.number}.",
                      tool="hotline", grounded=True, outcome="emergency", lang=inq.lang)
    if any(term in t for term in ADVICE_TERMS):
        return Answer(
            text="I can't give medical or dosing advice. Please ask a pharmacist, a doctor, "
                 "or your nearest primary healthcare centre. You can also call 1214.",
            tool="hotline", grounded=True, outcome="refused", lang=inq.lang)
    return None
