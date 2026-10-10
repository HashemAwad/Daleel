"""Load the checked-in seed CSVs into Postgres. Owner: D.

  PYTHONPATH=src python -m data.loaders        # idempotent: run it as often as you like

Reference tables (cazas, hotlines) are upserted; drugs, facilities and aliases are replaced
wholesale in one transaction, so a row removed from a CSV also disappears from the DB.
Prints counts only.
"""
from __future__ import annotations
import csv
import re
from pathlib import Path
from data.db import get_conn
from data.normalize import normalize, place_key

SEEDS = Path(__file__).parent / "seeds"


def _rows(name: str, required: bool = True) -> list[dict]:
    """A missing or empty required seed file is an error: loading it would wipe the table."""
    path = SEEDS / name
    if not path.exists():
        if required:
            raise FileNotFoundError(f"seed file missing: {path}")
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if required and not rows:
        raise ValueError(f"seed file has no rows: {path}")
    return rows


def _true(cell: str | None) -> bool:
    return (cell or "").strip().lower() == "true"


def _v(s: str | None):
    return (s or "").strip() or None      # empty CSV cell -> NULL (unknown), never 0 / ''


def ingredient_key(ingredients: str | None) -> str | None:
    """'Bisoprolol fumarate - 5mg, Amlodipine besylate - 5mg' -> 'amlodipine besylate + bisoprolol fumarate'"""
    names = []
    for part in (ingredients or "").split(","):
        name = normalize(re.split(r"\s-\s|\s\d", part.strip(), maxsplit=1)[0])
        if name and not name[0].isdigit():      # "1,000mg" splits on its comma: drop the dose fragment
            names.append(name)
    return " + ".join(sorted(set(names))) or None


def caza_alias_rows(cazas: list[dict], extra: list[dict]) -> list[tuple[str, str]]:
    aliases: dict[str, str] = {}

    def add(alias: str | None, caza: str) -> None:
        key = place_key(alias)
        if not key:
            return
        if aliases.setdefault(key, caza) != caza:
            raise ValueError(f"alias {key!r} maps to both {aliases[key]} and {caza}")

    for c in cazas:
        for name in (c["name_en"], c["name_ar"], c["name_fr"]):
            add(name, c["name_en"])
            add(re.sub(r"^(el |ال)", "", name or "", flags=re.I), c["name_en"])   # with / without the article
    for a in extra:
        add(a["alias"], a["caza"])
    return sorted(aliases.items())


def load() -> dict[str, int]:
    cazas, drugs, facilities = _rows("cazas.csv"), _rows("drugs.csv"), _rows("facilities.csv")
    hotlines = _rows("hotlines.csv")
    aliases = caza_alias_rows(cazas, _rows("caza_aliases.csv", required=False))

    # generics = other products with the same ingredient(s) and strength that MoPH marks 'G'
    for d in drugs:
        d["_ing"] = ingredient_key(d["ingredients"])
    generic_names: dict[tuple, set[str]] = {}
    for d in drugs:
        if d["brand_generic"] == "G" and d["_ing"]:
            generic_names.setdefault((d["_ing"], d["strength"]), set()).add(d["name"])

    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO cazas (name_en, name_ar, name_fr) VALUES (%s, %s, %s) "
            "ON CONFLICT (name_en) DO UPDATE SET name_ar = EXCLUDED.name_ar, name_fr = EXCLUDED.name_fr",
            [(c["name_en"], _v(c["name_ar"]), _v(c["name_fr"])) for c in cazas])
        cur.execute("DELETE FROM caza_aliases")
        cur.executemany("INSERT INTO caza_aliases (alias_key, caza) VALUES (%s, %s)", aliases)

        cur.executemany(
            "INSERT INTO hotlines (number, name, purpose, verified_on, source_url) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (number) DO UPDATE SET name = EXCLUDED.name, purpose = EXCLUDED.purpose, "
            "verified_on = EXCLUDED.verified_on, source_url = EXCLUDED.source_url",
            [(h["number"], h["name"], h["purpose"], _v(h["verified_on"]), _v(h["source_url"])) for h in hotlines])

        cur.execute("DELETE FROM drugs")
        cur.executemany(
            "INSERT INTO drugs (name, name_key, strength, form, atc, generics, ingredient_key, price, currency, "
            "list_date, source, source_url, checked_on, is_synthetic) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [(d["name"], normalize(d["name"]), _v(d["strength"]), _v(d["form"]), _v(d["atc"]),
              sorted(generic_names.get((d["_ing"], d["strength"]), set()) - {d["name"]}),
              d["_ing"], _v(d["price"]), d["currency"] or "LBP", _v(d["list_date"]), _v(d["source"]),
              _v(d["source_url"]), _v(d["checked_on"]), _true(d["is_synthetic"])) for d in drugs])

        cur.execute("DELETE FROM facilities")
        cur.executemany(
            "INSERT INTO facilities (name, type, caza, address, phone, lat, lon, source, source_url, "
            "checked_on, is_synthetic) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [(f["name"], f["type"], _v(f["caza"]), _v(f["address"]), _v(f["phone"]), _v(f["lat"]), _v(f["lon"]),
              _v(f["source"]), _v(f["source_url"]), _v(f["checked_on"]), _true(f["is_synthetic"]))
             for f in facilities])

    return {"cazas": len(cazas), "caza_aliases": len(aliases), "hotlines": len(hotlines),
            "drugs": len(drugs), "facilities": len(facilities)}


if __name__ == "__main__":
    print(load())
