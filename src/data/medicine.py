"""Medicine lookup over the `drugs` table. Owner: D. Contract: shared.contracts.MedicineLookup.

The router hands us the WHOLE user sentence. A wrong price is the worst thing this bot
can say, so every doubtful case returns [] and the pipeline falls back to the hotline:

  * a drug matches only if its full name appears as a whole-word phrase in the sentence
  * strength is exact: "Concor 5" never returns the 10mg row; "Concor 20" returns nothing
  * no typo tolerance, no similarity scores
  * several different products matching => all returned WITHOUT a price, so the bot has
    to ask which one instead of quoting one variant's price as "the" price
"""
from __future__ import annotations
import logging
import re
from data.db import get_conn
from data.normalize import normalize
from shared.contracts import DrugRecord

log = logging.getLogger(__name__)
MAX_RECORDS = 5

_UNIT = r"(?:mg|mcg|µg|g|ml|iu|ui|%)"
# A strength in a product NAME ("PROGRAF 0.5 MG", "Bavencio 20 mg/10 ml"): stripped before word matching.
_NAME_STRENGTH = re.compile(rf"\d[\d.,]*\s*{_UNIT}?(?:\s*/\s*[\d.,]*\s*(?:mg|ml|g|dose|vial))?", re.I)
# A standalone number, optionally with a unit. The look-arounds reject Arabizi letters-as-digits
# ("se3r", "7abbet", "2arib") and the inside of a decimal.
_NUMBER = re.compile(rf"(?<![\w.,])(\d+(?:[.,]\d+)?)(?:\s*{_UNIT})?(?![\w])", re.I)
_NOISE = {"mg", "ml", "mcg", "g", "iu", "ui", "po", "iv", "sc", "im"}   # units / routes inside names
# Brand first-words that are also ordinary words: never used for the family fallback.
_STOP_BRANDS = {"children", "human", "hum"}
_MIN_BRAND_LEN = 5

# Arabic-script spellings -> brand word, e.g. {normalize("بنادول"): "panadol"}.
# Deliberately empty: add an entry only after the healthcare teammate has checked it,
# and only for brands that have a price.
ALIASES: dict[str, str] = {}


def _num(text: str) -> float:
    if re.fullmatch(r"\d{1,3}(,\d{3})+", text):       # 1,000 = thousands
        return float(text.replace(",", ""))
    return float(text.replace(",", "."))               # 2,5 = French decimal


def numbers(text: str | None) -> set[float]:
    return {_num(m.group(1)) for m in _NUMBER.finditer(normalize_digits(text))}


def normalize_digits(text: str | None) -> str:
    # normalize() would split "2.5" on the dot, so fold Arabic-Indic digits by hand here.
    return (text or "").translate({0x0660 + i: str(i) for i in range(10)} | {0x06F0 + i: str(i) for i in range(10)})


def name_words(name: str) -> list[str]:
    """'CONCOR AM 5' -> ['concor', 'am'];  'Abremia 250 mg PO' -> ['abremia']"""
    return [w for w in normalize(_NAME_STRENGTH.sub(" ", name)).split() if w not in _NOISE]


def _strength_value(row: dict) -> float | None:
    """The one number that identifies this product's strength: the first number of `strength`
    (100 for '100 mg/10 ml'), else the first number in the name ('CONCOR AM 5')."""
    for source in (row.get("strength"), row["name"]):
        m = re.search(r"\d+(?:[.,]\d+)*", normalize_digits(source))
        if m:
            return _num(m.group(0))
    return None


def _has_phrase(tokens: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return any(tokens[i:i + n] == phrase for i in range(len(tokens) - n + 1))


def match(sentence: str, rows: list[dict]) -> list[dict]:
    """Pure matching. Returns the matched rows; `ambiguous` rows have had their price removed."""
    tokens = [ALIASES.get(t, t) for t in normalize(sentence).split()]
    asked = numbers(sentence)

    named = [(r, name_words(r["name"])) for r in rows]
    named = [(r, w) for r, w in named if w]
    hits = [(r, w) for r, w in named if _has_phrase(tokens, w)]
    if hits:
        longest = max(len(w) for _, w in hits)           # "concor plus" beats "concor"
        found = [r for r, w in hits if len(w) == longest]
    else:                                                # brand family: "panadol" -> its variants
        found = [r for r, w in named
                 if len(w[0]) >= _MIN_BRAND_LEN and w[0] not in _STOP_BRANDS and w[0] in tokens]
    if not found:
        return []

    if asked:
        found = [r for r in found if _strength_value(r) in asked]
        if not found:                                    # asked for a strength we don't have
            return []

    found.sort(key=lambda r: (r["name"], _strength_value(r) or 0, r.get("form") or ""))
    if len(found) > 1:
        found = [{**r, "price": None} for r in found]
    return found[:MAX_RECORDS]


def _record(row: dict) -> DrugRecord:
    label = row["name"]
    strength = row.get("strength")
    if strength and _strength_value({"name": "", "strength": strength}) not in numbers(row["name"]):
        label += f" {strength}"
    if row.get("form"):
        label += f" ({row['form']})"
    price = row.get("price")
    list_date = row.get("list_date")
    return DrugRecord(
        name=label,
        price=float(price) if price is not None else None,      # unknown stays None, never 0
        currency=row.get("currency") or "LBP",
        generics=list(row.get("generics") or []),
        is_free=row.get("is_free"),
        list_date=str(list_date) if list_date else None,
    )


class MedicineLookupImpl:
    def find(self, name: str) -> list[DrugRecord]:
        try:
            # ponytail: reads all ~400 rows per call. Cache or prefilter if the table grows past a few thousand.
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT name, strength, form, price, currency, generics, is_free, list_date FROM drugs"
                ).fetchall()
            return [_record(r) for r in match(name, rows)]
        except Exception as e:
            log.warning("medicine lookup failed: %s", type(e).__name__)   # class only, never the text
            return []
