# Daleel — Project Status (A–Z)

Snapshot of what's built, how to test it, and what's left. **103 tests passing on `main`.**

---
## 1. How to run the whole thing (test setup)
```bash
# one-time
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
#   install Ollama + a model (free local LLM):
ollama pull qwen2.5:7b        # finish the in-progress demo model (~4.7 GB)

# each session
docker compose up -d                      # Postgres (pgvector) — the data lives here
PYTHONPATH=src python -m data.loaders     # load seed data (once / after a reset)
PYTHONPATH=src uvicorn core.app:app --reload     # backend + web widget at :8000
PYTHONPATH=src pytest -q                   # 103 passing

# to also get WhatsApp + dashboard routes (until the 1-line wire-up below lands):
PYTHONPATH=src uvicorn channels.asgi:app --reload
```
Open **http://localhost:8000** for the chat widget. Set `.env` to `selfhost` + `qwen2.5:7b` for local inference.

---
## 2. What works TODAY (by question type) + how to test
Type these in the web widget (or `curl localhost:8000/chat -H 'content-type: application/json' -d '{"text":"…","user_ref":"t"}'`):

| Ask | Expect | Status |
|-----|--------|--------|
| `nearest hospital in Aley` | real hospitals (Al Iman, Al Ghanem…) | ✅ works |
| `nearest pharmacy in Beirut` | real pharmacies | ✅ works |
| `how much does panadol cost?` | finds the drug; says call 1787 if no price | ✅ works |
| `my father is not breathing` | emergency → **call 140** | ✅ works |
| `what dose of panadol for my baby?` | refuses advice → pharmacist/1214 | ✅ works |
| `price of unicorn tears` | "no official answer… call 1787" (won't invent) | ✅ works |
| `how do I renew the chronic-medication booklet?` | currently "no official source… 1787" | ⏳ needs B to load procedures |
| a WhatsApp voice note | currently placeholder transcript | ⏳ needs B's real transcription |

**Why procedures fall back:** the procedure documents aren't loaded yet (that's B). The model (qwen) can *talk*, but it's only allowed to answer from loaded official sources — and there are 0 procedures in the DB. Medicines/pharmacies work because D loaded that data (403 drugs, 1,160 facilities, 4 hotlines, 0 procedures).

---
## 3. What A (you) did — Dev A, core backend  ✅ COMPLETE
All in `src/core` + `src/shared`. Verify all at once: `PYTHONPATH=src pytest -q`.

| Ticket | What it does | How to verify |
|--------|--------------|---------------|
| A0 | Froze the shared contracts (types every module uses) | `python -c "import sys;sys.path.insert(0,'src');from shared.contracts import Inquiry,Answer;print('ok')"` |
| A1 | FastAPI backend: `/chat`, `/health`, serves the widget at `/` | `curl localhost:8000/health` → `{"ok":true}` |
| A2 | LLM client — **free local qwen via Ollama** (no key, no cost); Anthropic path optional | ask any question → a written answer (not `[stub answer]`) |
| A3 | Grounding gate — no source ⇒ 1787 fallback, never guesses | `curl … '{"text":"price of unicorn tears"…}'` → fallback, `grounded:false` |
| A4 | Tool router — keyword-first (reliable on the small model), model for ambiguous | `pytest -k router` |
| A5 | Safety rules — emergency→140, dosing→refuse, in AR/Arabizi/FR/EN | `pytest -k "emergency or advice"` |
| A6 | Voice + redaction wired into the pipeline (calls B's pieces) | `pytest -k voice` |
| A4/A7 | Integration: pass the town (caza) to D's directory search | `curl … '{"text":"nearest hospital in Aley"…}'` → real hospitals |
| — | Pipeline degrades gracefully if the model/DB is down (no crashes) | — |

---
## 4. What the other members did

### B — AI & retrieval (`src/ai`)  🟡 JUST STARTED
- ✅ **B0** — DB connectivity (`retrieval.py`: ping, count procedures).
- ⏳ **B1** load real procedure pages, **B2** vector search → *this unblocks procedure answers (the headline feature)*.
- ⏳ **B3** real redaction (currently a pass-through stub), **B4** real voice transcription (stub), **B5** metadata classifier, **B6** prompt tuning + eval set.
- Test when done: `PYTHONPATH=src python -m ai.ingest` then ask a procedure question.

### C — Channels & frontend (`src/channels`, `web`)  ✅ MOSTLY DONE
- ✅ Web chat widget (RTL, 4 languages, quick replies, source badges).
- ✅ WhatsApp webhook (`whatsapp.py`, Twilio signature check), salted-hash identity, voice-note intake, render/split logic.
- ✅ Phase-2 dashboard stub (`/dashboard`) + metrics endpoint + QR join page.
- ⏳ Needs **Twilio sandbox credentials** in `.env` to run WhatsApp live. Web works now.
- Test: `PYTHONPATH=src uvicorn channels.asgi:app --reload`, open `/` and `/dashboard`.

### D — Data & infra (`src/data`, `infra`)  ✅ ~70%
- ✅ **D0** schema (9 tables, pgvector), **D1** db helper, **D2** seeds + loaders, **D3** medicine lookup, **D4** directory search + caza resolution.
- ✅ Loaded: 403 drugs, 1,160 facilities, 4 hotlines, 26 cazas.
- ⏳ **D5 retention job** (extract metadata → delete transcripts) — *privacy is a scored criterion*, **D6** deploy to public URL, **D7** demo reset script.
- Test: `pytest -k "medicine or directory or schema"` (needs DB up).

---
## 5. Integration state (what's wired vs not)
| Link | State | Action |
|------|-------|--------|
| core ← B/D real modules | ✅ auto via `core/providers.py` | none — picks them up on push |
| router → D directory (caza) | ✅ wired | done |
| **core app ← C channel routes** | ❌ **not wired** | A adds one line to `core/app.py`: `from channels import register; register(app)` |
| pipeline → B redaction/voice | ✅ wired (uses stubs until B ships) | none |
| retention job running | ❌ not built | D (D5) |

---
## 6. What's still needed — critical path to a demo (priority order)
1. **B: load procedures + vector search (B1/B2)** — biggest gap; without it the signature "how do I get X" demo fails.
2. **D: retention job (D5)** + **B: real redaction (B3)** — privacy is explicitly scored.
3. **A: wire C's routes** — one line in `core/app.py` so WhatsApp + dashboard run in the main app. Then **someone adds Twilio creds**.
4. **B: real voice transcription (B4)** — voice was called a core feature.
5. **D: deploy to a public HTTPS URL (D6)** so Twilio's webhook can reach it.
6. **B: eval set + prompt tuning (B6)** — for a pass-rate number on a slide; consider a bigger model (7B/Aya) for better Arabic.

**Overall: ~60–65% to a solid demo.** Skeleton + 3 of 4 question types work with real data. Remaining weight is mostly on **B** (procedures, voice, redaction) and **D's retention job**.

---
## 7. Known limitations (say these honestly)
- The demo local model is **qwen2.5:7b** because its download was already halfway complete when the model decision was reviewed. Qwen3 8B is the recommended post-demo comparison candidate, not a blocker today. If the model is down, the bot answers from verified data using the plain renderer.
- Pharmacy data may be partly synthetic (per the plan) — label it in the demo.
- We delete transcripts on our side only; WhatsApp/the user's phone keep their copies.
