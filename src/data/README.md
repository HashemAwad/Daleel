# /src/data — Member D (data & infrastructure)

Your folder (+ `/infra`). You own the DB schema — publish it FIRST so B and C build against real tables.

| File | Does | Contract |
|------|------|----------|
| `init/schema.sql` | tables: `procedures` (pgvector), `facilities` (PostGIS), `drugs`, `hotlines`, `transcripts`, `metadata` | mounted by docker-compose |
| `db.py` | connection/session helper | — |
| `directory.py` | `class DirectorySearchImpl.nearest(...)` (PostGIS nearest-to) | `DirectorySearch` |
| `medicine.py` | `class MedicineLookupImpl.find(name)` | `MedicineLookup` |
| `loaders/` | load drug list + directories + hotlines into tables | — |
| `retention.py` | job: find idle convos → `classify()` → write `metadata` → delete transcript + hash | — |

Full ticket: `docs/tickets/dev-d.md`.
