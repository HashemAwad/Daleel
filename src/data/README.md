# /src/data — Member D (data & infrastructure)

Your folder (+ `/infra`). Postgres 16 with **pgvector + pg_trgm** (image `pgvector/pgvector:pg16`; no PostGIS — facilities use plain `lat`/`lon`).

## Using the DB
```bash
docker compose up -d                       # db on 127.0.0.1:5432, schema auto-applied on an EMPTY volume
PYTHONPATH=src python -m data.db           # re-apply schema to an existing volume (idempotent)
```
```python
from data.db import get_conn
with get_conn() as conn:                   # dict rows; commits + closes on exit
    conn.execute("SELECT 1")
```
Old volume from before this schema? Either run `python -m data.db` or `docker compose down -v && docker compose up -d`.
If you created your own `procedures` table by hand, drop it first — `IF NOT EXISTS` won't reshape it.

## Seed data (`seeds/*.csv` → `python -m data.loaders`)
```bash
PYTHONPATH=src python -m data.loaders      # idempotent; prints counts only
```
| CSV | Rows | Source |
|-----|------|--------|
| `drugs.csv` | 5,240 (4,646 priced) | The whole MoPH Lebanon National Drugs Database (202 list pages, per-drug `source_url`) + MoPH lists handed to the team (allocation, tender 388, AMAN) |
| `facilities.csv` | 967 pharmacies, 205 hospitals, 220 PHCs | OpenStreetMap via HOT/HDX export, snapshot 2026-10-05 (**ODbL — credit "© OpenStreetMap contributors"**) + MoPH Health Facility Locator: all PHCs (address + phone, no coordinates), 12 governmental hospitals, and a phone on 20 OSM hospitals. Pharmacies still have no phone; no opening hours |
| `cazas.csv`, `caza_aliases.csv` | 26 / ~130 keys | hand-written; caza names match the OSM `adm2_name` values |
| `hotlines.csv` | 5 | wording copied from moph.gov.lb / redcross.org.lb; `verified_on` empty until someone calls each number. **The app does not read this table: its hotlines are `core/stubs.py`** |

- Empty CSV cell = NULL = "unknown". A price is never 0; `is_free` is unset everywhere until a human confirms it.
- Same name/strength/form at two prices (pack sizes) → price left unknown rather than guessed.
- `list_date` is 2026-10-05 where the dated MoPH public price list confirms the name and strength, else empty. `checked_on` is the day we fetched.
- Sources, gaps and the spot-check list: `docs/DATA_RESEARCH.md`. MoPH pharmacies (981, 7 cazas) wait in `seeds/facilities_new.csv`: not merged, they would duplicate the OSM rows.
- Regenerate: `python -m data.build_seeds --suffix _new --moph-all --price-list <xls>` / `--no-moph --moph-facilities` (see `docs/DATA_RESEARCH.md`); the merge into the live CSVs was done by hand on 11 Oct.
- Use `data.normalize.normalize()` / `place_key()` for every key, at ingest **and** query time.

## Medicine lookup (`medicine.py`)
`MedicineLookupImpl().find(sentence)` takes the whole user sentence and fails closed:
- a product matches when its full name appears as a whole-word phrase; no typo tolerance, no similarity scores
- if no full name matches, products sharing the brand's first word come back as a family, **always without a price** ("aspirin" is not "Aspirin Protect 100mg")
- a number is a strength only with a unit ("5mg") or right after the name ("Concor 5"); "Concor for 10 people" asks for no strength
- strength is exact ("Concor 5" never returns 10mg; "Concor 20" returns `[]`)
- **one product → its price; several products → all returned with `price=None`** so the bot must ask which
- anything doubtful, or a DB error → `[]` → the 1787 fallback
- Arabic-script brand spellings: add to `ALIASES` only after the healthcare teammate has checked them (empty for now)

## Directory search (`directory.py`)
`DirectorySearchImpl().nearest(kind, caza=...)` — `caza` may be a caza name in any spelling, a town, or the whole user sentence.
- no recognisable place → `[]` (never arbitrary facilities presented as "nearest")
- with `lat`/`lon`: ranked by real distance, `distance_km` filled. With a place only: **not ranked by distance** — named town first, then the town sharing the caza's name, then alphabetical
- `resolve_caza(text)` → caza or `None`, never raises — for the router. `nearest()` **raises** on a database failure (the pipeline turns that into the hotline reply); `[]` means only "no place given"
- everyday words that are also caza spellings (شوف, sur, sour, صور) only count after a location word or an attached "in the" (بالشوف), unless they are the whole input

## Turn recording and retention (`transcripts.py`, `retention.py`)
`transcripts.record(inq, answer)` is called once per turn by `core.pipeline.handle` and never raises.
- **`metadata`: one row per turn** (not when `RECORD_TURNS=0` or while backing off after a DB outage) — topic from the route (`procedures`, `directory`, `drug_price`, `emergency`, `dosing_request`, `other`), caza, lang, outcome, Beirut-local day. No model call, no text, no session key. Written in its own transaction, before the transcript.
- **`transcripts`: only for a channel-minted ref (`wa_…` / `web_…`) and a non-default `SESSION_HASH_SALT`.** Text only when `STORE_TRANSCRIPT_TEXT=1`, after the redactor and `scrub()` (numbers, emails); never for emergency / refusal turns. The table is unlogged.
- `RECORD_TURNS=0` switches recording off (the test suite does this in `tests/conftest.py`).
```bash
PYTHONPATH=src python -m data.retention --once     # delete idle sessions (RETENTION_IDLE_MINUTES) + anything over 24h
PYTHONPATH=src python -m data.retention --loop     # the same, every RETENTION_INTERVAL_SECONDS (default 600)
PYTHONPATH=src python -m data.retention --status   # counts only; exit 1 if any session is overdue
docker compose exec db psql -U daleel -c "SELECT turn, role, text FROM transcripts ORDER BY created_at"   # show on stage
```

## Tables (`init/schema.sql`)
| Table | Notes |
|-------|-------|
| `procedures` | B's. `embedding vector(1024)` (bge-m3), no vector index (exact scan, <1k rows) |
| `facilities` | `type` ∈ pharmacy/hospital/phc, `caza` → `cazas`, `lat`/`lon` nullable, provenance + `is_synthetic` |
| `drugs` | `price` NULL = unknown (never 0), `is_free` NULL = unknown, `strength` matched exactly, provenance |
| `hotlines` | `verified_on` NULL until a human called it |
| `transcripts` | TEMPORARY and unlogged, scrubbed text or `[not stored]`, PK `(session_hash, turn)`, optional `outcome/tool/lang` |
| `metadata` | the only thing that survives a chat: closed vocab, `day` only, **no id / timestamp / session link** |
| `cazas`, `caza_aliases`, `drug_aliases` | spelling normalisation (Aley / عاليه / 3ale; panadol / بنادول) |

## Rules for code in here
- **Never log exception messages or row text** from DB calls — Postgres errors can echo the row. Log the exception class only.
- No connection at import time (`providers.py` would silently swap in a stub). Query errors → return `[]` so the hotline fallback fires.
- Seeds go through loaders (`ON CONFLICT`), never in `schema.sql`. Only `schema.sql` lives in `init/` (docker runs everything in that dir).

| File | Does | Contract |
|------|------|----------|
| `init/schema.sql` | all tables | mounted by docker-compose |
| `db.py` | `get_conn()`, `apply_schema()` | — |
| `directory.py` | `class DirectorySearchImpl.nearest(...)` | `DirectorySearch` |
| `medicine.py` | `class MedicineLookupImpl.find(name)` | `MedicineLookup` |
| `loaders.py` | seed CSVs → tables (a missing or empty required CSV is an error, never a wipe) | — |
| `transcripts.py` | `record(inq, answer)`: one metadata row per turn + the temporary transcript | — |
| `retention.py` | deletes idle sessions and anything over 24h (it writes nothing) | — |
| `demo.py` | demo reset + sample metadata | — |

Full ticket: `docs/tickets/dev-d.md`.
