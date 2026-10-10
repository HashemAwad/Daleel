"""Facility directory over the `facilities` table. Owner: D. Contract: shared.contracts.DirectorySearch.

    DirectorySearchImpl().nearest("pharmacy", caza="Aley")
    DirectorySearchImpl().nearest("pharmacy", caza="bade saydaliyye 2arib mn Aley")   # whole sentence is fine
    resolve_caza("pharmacie à Choueifat")  -> "Aley"

`caza` may be a caza name in any spelling, a town, or the user's whole sentence.

  * lat/lon given  -> every facility of that kind ranked by real distance, distance_km filled
  * place only     -> facilities in that caza, NOT ranked by distance: the named town first,
                      then the town that shares the caza's name, then alphabetical
  * neither        -> [] (we never present arbitrary facilities as "nearest")

A database failure RAISES from nearest() (the pipeline turns that into the hotline fallback).
Returning [] there would be read as "no place given" and make the bot ask for a town forever.
resolve_caza() never raises.
"""
from __future__ import annotations
import logging
import math
import time
from data.db import get_conn
from data.normalize import place_key
from shared.contracts import Facility

log = logging.getLogger(__name__)
KINDS = {"pharmacy", "hospital", "phc"}
MAX_K = 10


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

# Caza spellings that are also everyday words: "shouf" = "look", "sur" = French "on", صور = "pictures".
# Inside a sentence they only count right after a location word.
_AMBIGUOUS = {place_key(w) for w in ["shouf", "shuf", "شوف", "sur", "sour", "tyre", "صور", "متن"]}
_LOCATION_WORDS = {place_key(w) for w in [
    "in", "near", "from", "at", "à", "a", "au", "de", "du", "en", "vers", "fi", "bi", "b", "mn", "min",
    "3and", "2arib", "janb", "7ad", "في", "من", "ب", "عند", "قرب", "قريب", "جنب", "حد",
]}
# Attached prepositions / articles: بعاليه, بالشوف, b3aley, bel chouf
_PREFIXES = sorted([place_key(p) for p in ["بال", "لل", "عال", "ال", "ب", "ل", "ع", "و", "bel", "bil", "el", "b", "l"]],
                   key=len, reverse=True)
# Only these (preposition + article, "in the ...") may unlock an ambiguous word: بالشوف = "in Chouf",
# but بشوف = "I see", الصور = "the pictures", وشوف = "and look".
_LOCATIVE_PREFIXES = {place_key(p) for p in ["بال", "لل", "عال", "bel", "bil"]}
# Town first-words that are generic ("farm of", "valley of") or surnames, not a specific place.
_GENERIC_TOWN_WORDS = {
    "cheikh", "haouch", "jdeidet", "joubb", "majdel", "mazraa", "mazareaa", "ouadi", "qornet", "sahel",
    "tallet", "kneisset", "douar", "machta", "raouda", "manara", "maasser", "touaite", "tahouitat",
    "soultaniyet", "baghdadi", "majzoub", "biret", "bourjein",
}
_MIN_TOWN_LEN = 5

_CACHE_SECONDS = 300          # re-read place tables now and then, so a reload shows up without a restart
_tables: tuple[dict[str, str], dict[str, str]] | None = None
_loaded_at = 0.0


def build_towns(rows: list[dict], aliases: dict[str, str]) -> dict[str, str]:
    """town first-word -> caza, for words that are distinctive and belong to exactly one caza."""
    seen: dict[str, set[str]] = {}
    for r in rows:
        words = place_key(r["address"]).split()
        if words and r["caza"]:
            seen.setdefault(words[0], set()).add(r["caza"])
    return {w: next(iter(c)) for w, c in seen.items()
            if len(c) == 1 and len(w) >= _MIN_TOWN_LEN and w not in aliases and w not in _GENERIC_TOWN_WORDS}


def _load() -> tuple[dict[str, str], dict[str, str]]:
    """Place tables, cached briefly. Raises if the DB is unreachable or no place data is loaded:
    an empty table must never be cached, or every question would look like "no town given"."""
    global _tables, _loaded_at
    if _tables is None or time.monotonic() - _loaded_at > _CACHE_SECONDS:
        with get_conn() as conn:
            aliases = {r["alias_key"]: r["caza"] for r in conn.execute("SELECT alias_key, caza FROM caza_aliases")}
            towns = build_towns(conn.execute(
                "SELECT DISTINCT address, caza FROM facilities WHERE address IS NOT NULL").fetchall(), aliases)
        if not aliases:
            raise RuntimeError("no place data loaded (run: python -m data.loaders)")
        _tables, _loaded_at = (aliases, towns), time.monotonic()
    return _tables


def resolve(text: str | None, aliases: dict[str, str], towns: dict[str, str]) -> tuple[str | None, str | None]:
    """Pure. -> (caza, town_word). The first place mentioned wins; the longest phrase at that spot wins."""
    tokens = place_key(text).split()
    if not tokens:
        return None, None
    whole = " ".join(tokens)
    if whole in aliases:                                   # a bare place name, however ambiguous
        return aliases[whole], None
    longest = max((len(k.split()) for k in aliases), default=1)

    for i in range(len(tokens)):
        after_location_word = i > 0 and tokens[i - 1] in _LOCATION_WORDS
        for n in range(min(longest, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i:i + n])
            if phrase in aliases and (phrase not in _AMBIGUOUS or after_location_word):
                return aliases[phrase], None
        tok = tokens[i]
        for cand in (tok, tok.rstrip("h")):               # OSM spells it "Jounie"; people write "Jounieh"
            if cand in towns:
                return towns[cand], cand
        for p in _PREFIXES:                                # بعاليه -> عاليه, b3aley -> 3aley
            rest = tok[len(p):]
            if tok.startswith(p) and rest:
                if rest in aliases and (rest not in _AMBIGUOUS or p in _LOCATIVE_PREFIXES):
                    return aliases[rest], None
                if rest in towns:
                    return towns[rest], rest
    return None, None


def resolve_caza(text: str | None) -> str | None:
    """The caza a sentence refers to, or None. Safe to call from the router: never raises."""
    try:
        return resolve(text, *_load())[0]
    except Exception as e:
        log.warning("resolve_caza failed: %s", type(e).__name__)   # class only, never the text
        return None


def order(rows: list[dict], caza: str, town: str | None, aliases: dict[str, str]) -> list[dict]:
    """Named town first, then the town that shares the caza's name (Aley town for Aley caza), then by name."""
    def rank(r: dict) -> tuple:
        words = place_key(r.get("address")).split()
        first = words[0] if words else ""
        return (first != town if town else False, aliases.get(first) != caza, r["name"].lower(), r["id"])
    return sorted(rows, key=rank)


def _facility(r: dict, distance_km: float | None = None) -> Facility:
    return Facility(
        id=str(r["id"]),
        name=r["name"] + (" [demo data]" if r["is_synthetic"] else ""),
        type=r["type"], caza=r["caza"], address=r["address"], phone=r["phone"],
        lat=r["lat"], lon=r["lon"], distance_km=distance_km)


class DirectorySearchImpl:
    def nearest(self, kind: str, caza: str | None = None, lat: float | None = None,
                lon: float | None = None, k: int = 3) -> list[Facility]:
        if kind not in KINDS:
            return []
        k = max(1, min(k, MAX_K))
        try:
            return self._nearest(kind, caza, lat, lon, k)
        except Exception as e:
            log.warning("directory lookup failed: %s", type(e).__name__)   # class only, never the text
            raise

    def _nearest(self, kind: str, caza: str | None, lat: float | None, lon: float | None, k: int) -> list[Facility]:
        aliases, towns = _load()          # also proves the DB is up before we answer "no place given"

        # TRUE nearest: if the user shared a location, rank ALL facilities of this
        # kind by real distance and fill distance_km. This is the accurate path.
        if lat is not None and lon is not None:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, name, type, caza, address, phone, lat, lon, is_synthetic "
                    "FROM facilities WHERE type = %s AND lat IS NOT NULL AND lon IS NOT NULL",
                    (kind,)).fetchall()
            ranked = sorted(((_haversine_km(lat, lon, r["lat"], r["lon"]), r) for r in rows),
                            key=lambda x: x[0])[:k]
            return [_facility(r, round(dist, 1)) for dist, r in ranked]

        # No coordinates: by caza / town.
        if not caza:
            return []
        resolved, town = resolve(caza, aliases, towns)
        if not resolved:
            return []
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, type, caza, address, phone, lat, lon, is_synthetic "
                "FROM facilities WHERE type = %s AND caza = %s", (kind, resolved)).fetchall()
        return [_facility(r) for r in order(rows, resolved, town, aliases)[:k]]
