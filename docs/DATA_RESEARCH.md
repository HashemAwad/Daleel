# Data research, 10 Oct 2026

Research behind the seed data for the four question types. **Merged into the live seeds on 11 Oct:** all
drugs, all 220 PHCs, the governmental hospitals (12 new rows, a phone added to 20 OSM rows) and the
hotlines. **Not merged:** the 981 MoPH pharmacies, which stay in `facilities_new.csv` because they would
duplicate the OSM pharmacies. The counts below describe the research files as collected. Every value was read from the page named in its `source_url`
on 2026-10-10 (`checked_on`); nothing was filled from memory, and an empty cell means unknown.

| File | Rows | What |
|---|---|---|
| `src/data/seeds/facilities_new.csv` | 1,234 | 33 governmental hospitals, 220 PHC centres, 981 pharmacies |
| `src/data/seeds/drugs_new.csv` | 5,021 | the whole MoPH drug database (4,658 with a price, 4,166 with `list_date`) |
| `src/data/seeds/hotlines_new.csv` | 5 | 1787, 1214, 01/832700, 1564, 140 |
| `src/data/seeds/procedure_urls.txt` | 59 URLs | procedure pages for Dev B to ingest |

Regenerate (about 12 minutes, 2 s pause per request):
```bash
PYTHONPATH=src python -m data.build_seeds --no-moph --moph-facilities --suffix _new
PYTHONPATH=src python -m data.build_seeds --moph-all --price-list WebMarketed20261005.xls --suffix _new   # needs xlrd
```
Without `--suffix _new` these commands overwrite the live seeds.

## Sources

| Source | URL | Licence | Gave |
|---|---|---|---|
| MoPH Health Facility Locator | https://www.moph.gov.lb/en/HealthFacilities/index/3/188/1 (types 1, 4, 7) | "© Copyrights reserved to Ministry of Public Health"; no reuse licence stated | 1,234 facility rows |
| MoPH Lebanon National Drugs Database | https://www.moph.gov.lb/en/Drugs/index/3/4848 | same | 6,032 product pages, 5,021 rows |
| MoPH Drugs Public Price List, exchange rate of 5/10/2026 | https://www.moph.gov.lb/en/Pages/3/3101/drugs-public-price-list- (`WebMarketed20261005.xls`) | same | `list_date` and a price cross-check; no rows of its own |
| MoPH Administrative Services | https://www.moph.gov.lb/ar/AdministrativeServices/index (201 services) | same | 41 procedure URLs |
| MoPH information pages | moph.gov.lb `/Pages/...` | same | 16 procedure URLs, 4 hotline rows |
| Directorate General of Civil Status | https://www.dgcs.gov.lb/arabic/applicationmechanisms/mechanism4 | none stated | 2 procedure URLs |
| Lebanese Red Cross | https://www.redcross.org.lb/get-in-touch/ | "© 2026 Lebanese Red Cross. All rights reserved" | 1 hotline row |

No OpenStreetMap data is in the new files, so they need no ODbL credit; the existing `facilities.csv` still does.
`moph.gov.lb/robots.txt` disallows only `/files/*`; nothing under that path was fetched. No logins.

## Facilities
- **Governmental hospitals (33):** name, caza, phone (32 of 33). The locator gives them no address. The
  `source` column reads "MoPH Health Facility Locator (Governmental Hospitals)", which is the only
  public flag: the schema has no public/private column.
- **PHC centres (220):** name, caza, address (218), phone (215), all 26 cazas. Addresses are in Arabic.
- **Pharmacies (981):** the locator lists pharmacies for only 7 cazas (Baabda 335, Beirut 231, Aley 184,
  Zahle 177, El Hermel 20, Rachaya 19, West Bekaa 15). 796 have a phone.
- `lat`/`lon` are empty on every row. The locator has no coordinates.
- **Privacy edits, made in `build_seeds.py`:** pharmacy addresses name the landlord ("... ملك فلان");
  the address is cut before that word on about 900 rows. 78 pharmacy phone numbers that are mobile numbers
  were left empty because they may be the owner's own.
- Names are as the ministry spells them; 5 contain a "?" where the site lost a character, and some
  pharmacy names carry a note such as "( اقفال مؤقت )" (temporarily closed).
- **Not merged with the OSM rows.** Many of these hospitals and pharmacies are already in
  `facilities.csv` under another spelling; a simple append would create duplicates.

## Medicines
- The database has 202 list pages, so all of it was fetched instead of choosing 200 brands by hand.
  No official "most used brands" list was found.
- 6,032 product pages became 5,021 rows: products sharing name, strength and form are one row, as the
  existing seed does. `source_url` is the first product page of the group, not one row per page.
- **345 groups have two or more prices (pack sizes), so their price is empty.** The product page has a
  "Presentation" field (pack size) that would separate them, but the seed has no column for it.
- **`list_date`:** the price-list page says "Drugs Prices According to the Exchange Rate Issued on
  5/10/2026". A row is dated 2026-10-05 only when the official spreadsheet lists its name and strength
  with that single date (4,166 rows). The other 855 are spelled differently there or are absent.
- **Cross-check:** 3,902 scraped prices equal the spreadsheet price to the pound. Two do not, most
  likely another pack size: EXODERIL 1% (345,368 scraped, 159,917 listed for 10 ml) and OMEPRAL 20mg
  (712,876 scraped, 213,735 listed for 14). All 88 MoPH rows in the live `drugs.csv` are in the new
  file at the same price.
- **Lipitor is not in the MoPH database.** A search for it returns nothing; 30 other atorvastatin
  products are listed (Atorlip, Liponorm, Lorvast, ...).
- 799 rows have no strength in the source.

### Free medicines (reported, no flag set)
MoPH page: https://www.moph.gov.lb/en/Pages/3/77224/free-medicines-distributed-by-the-ministry-of-public-health
- "List of medicines distributed free of charge by the Ministry of Health" (`Allocation Meds website-.xlsx`)
- "List of Medicines (84 medicines) purchased under the public tender No. 388/2024 and distributed
  free of charge by the Ministry of Public Health" (`Tender388-2024.xlsx`)
- "List of Medications Provided By MoPH in the Catastrophic Disease Management Program"
  (`Active medications in AMAN_final.xlsx`, page dated 23/10/2024)

These are the three spreadsheets already behind the live `drugs.csv`. The page states no condition.
The medicine-assistance procedure (`AdministrativeServices/details/1`) gives two: the patient is
Lebanese and is not covered by any other insurer. Whether that applies to all three lists is for the
healthcare teammate to confirm (open item H4).

## Hotlines
| Number | What the official page says | Differs from the live seed? |
|---|---|---|
| 1787 | "Hotline for Health Services for Displaced Lebanese" (MoPH site header) | **Yes.** The seed says "general health info" |
| 1214 | "MoPH Hotline" (MoPH site header). No purpose is stated on the page | **Yes.** The seed says "Primary care, medication / coverage"; no page supports that |
| 01/832700 | "Hotline for the Patient Admission to Hospitals" (MoPH site header) | New |
| 1564 | "the national hotline for psychological support and suicide prevention, in partnership with Embrace (available 24/7)" | Same meaning |
| 140 | Red Cross: "For Emergencies Call 140", "national medical emergency hotline" | Same meaning |

`verified_on` is empty on every row. The MoPH page source also holds "Hotline for complaints 1214" and
"Coronavirus hotline 01/594459" inside commented-out HTML; they are not shown to visitors and are not
in the file. No official poison-control or epidemic line was found.

## Procedures
- 41 MoPH administrative-service pages (Arabic), 16 MoPH information pages (English and Arabic
  addresses), 2 civil-status pages. Each was fetched and its body read.
- **For Dev B:** the ingest extractor (trafilatura) keeps the site menu together with the procedure on
  MoPH pages, and on 3 pages (`details/81`, `38`, `104`) it returns the menu without the procedure.
  38 of 41 keep the procedure block.
- Some service pages are short (`details/82` has about 200 characters): that is all the ministry publishes.

## Not found or not verified
- **French pages.** moph.gov.lb has no French version (`/fr/` returns an empty shell). Dawlati
  (dawlati.gov.lb, the national services portal) has French, English and Arabic pages for 10 MoPH
  services, but they hold only a title without JavaScript, so they are not in the list.
- **Chronic-medication card.** No page describes it. The nearest are the PHC FAQ and `details/1`.
- **Disability card.** socialaffairs.gov.lb did not answer from this machine; nothing verified.
- **NSSF health claims.** cnss.gov.lb has a forms index (`/مستندات-ونماذج/`) and the law text, no
  step-by-step claims page.
- **Birth and death certificates** are covered only by the civil-status page, in Arabic.
- Hospital addresses, coordinates for all new facilities, pharmacies outside the 7 cazas, opening hours.
- An official list of the most used brands, and an official "free" condition per medicine.

## 30 rows to spot-check by hand
Open the link and compare every field. Also check the two price disagreements above.

| # | Type | Row | Source page |
|---|---|---|---|
| 1 | drug | METHOFEN PLATINUM · (no strength) · Tablet · 668082 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/4309 |
| 2 | drug | FLUMIVIR · 75mg · Capsule · 1384158 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/3225 |
| 3 | drug | APO-ATORVASTATIN · 20mg · Tablet · 1416410 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/1905 |
| 4 | drug | GLYZIDE · 80mg · Tablet · 534849 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/448 |
| 5 | drug | LOTENSE · 5mg · Capsule · 388370 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/1574 |
| 6 | drug | ONDANSETRON VIANEX · 8mg/4ml · Injectable solution · 387027 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/235 |
| 7 | drug | LORBRENA · 25mg · Tablet · 134559469 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/3579 |
| 8 | drug | MICTONORM XL · 45mg · Capsule, modified release · 1877348 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/2431 |
| 9 | drug | GLUCOBAS · 1000mg · Tablet · 302045 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/427 |
| 10 | drug | DIOSMINE BIOGARAN CONSEIL · 600mg · Tablet, coated · 761959 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/1466 |
| 11 | drug | DIANEAL PD4 CYCLER 3.86% GLUCOSE · (no strength) · Injectable solution · 1150329 LBP · list (empty) | https://www.moph.gov.lb/en/Drugs/view/1196 |
| 12 | drug | OESTRACLIN · 0.6mg/g · Gel · 448843 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/2367 |
| 13 | drug | PROGRAF 5MG · 5mg · Capsule · 94286686 LBP · list 2026-10-05 | https://www.moph.gov.lb/en/Drugs/view/4012 |
| 14 | drug | ? FUROSEMIDE INJECTION · 20mg/ml · Injectable solution · 25597 LBP · list (empty) | https://www.moph.gov.lb/en/Drugs/view/1415 |
| 15 | hospital | Kherbet Kanafar Governmental Hospital · West Bekaa · (no address) · 08/645917 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84393/kherbet-kanafar-governmental-hospital |
| 16 | hospital | saida governmental hospital · Saida · (no address) · 07/721606 - 07/751329 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84379/saida-governmental-hospital |
| 17 | hospital | Orange Nassau governmental hospital · Tripoli · (no address) · 06/435997 - 06/428200 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84381/orange-nassau-governmental-hospital |
| 18 | hospital | Daher elbachek governmental hospital · El Meten · (no address) · 04/872148 04/872150->55 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84389/daher-elbachek-governmental-hospital |
| 19 | phc | Maarouf Saad Center · Saida · مدينة العمال · 07-722393 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71758/maarouf-saad-center |
| 20 | phc | Meriata - Kadrieh Municipality Health Center · Zgharta · مرياطة - الطريق العام · 06-255544 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71804/meriata-kadrieh-municipality-health-center |
| 21 | phc | Msaytbeh Medical and Social Center- Makassed · Beirut · المصيطبة مقابل منزل صائب سلام · 01-316920 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71647/msaytbeh-medical-and-social-center-makassed |
| 22 | phc | Jbeil Qadaa Governmental Dispensary · Jbeil · جبيل · 09-540218 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71653/jbeil-qadaa-governmental-dispensary |
| 23 | phc | Lebanese University Health Center - Hadath · Baabda · الجامعة اللبنانية - الحدث · 05/470983 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71692/lebanese-university-health-center-hadath |
| 24 | phc | Yadouna Association center - Baabda · Baabda · بعبدا · 05-923209 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/71678/yadouna-association-center-baabda |
| 25 | pharmacy | حسام · Baabda · الشياح-مارون مسك · (no phone) | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84982/ |
| 26 | pharmacy | صيدلية بسوس Bsous Pharmacy · Aley · بسوس -حي العاصي -الشارع العام -عقار رقم 875 قسم A8 · 05/943211 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/84786/--bsous-pharmacy |
| 27 | pharmacy | الحكمة · Zahle · رياق-السلم · 08/901339 | https://www.moph.gov.lb/en/HealthFacilities/view/3/188/85451/ |
| 28 | hotline | 1787 · MoPH hotline for displaced Lebanese · Hotline for Health Services for Displaced Lebanese (wording of the moph.gov.lb site header) | https://www.moph.gov.lb/en/contact |
| 29 | hotline | 140 · Lebanese Red Cross · For Emergencies Call 140; the national medical emergency hotline | https://www.redcross.org.lb/get-in-touch/ |
| 30 | hotline | 1564 · The Lifeline (Embrace with the MoPH National Mental Health Programme) · National hotline for psychological support and suicide prevention, in partnership with Embrace (available 24/7) | https://www.moph.gov.lb/en/view/75556/1564-the-lifeline |
