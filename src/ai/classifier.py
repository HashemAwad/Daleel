"""Metadata classifier (B5). Owner: B.  `classify(transcript) -> Metadata`.

Called by D's retention job on the (already redacted) transcript just before it is deleted.
Deterministic keyword scoring over AR / Arabizi / FR / EN: no model call, no network, and
every output field comes from a CLOSED vocabulary (or a `cazas.name_en` from the DB), so no
free text, numbers or names can leak into `metadata`.

`outcome` here is only what the transcript itself can show ("emergency" or "answered");
the retention job owns answered/unanswered/escalated/refused from session state and may
override it. Never log the transcript or the result.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from shared.contracts import Lang, Metadata

TOPICS = ("coverage", "referral_admission", "chronic_med", "acute_med", "procedures",
          "directory", "mental_health", "emergency", "other")

# ---------------------------------------------------------------- normalization
_TASHKEEL = re.compile("[ً-ٰٟـ]")
_ARABIC = re.compile("[؀-ۿ]")
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})


def _norm(text: str) -> str:
    return _TASHKEEL.sub("", text).translate(_AR_MAP).lower()


# ---------------------------------------------------------------- vocabulary (normalized)
# Substring match on the normalized text; add terms as the eval set shows gaps.
_KW: dict[str, tuple[str, ...]] = {
    "emergency": ("اسعاف", "طوارئ", "ازمه قلبيه", "جلطه", "نزيف", "غيبوبه",
                  "emergency", "ambulance", "heart attack", "bleeding", "unconscious",
                  "urgence", "samu", "crise cardiaque", "hemorragie", "hémorragie",
                  "es3af", "is3af"),
    "mental_health": ("اكتئاب", "قلق", "نفسي", "انتحار", "1564",
                      "depress", "anxiety", "suicid", "mental health", "panic",
                      "dépress", "anxiété", "santé mentale", "idées noires",
                      "ekti2ab", "ne2si"),
    "chronic_med": ("سرطان", "سكري", "السكر", "ضغط الدم", "غسيل كلي", "تلاسيميا", "مزمن",
                    "cancer", "diabet", "insulin", "dialysis", "thalass", "chronic",
                    "hypertension", "blood pressure",
                    "diabète", "dialyse", "chronique", "tension",
                    "sarataan", "saratan", "sokkari", "sukkari", "daghet"),
    "acute_med": ("دوا", "دواء", "ادويه", "علاج", "بنادول", "مضاد حيوي", "حراره", "سعر",
                  "medicine", "medication", "drug", "pill", "antibiotic", "fever", "panadol",
                  "médicament", "medicament", "pilule", "antibiotique", "fièvre", "prix",
                  "dawa", "dawe", "dawa2", "adwiye"),
    "referral_admission": ("تحويله", "تحويل", "ادخال", "دخول المستشفي", "قبول", "مستشفي",
                           "referral", "admission", "admit", "hospital", "hospitalis",
                           "hôpital", "hopital", "mostashfa", "mostachfa"),
    "coverage": ("ضمان", "تغطيه", "تامين", "تعاونيه", "بطاقه صحيه", "مجاني", "مجانا",
                 "coverage", "insurance", "insured", "nssf", "free of charge", "covered",
                 "couverture", "assurance", "gratuit", "mutuelle",
                 "daman", "da2man", "tghtiye", "ta2min"),
    "procedures": ("كيف احصل", "كيف اخد", "ورقه", "اوراق", "معامله", "طلب", "شهاده",
                   "اثبات", "تسجيل", "بطاقه", "how do i get", "how to get", "how can i get",
                   "paper", "document", "certificate", "procedure", "apply", "register",
                   "démarche", "demarche", "certificat", "papier", "dossier", "comment obtenir",
                   "kif ekhod", "kif bjib", "wara2a", "mo3amale", "shehade"),
}
_PROXIMITY = ("اقرب", "قريب", "جنبي", "عنوان", "وين", "nearest", "closest", "near me", "nearby",
              "where is", "address", "proche", "près de", "pres de", "plus proche",
              "2arib", "2a2reb", "a2reb", "aa2reb", "wein")
_DIRECTORY_NOUNS = ("صيدليه", "مستوصف", "مركز صحي", "pharmac", "clinic", "clinique", "phc",
                    "health cent", "centre de santé", "mostawsaf", "saydaliye", "saydaliyye",
                    "sa2daliye")
_PRIORITY = ("emergency", "mental_health", "chronic_med", "acute_med", "referral_admission",
             "coverage", "directory", "procedures")

_SUBTOPICS = (("cancer", ("سرطان", "cancer", "sarataan", "saratan")),
              ("diabetes", ("سكري", "السكر", "diabet", "insulin", "sokkari", "sukkari")),
              ("dialysis", ("غسيل", "dialys")),
              ("thalassemia", ("تلاسيميا", "thalass")),
              ("hypertension", ("ضغط", "hypertension", "blood pressure", "tension", "daghet")))

# ---------------------------------------------------------------- language
_FR = re.compile(r"\b(le|la|les|des|du|de|et|pour|vous|est|une|un|dans|que|sur|je|mon|ma|où|comment|"
                 r"puis|quel|quelle|pharmacie|besoin|voudrais|liste)\b")
_ARABIZI_DIGITS = re.compile(r"\b\w*[a-z][23579]\w*\b|\b[23579][a-z]\w*\b")
_ARABIZI_WORDS = re.compile(r"\b(bade|badde|badi|kif|kifak|shu|esh|ktir|mnih|wein|3ande|3endi|"
                            r"lazem|hek|sa7a|mesh|aam|shi|ma3|3am|la)\b")


def detect_lang(text: str) -> Optional[Lang]:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    if sum(1 for c in letters if _ARABIC.match(c)) / len(letters) > 0.5:
        return "ar"
    t = text.lower()
    if _ARABIZI_DIGITS.search(t) or len(_ARABIZI_WORDS.findall(t)) >= 2:
        return "arabizi"
    return "fr" if len(_FR.findall(t)) >= 2 or re.search("[éèêàçùôâî]", t) else "en"


# ---------------------------------------------------------------- caza (closed vocab from DB)
def _caza(text: str) -> Optional[str]:
    try:
        from data.directory import resolve_caza      # never raises; returns a cazas.name_en or None
        return resolve_caza(text)
    except Exception:
        return None


# ---------------------------------------------------------------- classify
def _topic(norm: str) -> str:
    scores = {t: sum(1 for k in kws if k in norm) for t, kws in _KW.items()}
    scores["directory"] = 0
    scores["procedures"] *= 0.5        # generic "how do I get X" words must not outvote a specific topic
    has_noun = any(n in norm for n in _DIRECTORY_NOUNS)
    if has_noun and any(p in norm for p in _PROXIMITY):
        scores["directory"] += 3                       # "nearest pharmacy" is a lookup, not a drug question
    elif has_noun and not any(scores.values()):
        scores["directory"] += 1
    best = max(scores.values())
    if best == 0:
        return "other"
    return next(t for t in _PRIORITY if scores[t] == best)


def classify(transcript: str) -> Metadata:
    text = transcript or ""
    norm = _norm(text)
    topic = _topic(norm)
    subtopic = None
    if topic == "chronic_med":
        subtopic = next((s for s, kws in _SUBTOPICS if any(k in norm for k in kws)), None)
    return Metadata(topic=topic, subtopic=subtopic, caza=_caza(text), lang=detect_lang(text),
                    outcome="emergency" if topic == "emergency" else "answered",
                    day=date.today().isoformat())
