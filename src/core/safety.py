"""Safety rules that fire BEFORE the model. Owner: A.
Return an Answer to short-circuit the pipeline, or None to continue.
Expand these lists with B's eval-set findings. Emergency is checked first."""
from __future__ import annotations
from typing import Optional
from shared.contracts import Inquiry, Answer
from core import providers

# Emergency: route straight to the ambulance, model not involved.
EMERGENCY_TERMS = [
    # EN
    "not breathing", "can't breathe", "cannot breathe", "heart attack", "unconscious",
    "bleeding badly", "overdose", "choking", "stroke", "suicide", "kill myself",
    # FR
    "ne respire plus", "crise cardiaque", "inconscient", "overdose", "suicide",
    # AR / arabizi
    "ما عم يتنفس", "مش عم يتنفس", "نوبة قلبية", "فاقد الوعي", "نزيف", "بدي موت", "بدي قتل حالي",
    "3am ymout", "ma 3am yteneffas", "badde moot",
]

# Medical advice / dosing: refuse and point to a human.
ADVICE_TERMS = [
    # EN
    "dose", "dosage", "how much should i take", "how many pills", "mg of", "diagnose",
    "what do i have", "is it safe to take",
    # FR
    "dose", "posologie", "combien de comprimés", "diagnostic",
    # AR / arabizi
    "جرعة", "كم حبة", "كم حبه", "شو عندي", "شو المرض", "آمن آخذ", " qaddesh habbe", "jar3a",
]


def _matches(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def check(inq: Inquiry) -> Optional[Answer]:
    t = inq.text.lower()
    if _matches(t, EMERGENCY_TERMS):
        rc = next(h for h in providers.HOTLINES if h.number == "140")
        return Answer(
            text=f"This may be an emergency. Call the Red Cross now: {rc.number}.",
            tool="hotline", grounded=True, outcome="emergency", lang=inq.lang)
    if _matches(t, ADVICE_TERMS):
        return Answer(
            text="I can't give medical or dosing advice. Please ask a pharmacist, a doctor, "
                 "or your nearest primary healthcare centre. You can also call 1214.",
            tool="hotline", grounded=True, outcome="refused", lang=inq.lang)
    return None
