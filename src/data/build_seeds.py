"""Regenerate seeds/drugs.csv and seeds/facilities.csv from their sources. Owner: D.

One-off dev tool, NOT used at runtime — the app only ever reads the checked-in CSVs.

  PYTHONPATH=src python -m data.build_seeds --osm health_facilities.geojson --xlsx data_source

Sources
  drugs       MoPH Lebanon National Drugs Database (public search), queried per brand name
              + MoPH spreadsheets handed to the team (needs `pip install openpyxl`)
  facilities  HOT / OpenStreetMap "Lebanon Health Facilities" export from HDX (ODbL):
              https://data.humdata.org/dataset/hotosm_lbn_health_facilities
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
import time
from datetime import date
from pathlib import Path
import httpx
from data.normalize import normalize

SEEDS = Path(__file__).parent / "seeds"
TODAY = date.today().isoformat()
MOPH_URL = "https://www.moph.gov.lb/Drugs/index/3/4848"
MOPH_SOURCE = "MoPH Lebanon National Drugs Database"
OSM_SOURCE = "OpenStreetMap contributors (ODbL), HOT export via HDX"
OSM_URL = "https://data.humdata.org/dataset/hotosm_lbn_health_facilities"

# Common outpatient brands to pull from the MoPH database.
BRANDS = [
    "concor", "panadol", "augmentin", "glucophage", "lipitor", "nexium", "aspirin", "amlor",
    "crestor", "plavix", "ventolin", "euthyrox", "lasix", "coversyl", "zyrtec", "brufen",
    "voltaren", "xarelto", "januvia", "diamicron", "lantus", "atacand", "tenormin", "norvasc",
    "amoxil", "profinal", "tritace", "eltroxin", "zocor", "glucovance",
]
DRUG_COLS = ["name", "strength", "form", "atc", "ingredients", "brand_generic", "price", "currency",
             "list_date", "source", "source_url", "checked_on", "is_synthetic"]
FAC_COLS = ["name", "type", "caza", "address", "phone", "lat", "lon",
            "source", "source_url", "checked_on", "is_synthetic"]
STRENGTH = re.compile(r"\d[\d.,/]*\s*(?:mg|mcg|µg|g|ml|iu|ui|%)(?:\s*/\s*[\d.,]*\s*(?:mg|ml|g|vial))?", re.I)


def _cell(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", s)).split())


def moph_drugs() -> list[dict]:
    out = []
    with httpx.Client(timeout=40, headers={"User-Agent": "Mozilla/5.0 (Daleel hackathon seed build)"}) as http:
        for brand in BRANDS:
            page = http.post(MOPH_URL, data={"_method": "POST", "data[Drug][name]": brand}).text
            table = re.search(r"<table.*?</table>", page, re.S | re.I)
            for row in re.findall(r"<tr.*?</tr>", table.group(0) if table else "", re.S | re.I):
                cells = [_cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
                if len(cells) != 7:
                    continue
                atc, name, bg, ingredients, dosage, form, price = cells
                view = re.search(r"/Drugs/view/(\d+)", row)
                amount = re.search(r"([\d,]+)\s*L\.L", price)
                out.append(dict(
                    name=name, strength=dosage, form=form, atc=atc, ingredients=ingredients,
                    brand_generic=bg, price=amount.group(1).replace(",", "") if amount else "",
                    currency="LBP", list_date="", source=MOPH_SOURCE,
                    source_url=f"https://www.moph.gov.lb/en/Drugs/view/{view.group(1)}" if view else MOPH_URL,
                    checked_on=TODAY, is_synthetic="false"))
            time.sleep(1)   # be polite to the ministry's server
    return out


def xlsx_drugs(folder: Path) -> list[dict]:
    import openpyxl

    def rows(name: str):
        ws = openpyxl.load_workbook(folder / name, read_only=True, data_only=True).worksheets[0]
        return [[("" if c is None else str(c).strip()) for c in r] for r in list(ws.iter_rows(values_only=True))[1:]]

    def rec(name, strength, form, ingredients, price, source):
        return dict(name=name, strength=strength, form=" ".join(form.split()), atc="", ingredients=ingredients,
                    brand_generic="", price=price, currency="LBP", list_date="", source=source,
                    source_url="", checked_on=TODAY, is_synthetic="false")

    out = []
    for fname in ["Allocation Meds website-.xlsx", "Tender388-2024.xlsx"]:
        for r in rows(fname):
            if r[2]:
                price = f"{float(r[9]):.2f}" if r[9] else ""
                out.append(rec(r[2], r[3], r[5], "", price, f"MoPH list: {fname}"))
    for r in rows("Active medications in AMAN_final.xlsx"):
        if r[3]:
            m = STRENGTH.search(r[3]) or STRENGTH.search(r[2])
            out.append(rec(r[3], m.group(0) if m else "", "", r[2], "", "MoPH AMAN active medications list"))
    return out


def dedupe_drugs(rows: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    conflicted: set[tuple] = set()
    for r in rows:
        key = (normalize(r["name"]), r["strength"], r["form"])
        if key not in seen:
            seen[key] = r
        elif r["price"] and seen[key]["price"] and r["price"] != seen[key]["price"]:
            # same name/strength/form at two prices (pack sizes): we can't tell which, so say unknown
            seen[key]["price"] = ""
            conflicted.add(key)
            print("price conflict -> unknown:", key[0], key[1])
        elif r["price"] and not seen[key]["price"] and key not in conflicted:
            seen[key]["price"] = r["price"]
    return list(seen.values())


def osm_facilities(geojson: Path) -> list[dict]:
    out, seen = [], set()
    for f in json.loads(geojson.read_text(encoding="utf-8"))["features"]:
        p, g = f["properties"], f["geometry"]
        kind = p.get("amenity")
        name = (p.get("name_en") or p.get("name") or "").strip()
        if kind not in ("pharmacy", "hospital") or not name or (kind, name, p["adm2_name"]) in seen:
            continue
        seen.add((kind, name, p["adm2_name"]))
        pts = [g["coordinates"]] if g["type"] == "Point" else g["coordinates"][0]
        lon, lat = (sum(c[i] for c in pts) / len(pts) for i in (0, 1))
        out.append(dict(name=name, type=kind, caza=p["adm2_name"], address=p.get("adm3_name") or "",
                        phone="", lat=f"{lat:.6f}", lon=f"{lon:.6f}", source=OSM_SOURCE,
                        source_url=OSM_URL, checked_on=TODAY, is_synthetic="false"))
    return out


def write(name: str, cols: list[str], rows: list[dict]) -> None:
    with open(SEEDS / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(name, len(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", type=Path)
    ap.add_argument("--xlsx", type=Path)
    ap.add_argument("--no-moph", action="store_true")
    args = ap.parse_args()
    drugs = [] if args.no_moph else moph_drugs()
    if args.xlsx:
        drugs += xlsx_drugs(args.xlsx)
    if drugs:
        write("drugs.csv", DRUG_COLS, dedupe_drugs(drugs))
    if args.osm:
        write("facilities.csv", FAC_COLS, osm_facilities(args.osm))
