# CLAUDE.md — Daleel (read me first)

This file is loaded automatically by Claude Code. If you are an agent working in this repo, follow it.

## What we're building
**Daleel** (دليل) — a health-information assistant for Lebanon's Ministry of Public Health (MoPH), on **WhatsApp** and a **web widget**, in **Arabic / Arabizi / French / English**. It answers four question types, always from a verified source (never model memory):
1. **Procedures** ("how do I get X paper?") — RAG over official pages.
2. **Directory** (nearest pharmacy / public hospital / PHC) — DB query.
3. **Medicines** (price, is-it-free) — drug-list lookup.
4. **Hotlines / escalation** — deterministic routing (1787, 1214, 1564, Red Cross 140).

**Voice notes are a core feature, not a bonus:** WhatsApp audio → transcribe → treat as a text inquiry.

**Phase 1 (this weekend):** the chatbot. **Phase 2 (right after):** a ministry dashboard built from anonymised metadata. Build Phase 1 so Phase 2 is easy — that's why every turn writes one anonymous `Metadata` row (`data.transcripts.record`) and the retention job exists now. See `docs/ARCHITECTURE.md` and the full scope doc.

## Privacy is a scored criterion — build it in Phase 1
- **Redact** phone numbers / Lebanese IDs / names **before** any model call.
- Store transcripts only temporarily. One anonymous `Metadata` row is written **per turn** by `data.transcripts.record` (from the route taken, no model call); the **retention job only deletes** the text + session hash. Do not add a second metadata writer.
- `user_ref` is always a **salted hash**, never a raw phone number.

## How we work (AI-driven, fast)
- **You only edit files inside your module folder** (see ownership below). The one shared file is `src/shared/contracts.py` — changing a type/signature there needs a heads-up in the team channel first.
- **Work on `main`, in small commits, one ticket each.** Before every push: `git pull --rebase`, then `PYTHONPATH=src pytest -q` must be green. Never force-push `main`. (Branches/PRs are optional — fine for a risky change.)
- **Announce in the team channel** any change to `src/shared/contracts.py` or `src/data/init/schema.sql`.
- **Demo freeze:** feature freeze Sun 10:00 — then tag `demo-freeze` and demo from that tag; only bug fixes after.
- **Definition of done = the ticket's "Done when" check passes** AND the smoke test is green.
- Build against `shared.contracts`. If your module isn't ready, the stubs in `core/stubs.py` keep the app running — don't edit stubs to fake features.

## Run & test
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
docker compose up -d                       # Postgres + pgvector (+ pg_trgm); schema auto-applies on a fresh volume
PYTHONPATH=src python -m data.db           # re-apply schema to an existing volume (idempotent)
cp .env.example .env                        # select the API vendor and fill its key
PYTHONPATH=src uvicorn core.app:app --reload   # backend + widget + channel routes at http://localhost:8000
PYTHONPATH=src python -m data.retention --loop  # deletes idle transcripts; without it nothing is ever deleted
PYTHONPATH=src pytest -q                     # must stay green. NEVER on the demo server: DB tests reload seeds + delete transcripts
```
Open `web/index.html` (or serve it) to use the chat widget.

## Layout & ownership (one owner per folder)
| Folder | Owner | What |
|--------|-------|------|
| `src/shared/` | A (steward) | Frozen contracts + config — changes reviewed by all |
| `src/core/`, `src/app` | **A** | FastAPI, pipeline, safety, router, grounding, LLM client |
| `src/ai/` | **B** | retrieval, embeddings, redaction, classifier, **transcription**, eval |
| `src/channels/`, `web/` | **C** | WhatsApp webhook, web widget, dashboard stub |
| `src/data/`, `infra/` | **D** | DB schema, directory/medicine/hotline data, retention job, deploy |

Healthcare teammate (5th): verifies procedures, writes the eval set, defines the topic list, leads the pitch.

## The contract between modules
Core depends only on the Protocols in `src/shared/contracts.py`. `core/providers.py` imports each real implementation if it exists, else a stub. To ship, expose exactly these names:
- B → `ai.retrieval.ProcedureSearchImpl`, `ai.redaction.redact`, `ai.classifier.classify`, `ai.transcribe.TranscriberImpl`
- D → `data.directory.DirectorySearchImpl`, `data.medicine.MedicineLookupImpl`
- A → `core.llm.AnthropicLLM` (primary Claude API), `core.llm_hosted.HostedLLM` (explicit alternate API)

Full detail: `docs/CONTRACTS.md`. Your tasks: `docs/tickets/dev-<you>.md`. Plan + timeline: `docs/PLAN.md`.

## Guardrails
- Never commit secrets — use `.env` (gitignored).
- Never log raw message text, phone numbers, or names.
- The model answers only from retrieved context; if nothing supports an answer, return the hotline fallback — do not guess.
