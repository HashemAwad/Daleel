"""PII redaction (B3). Owner: B. `redact(text) -> text` runs BEFORE any model call.

Regex-only (no model, no network) so it is fast and deterministic. Masks:
  [PHONE] Lebanese/intl phone numbers      [ID]    long digit runs (national ID, etc.)
  [EMAIL] e-mail addresses                 [NAME]  names the user introduces themselves with
Names can't be detected in general without NER; we catch introductions in AR / EN / FR /
Arabizi ("اسمي X", "أنا X", "my name is X", "je m'appelle X", "ismi X"). Over-masking is
preferred to leaking. Hotlines (1787, 1214, 140...) and prices are short and are left alone.
Never log the input or output of this module.
"""
from __future__ import annotations

import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# optional +961 / 00961 / 961, then 7-8 digits (optionally 0-prefixed local), with separators
_SEP = r"[ \-./]?"
_PHONE = re.compile(
    r"(?<![\d\w])(?:(?:\+|00)961" + _SEP + r"|961" + _SEP + r")?\(?0?\d{1,2}\)?"
    r"(?:" + _SEP + r"\d{2,3}){2,3}(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{9,}(?!\d)")

_W = r"[^\W\d_]+"                      # one letter-only word (any script)
_NAME_WORDS = rf"{_W}(?:\s+{_W}){{0,2}}"
# Words after "أنا" that are NOT names (states/needs/verbs). Extend as the eval set shows.
_NOT_NAMES = {
    "مريض", "مريضة", "بحاجة", "محتاج", "محتاجة", "بدي", "عم", "عندي", "حامل", "كبير", "كبيرة",
    "لبناني", "لبنانية", "سوري", "سورية", "طالب", "طالبة", "من", "في", "هون", "بس", "كمان",
    "مش", "ما", "عايش", "عايشة", "ساكن", "ساكنة", "اسمي", "إسمي", "بعمل", "عم", "لسا",
}
_NAME_INTRO = [
    # Arabic: اسمي / إسمي / اسمه / اسمها + 1-3 words
    re.compile(rf"((?<!\w)[اإ]سم[يهـها]*\s+)({_NAME_WORDS})"),
    # English / French / Arabizi introductions (case-insensitive trigger)
    re.compile(rf"((?<!\w)(?:my name is|i am called|i'm called|je m'appelle|mon nom est|"
               rf"mon nom c'est|[ie]s[mn]i|esmi|ismi|esmo|ismo)\s+)({_NAME_WORDS})", re.I),
]
_ANA = re.compile(rf"((?<!\w)أنا\s+)({_W})")


def _mask_ana(m: re.Match) -> str:
    return m.group(0) if m.group(2) in _NOT_NAMES else m.group(1) + "[NAME]"


def _mask_intro(m: re.Match) -> str:
    # keep the intro words, mask the name; stop the name at a conjunction (و/w/and/et)
    words = m.group(2).split()
    kept = []
    for i, w in enumerate(words):
        if i > 0 and w.lower() in {"and", "et", "w", "و", "بس", "but", "mais", "bas"}:
            kept = words[i:]
            break
    return m.group(1) + "[NAME]" + (" " + " ".join(kept) if kept else "")


def redact(text: str) -> str:
    if not text:
        return text
    t = _EMAIL.sub("[EMAIL]", text)
    # match digits on an ASCII-digit view so Arabic-Indic numerals are caught too
    t = t.translate(_DIGITS)
    t = _LONG_DIGITS.sub("[ID]", t)
    t = _PHONE.sub(lambda m: "[PHONE]" if len(re.sub(r"\D", "", m.group(0))) >= 7 else m.group(0), t)
    for rx in _NAME_INTRO:
        t = rx.sub(_mask_intro, t)
    t = _ANA.sub(_mask_ana, t)
    return t
