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
| `drugs.csv` | 403 (96 priced) | MoPH Lebanon National Drugs Database (30 common brands, with per-drug `source_url`) + MoPH lists handed to the team (allocation, tender 388, AMAN) |
| `facilities.csv` | 967 pharmacies, 193 hospitals | OpenStreetMap via HOT/HDX export, snapshot 2026-10-05. **ODbL — credit "© OpenStreetMap contributors"**. No phone numbers, no opening hours, no PHCs yet |
| `cazas.csv`, `caza_aliases.csv` | 26 / ~130 keys | hand-written; caza names match the OSM `adm2_name` values |
| `hotlines.csv` | 4 | `verified_on` empty until someone calls each number |

- Empty CSV cell = NULL = "unknown". A price is never 0; `is_free` is unset everywhere until a human confirms it.
- Same name/strength/form at two prices (pack sizes) → price left unknown rather than guessed.
- `list_date` is empty: the MoPH search page doesn't state one. `checked_on` is the day we fetched.
- Regenerate drugs/facilities: `python -m data.build_seeds --osm <geojson> --xlsx data_source` (needs `openpyxl`).
- Use `data.normalize.normalize()` / `place_key()` for every key, at ingest **and** query time.

## Tables (`init/schema.sql`)
| Table | Notes |
|-------|-------|
| `procedures` | B's. `embedding vector(1024)` (bge-m3), no vector index (exact scan, <1k rows) |
| `facilities` | `type` ∈ pharmacy/hospital/phc, `caza` → `cazas`, `lat`/`lon` nullable, provenance + `is_synthetic` |
| `drugs` | `price` NULL = unknown (never 0), `is_free` NULL = unknown, `strength` matched exactly, provenance |
| `hotlines` | `verified_on` NULL until a human called it |
| `transcripts` | TEMPORARY, **redacted text only**, PK `(session_hash, turn)`, optional `outcome/tool/lang` |
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
| `loaders/` | seed CSVs → tables | — |
| `retention.py` | idle convos → `classify()` → `metadata` → delete transcript | — |

Full ticket: `docs/tickets/dev-d.md`.
