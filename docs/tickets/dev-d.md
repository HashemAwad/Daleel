# Dev D — Data & infrastructure

You own `src/data/` and `infra/`. You own the **DB schema**, the real directory/medicine/hotline data, the **retention job**, and deployment. **Your independence: high — but you unblock B and C, so ship the schema FIRST.** After that you build in isolation; stubs stand in for your tools in the app until you push.

Branch per ticket: `feat/d/<ID>`. Done = the check passes **and** `PYTHONPATH=src pytest -q` is green.

---
### D0 · Publish the schema — Sprint 0 · **Do this first — it unblocks B and C**
`src/data/init/schema.sql`: create tables per `docs/CONTRACTS.md` (`procedures` w/ `vector`, `facilities` w/ PostGIS `geom`, `drugs`, `hotlines`, `transcripts`, `metadata`); enable `vector` + `postgis` extensions. `docker compose up -d` auto-runs it.
**Done when:** `docker compose up -d` then `\dt` shows all 6 tables; post "schema is up" in the channel.

### D1 · DB helper — Sprint 0–1 · **Independent**
`src/data/db.py`: a connection/session helper reading `DATABASE_URL`.
**Done when:** `from data.db import get_conn` works and runs a `SELECT 1`.

### D2 · Load hotlines + drug list — Sprint 2 · **Independent**
`src/data/loaders/`: insert the 4 hotlines, and load the MoPH public drug + free-medicine lists into `drugs`.
**Done when:** `SELECT * FROM hotlines` returns 4 rows; `SELECT count(*) FROM drugs` > 0.

### D3 · Medicine lookup — Sprint 2 · **Independent**
`src/data/medicine.py`: `class MedicineLookupImpl.find(name) -> [DrugRecord]` (case/typo-tolerant match).
**Done when:** `MedicineLookupImpl().find("Concor")` returns a `DrugRecord`; `/chat` price question now returns real data (providers auto-picks it up).

### D4 · Directory search (PostGIS) — Sprint 2–3 · **Independent**
`src/data/directory.py`: `class DirectorySearchImpl.nearest(kind, caza?, lat?, lon?, k)`. Load ≥1 directory (PHC or hospitals); normalise caza spellings (Aley / عاليه / 3ale).
**Done when:** `nearest("pharmacy", caza="Aley")` returns rows; `/chat` directory question returns real facilities.

### D5 · Retention job — Sprint 4 · **Soft-dep on B's classify** (stub covers it)
`src/data/retention.py`: find transcripts idle > `RETENTION_IDLE_MINUTES`, call `classify()` (B's, or stub) → write a `metadata` row (assert no free text/numbers/names) → delete transcript rows + session hash; log only a count. Schedule every 10 min (demo: set env to 2 min).
**Done when:** insert a fake transcript, run the job, confirm a `metadata` row appears and the transcript rows are gone.

### D6 · Deploy — Sprint 4 · **Independent**
`infra/`: run the app on a cloud VM with a public HTTPS URL (ngrok fallback) so Twilio can reach the webhook; `.env` on the box; DB container running.
**Done when:** `curl https://<public-url>/health` returns ok from another network.

### D7 · Demo reset + backup — Sprint 6 · **Independent**
Script to reseed data and clear transcripts/metadata for a clean rehearsal; help record the backup video.
**Done when:** `bash infra/reset_demo.sh` returns the app to a known demo state.

**Agent kickoff prompt:**
> You are working ONLY in `src/data/` and `infra/` of the Daleel repo. Read `CLAUDE.md`, `docs/CONTRACTS.md`, and `docs/tickets/dev-d.md`. Do D0 (schema) first and announce it. Expose `DirectorySearchImpl` and `MedicineLookupImpl` exactly as named in `docs/CONTRACTS.md` so `core/providers.py` auto-detects them. The retention job must leave no free text/PII in `metadata`. Don't touch other folders. Run `PYTHONPATH=src pytest -q`; keep it green.
