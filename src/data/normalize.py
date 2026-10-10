"""One text normaliser for the data layer. Owner: D.

Use the SAME function at ingest and at query time, or keys silently stop matching.
  normalize()  — drugs and general text. Keeps digits as-is ("Concor 5" stays 5).
  fold()       — the same folding without stripping punctuation, for code that must see "2.5".
  place_key()  — place names only. Also folds Arabizi digits (3ale -> aale).
"""
from __future__ import annotations
import re
import unicodedata

_MAP = str.maketrans({
    "ى": "ي", "ة": "ه", "ـ": "",
    **{chr(0x0660 + i): str(i) for i in range(10)},   # Arabic-Indic digits
    **{chr(0x06F0 + i): str(i) for i in range(10)},   # Eastern Arabic-Indic digits
})
_ARABIZI = str.maketrans({"2": "a", "3": "a", "5": "kh", "7": "h", "8": "gh", "9": "s"})


def fold(text: str | None) -> str:
    """Case, accents, Arabic letter forms and digits folded; punctuation KEPT (so "2.5" survives)."""
    # NFKD splits accents, tashkeel and hamza-on-alef into combining marks we then drop:
    # é -> e, أ/إ/آ -> ا, presentation forms -> plain letters.
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower().translate(_MAP)


def normalize(text: str | None) -> str:
    return " ".join(re.sub(r"[^\w\s]|_", " ", fold(text)).split())


def place_key(text: str | None) -> str:
    # Arabizi digits only inside tokens that also have letters, so "3ale" folds but "2026" doesn't.
    return " ".join(
        tok.translate(_ARABIZI) if any(c.isalpha() for c in tok) else tok
        for tok in normalize(text).split()
    )


if __name__ == "__main__":
    assert normalize("Coûte  le CONCOR 5?") == "coute le concor 5"
    assert normalize("بَنادُول") == normalize("بنادول")
    assert normalize("أدوية") == "ادويه"
    assert normalize("٥ mg") == "5 mg"
    assert place_key("3ale") == place_key("Aale") == "aale"
    assert place_key("عاليه") == place_key("عالية")
    assert place_key("2026") == "2026"
    print("normalize ok")
