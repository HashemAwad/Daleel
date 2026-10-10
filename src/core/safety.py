"""Safety rules that fire BEFORE the model. Owner: A.
Return an Answer to short-circuit the pipeline, or None to continue.
Expand these lists with B's eval-set findings. Emergency is checked first."""
from __future__ import annotations
from typing import Optional
from shared.contracts import Inquiry, Answer
from core import providers
from core.language import of as reply_lang

_EMERGENCY = {
    "ar": "قد تكون هذه حالة طارئة. اتصل بالصليب الأحمر الآن على 140.",
    "arabizi": "Hayde mumkin tkun 7ale tari2a. 2ettsel bel Salib el A7mar halla2 3a 140.",
    "fr": "Cela peut être une urgence. Appelez immédiatement la Croix-Rouge au 140.",
    "en": "This may be an emergency. Call the Red Cross now: 140.",
}
_REFUSAL = {
    "ar": "لا أستطيع إعطاء نصيحة طبية أو تحديد جرعة. اسأل صيدلياً أو طبيباً أو اتصل على 1214.",
    "arabizi": "Ma fine 3tik nasi7a tibbiye aw jar3a. Es2al saydale aw hakim, aw 2ettsel 3a 1214.",
    "fr": "Je ne peux pas donner de conseil médical ni de posologie. Consultez un pharmacien ou un médecin, ou appelez le 1214.",
    "en": "I can't give medical or dosing advice. Ask a pharmacist or doctor, or call 1214.",
}

# Emergency: route straight to the ambulance, model not involved.
EMERGENCY_TERMS = [
    # EN
    "not breathing", "can't breathe", "cannot breathe", "heart attack", "unconscious",
    "bleeding badly", "severe chest pain", "crushing chest pain", "overdose", "choking",
    "stroke", "suicide", "kill myself",
    # FR
    "ne respire plus", "crise cardiaque", "inconscient", "overdose", "suicide",
    # AR / arabizi
    "ما عم يتنفس", "مش عم يتنفس", "نوبة قلبية", "فاقد الوعي", "نزيف", "بدي موت", "بدي قتل حالي",
    "3am ymout", "ma 3am yteneffas", "badde moot",
]

# Medical advice / dosing: refuse and point to a human.
ADVICE_TERMS = [
    # EN
    "dose", "dosage", "how much should i take", "how many pills", "diagnose",
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
        lang = reply_lang(inq)
        return Answer(
            text=_EMERGENCY[lang].replace("140", rc.number),
            tool="hotline", grounded=True, outcome="emergency", lang=lang)
    if _matches(t, ADVICE_TERMS):
        lang = reply_lang(inq)
        return Answer(
            text=_REFUSAL[lang], tool="hotline", grounded=True, outcome="refused", lang=lang)
    return None
