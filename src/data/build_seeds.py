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
SUFFIX = ""
MOPH_URL = "https://www.moph.gov.lb/Drugs/index/3/4848"
MOPH_SOURCE = "MoPH Lebanon National Drugs Database"
MOPH_ALL_URL = "https://www.moph.gov.lb/en/Drugs/index/3/4848/page:{p}/sort:Drug.brand_name/direction:ASC"
MOPH_FAC_URL = "https://www.moph.gov.lb/en/HealthFacilities/index/3/188/{t}/page:{p}"
MOPH_FAC_TYPES = {1: ("hospital", "Governmental Hospitals"), 4: ("phc", "PHC Centers"), 7: ("pharmacy", "Pharmacies")}
# MoPH locator district spellings that are not a cazas.csv name in any language
MOPH_CAZA = {"ech chouf": "Chouf", "kesseroune": "Kesrwane", "bcharreh": "Bcharre", "hermel": "El Hermel",
             "baalbeck": "Baalbek", "nabatiye": "El Nabatieh", "el maten": "El Meten"}
UA = {"User-Agent": "Mozilla/5.0 (Daleel hackathon seed build)"}
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


def _table_rows(page: str) -> list[tuple[str, list[str]]]:
    table = re.search(r"<table.*?</table>", page, re.S | re.I)
    rows = re.findall(r"<tr.*?</tr>", table.group(0) if table else "", re.S | re.I)
    return [(r, [_cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S | re.I)]) for r in rows]


def _drug_rows(page: str) -> list[dict]:
    out = []
    for row, cells in _table_rows(page):
        if len(cells) != 7:
            continue
        atc, name, bg, ingredients, dosage, form, price = cells
        view = re.search(r"/Drugs/view/(\d+)", row)
        amount = re.search(r"([\d,]+)\s*L\.L", price)
        amount = amount.group(1).replace(",", "") if amount else ""
        out.append(dict(
            name=name, strength=dosage, form=form, atc=atc, ingredients=ingredients,
            brand_generic=bg, price=amount if amount.strip("0") else "",   # a price is never 0
            currency="LBP", list_date="", source=MOPH_SOURCE,
            source_url=f"https://www.moph.gov.lb/en/Drugs/view/{view.group(1)}" if view else MOPH_URL,
            checked_on=TODAY, is_synthetic="false"))
    return out


def _no_owner(address: str) -> str:
    """Pharmacy addresses name the landlord ("... ملك فلان"): keep the place, drop the person.
    Errs towards cutting too much (any "ملك" not written "الملك" ends the address)."""
    return re.split(r"[\s\-–(،,]*(?<!ال)[بيم]?ملك", address, maxsplit=1)[0].strip()


def _get(http: httpx.Client, url: str) -> str:
    for attempt in range(3):
        try:
            r = http.get(url)
            r.raise_for_status()
            return r.text
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(10)
        finally:
            time.sleep(2)   # be polite to the ministry's server
    return ""


def moph_drugs() -> list[dict]:
    out = []
    with httpx.Client(timeout=40, headers=UA) as http:
        for brand in BRANDS:
            out += _drug_rows(http.post(MOPH_URL, data={"_method": "POST", "data[Drug][name]": brand}).text)
            time.sleep(1)   # be polite to the ministry's server
    return out


def moph_drugs_all() -> list[dict]:
    """Every page of the public database (about 200 list pages), not a brand selection."""
    out = []
    with httpx.Client(timeout=60, headers=UA) as http:
        first = _get(http, MOPH_ALL_URL.format(p=1))
        last = max(map(int, re.findall(r"/Drugs/index/3/4848[^\"]*?page:(\d+)", first)))
        for p in range(1, last + 1):
            rows = _drug_rows(first if p == 1 else _get(http, MOPH_ALL_URL.format(p=p)))
            if not rows:   # a truncated list must not pass for the whole database
                raise SystemExit(f"MoPH drugs page {p}/{last} had no rows")
            out += rows
            print(f"drugs page {p}/{last}: {len(out)} rows", flush=True)
    return out


def moph_facilities() -> list[dict]:
    """MoPH Health Facility Locator: governmental hospitals, PHC centres, pharmacies. No coordinates."""
    with open(SEEDS / "cazas.csv", encoding="utf-8") as fh:
        cazas = {normalize(v): r["name_en"] for r in csv.DictReader(fh) for v in r.values()}
    cazas.update(MOPH_CAZA)
    out, seen, unmapped = [], set(), {}
    with httpx.Client(timeout=60, headers=UA) as http:
        for t, (kind, label) in MOPH_FAC_TYPES.items():
            first = _get(http, MOPH_FAC_URL.format(t=t, p=1))
            last = max(map(int, re.findall(rf"/HealthFacilities/index/3/188/{t}/page:(\d+)", first)), default=1)
            for p in range(1, last + 1):
                page = first if p == 1 else _get(http, MOPH_FAC_URL.format(t=t, p=p))
                head = [_cell(h).lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", page, re.S | re.I)]
                rows = [(r, c) for r, c in _table_rows(page) if c and len(c) == len(head)]
                if not rows:
                    raise SystemExit(f"MoPH facilities type {t} page {p}/{last} had no rows")
                for row, cells in rows:
                    f = dict(zip(head, cells))
                    view = re.search(r"/en/HealthFacilities/view/3/188/(\d+)/[^\"?]*", row)
                    caza = cazas.get(normalize(f["caza"]))
                    if not caza:
                        unmapped[f["caza"]] = unmapped.get(f["caza"], 0) + 1
                        continue
                    if not view or view.group(1) in seen:
                        continue
                    seen.add(view.group(1))
                    phone = f.get("phone", "")
                    if kind == "pharmacy" and re.match(r"\s*(?:03|7\d|81)\b", phone):
                        phone = ""   # a pharmacy's mobile number may be the owner's own: not collected
                    out.append(dict(
                        name=f["name"] or f.get("name(ar)", ""), type=kind, caza=caza, address=_no_owner(f.get("address", "")),
                        phone=phone if re.search(r"\d", phone) else "", lat="", lon="",
                        source=f"MoPH Health Facility Locator ({label})",
                        source_url="https://www.moph.gov.lb" + view.group(0), checked_on=TODAY, is_synthetic="false"))
                print(f"facilities {label} page {p}/{last}: {len(out)} rows", flush=True)
    if unmapped:
        print("SKIPPED, caza not in cazas.csv:", unmapped)
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


def add_list_dates(rows: list[dict], xls: Path) -> dict:
    """Fill list_date from the dated MoPH "Drugs Public Price List" (.xls, needs `pip install xlrd`):
    https://www.moph.gov.lb/en/Pages/3/3101/drugs-public-price-list-  A row gets a date only when every
    line of the official list with its name and strength carries the same exchange-rate date."""
    import xlrd

    def key(name, strength):
        return normalize(name), re.sub(r"\s", "", str(strength)).lower()

    book = xlrd.open_workbook(xls)
    sheet = book.sheet_by_index(0)
    col = {str(h).strip(): i for i, h in enumerate(sheet.row_values(0))}
    dates, prices = {}, {}
    for i in range(1, sheet.nrows):
        r = sheet.row_values(i)
        k = key(r[col["Brand name"]], r[col["Strength"]])
        if r[col["Exch_Dates"]]:
            dates.setdefault(k, set()).add(xlrd.xldate_as_datetime(r[col["Exch_Dates"]], book.datemode).date().isoformat())
        if r[col["Public Price LL"]]:
            prices.setdefault(k, set()).add(round(float(r[col["Public Price LL"]])))
    stats = dict(dated=0, price_confirmed=0, price_differs=0, not_in_list=0)
    for r in rows:
        k = key(r["name"], r["strength"])
        if k not in dates:
            stats["not_in_list"] += 1
            continue
        if len(dates[k]) == 1:
            r["list_date"] = next(iter(dates[k]))
            stats["dated"] += 1
        if r["price"]:
            ok = any(abs(float(r["price"]) - x) <= 1 for x in prices.get(k, ()))
            stats["price_confirmed" if ok else "price_differs"] += 1
    return stats


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
    name = name.replace(".csv", SUFFIX + ".csv")
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
    ap.add_argument("--moph-all", action="store_true", help="whole MoPH drug database instead of BRANDS")
    ap.add_argument("--moph-facilities", action="store_true", help="MoPH locator -> facilities CSV (replaces --osm)")
    ap.add_argument("--price-list", type=Path, help="dated MoPH public price list .xls -> list_date")
    ap.add_argument("--suffix", default="", help="e.g. _new: write drugs_new.csv, never the live seed")
    args = ap.parse_args()
    SUFFIX = args.suffix
    drugs = [] if args.no_moph else moph_drugs_all() if args.moph_all else moph_drugs()
    if args.xlsx:
        drugs += xlsx_drugs(args.xlsx)
    if drugs:
        drugs = dedupe_drugs(drugs)
        if args.price_list:
            print("official price list:", add_list_dates(drugs, args.price_list))
        write("drugs.csv", DRUG_COLS, drugs)
    if args.osm:
        write("facilities.csv", FAC_COLS, osm_facilities(args.osm))
    elif args.moph_facilities:
        write("facilities.csv", FAC_COLS, moph_facilities())
