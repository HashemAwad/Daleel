"""Medicine lookup over the `drugs` table. Owner: D. Contract: shared.contracts.MedicineLookup.

The router hands us the WHOLE user sentence. A wrong price is the worst thing this bot
can say, so every doubtful case returns [] or drops the price:

  * a product matches when its full name appears as a whole-word phrase in the sentence
  * if no full name matches, products sharing the brand's first word are returned as a
    "family" — ALWAYS without a price, even when there is only one, because the user did
    not name that product ("aspirin" is not "Aspirin Protect 100mg")
  * a number is a strength only if it carries a unit ("5mg") or directly follows the drug
    name ("Concor 5"). "Concor for 10 people" asks for no strength.
  * strength is exact: "Concor 5" never returns the 10mg row; "Concor 20" returns nothing
  * several products matching => all returned WITHOUT a price, so the bot has to ask which
  * no typo tolerance, no similarity scores
"""
from __future__ import annotations
import logging
import re
from data.db import get_conn
from data.normalize import fold, normalize
from shared.contracts import DrugRecord

log = logging.getLogger(__name__)
MAX_RECORDS = 5

_UNIT = r"(?:mg|mcg|µg|μg|g|ml|iu|ui|%)"
# A strength in a product NAME ("PROGRAF 0.5 MG", "Bavencio 20 mg/10 ml"): stripped before word matching.
_NAME_STRENGTH = re.compile(rf"\d[\d.,]*\s*{_UNIT}?(?:\s*/\s*[\d.,]*\s*(?:mg|ml|g|dose|vial))?", re.I)
# Sentence tokens: a standalone number (optionally with a unit), or a word. The look-arounds keep
# Arabizi letters-as-digits ("se3r", "7abbet", "2arib") as WORDS and never split a decimal.
_TOKEN = re.compile(rf"(?P<num>(?<![\w.,])\d+(?:[.,]\d+)?)(?P<unit>\s*{_UNIT})?(?![\w])|(?P<word>[^\W_]+)", re.I)
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


def tokens(sentence: str | None) -> list[tuple]:
    """('w', word) or ('n', value, has_unit), in sentence order."""
    out: list[tuple] = []
    for m in _TOKEN.finditer(fold(sentence)):
        if m.group("num"):
            out.append(("n", _num(m.group("num")), bool(m.group("unit"))))
        else:
            word = m.group("word")
            out.append(("w", ALIASES.get(word, word)))
    return out


def numbers(text: str | None) -> set[float]:
    return {t[1] for t in tokens(text) if t[0] == "n"}


def name_words(name: str) -> list[str]:
    """'CONCOR AM 5' -> ['concor', 'am'];  'Abremia 250 mg PO' -> ['abremia']"""
    return [w for w in normalize(_NAME_STRENGTH.sub(" ", name)).split() if w not in _NOISE]


def _strength_value(row: dict) -> float | None:
    """The one number that identifies this product's strength: the first number of `strength`
    (100 for '100 mg/10 ml'), else the first number in the name ('CONCOR AM 5')."""
    for source in (row.get("strength"), row["name"]):
        m = re.search(r"\d+(?:[.,]\d+)*", fold(source))
        if m:
            return _num(m.group(0))
    return None


def match(sentence: str, rows: list[dict]) -> list[dict]:
    """Pure matching. Returns the matched rows, with `price` removed wherever it must not be quoted."""
    toks = tokens(sentence)
    words = [t[1] if t[0] == "w" else None for t in toks]          # None marks a number's position
    with_unit = {t[1] for t in toks if t[0] == "n" and t[2]}

    def phrase_end(phrase: list[str]) -> int | None:
        n = len(phrase)
        return next((i + n for i in range(len(words) - n + 1) if words[i:i + n] == phrase), None)

    named = [(r, w) for r in rows if (w := name_words(r["name"]))]
    hits = [(r, w, end) for r, w in named if (end := phrase_end(w)) is not None]
    family = not hits
    if hits:
        longest = max(len(w) for _, w, _ in hits)                   # "concor plus" beats "concor"
        found = [(r, end) for r, w, end in hits if len(w) == longest]
    else:                                                           # brand family: "panadol" -> its variants
        found = [(r, words.index(w[0]) + 1) for r, w in named
                 if len(w[0]) >= _MIN_BRAND_LEN and w[0] not in _STOP_BRANDS and w[0] in words]

    kept = []
    for r, end in found:
        asked = set(with_unit)
        if end < len(toks) and toks[end][0] == "n":                 # the number right after the name
            asked.add(toks[end][1])
        if not asked or _strength_value(r) in asked:                # a strength we don't have => dropped
            kept.append(r)
    if not kept:
        return []

    kept.sort(key=lambda r: (r["name"], _strength_value(r) or 0, r.get("form") or ""))
    if family or len(kept) > 1:
        kept = [{**r, "price": None} for r in kept]
    return kept[:MAX_RECORDS]


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
            # ponytail: reads all ~400 rows per call (13-26 ms measured). Cache or prefilter past ~2-3k rows.
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT name, strength, form, price, currency, generics, is_free, list_date FROM drugs"
                ).fetchall()
            return [_record(r) for r in match(name, rows)]
        except Exception as e:
            log.warning("medicine lookup failed: %s", type(e).__name__)   # class only, never the text
            return []
