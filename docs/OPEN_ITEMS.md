# Open items — what is missing, and from whom

Maintained by Dev D. Last updated Sun 11 Oct, after the full review of D0–D7 and its fixes.
Status is as read from `main` at that time — check the code before assuming an item is still open.

## Dev A — core (`src/core`)
| # | Missing | Why it matters | Where |
|---|---------|----------------|-------|
| A1 | ~~Render a missing price as "price not available"~~ **Done by D (owner asked):** `build_context` no longer prints `price None` or `list None` | — | `core/prompts.py` |
| A2 | System prompt: when several `[medicine]` records come back, ask "which one?" and quote no price | The lookup returns several products *without* prices on purpose; the model must not pick one | `core/prompts.py` |
| A3 | ~~Router passes no place~~ **Done by A** (`467889a`): `run_tool` passes `caza=_resolve_caza(inq.text)` | — | — |
| A4 | ~~Nothing writes the `transcripts` table~~ **Done by D (owner approved):** `pipeline.handle` now calls `data.transcripts.record(inq, answer)` after every turn, early returns included | — | `core/pipeline.py` |
| A5 | ~~Redaction flag~~ **No longer needed:** `record()` runs the redactor plus its own number/email scrub, and stores text only when `STORE_TRANSCRIPT_TEXT=1` | — | — |
| A6 | `/chat` still accepts a client-supplied `user_ref`, default `"anon"` | All such users share one session that never goes idle, so retention never fires for them. C now mints ids at `GET /api/session`; core should reject or replace `"anon"` | `core/app.py:29` |
| A7 | No Arabizi price words in the router ("se3er", "adde", "kam") | "kam se3er el nexium 40" goes to procedure search, never to the medicine lookup | `core/router.py` `MEDICINE_TERMS` |
| A8 | `"dose"` / `"mg of"` refuse before routing | "price of 5 mg of concor" is refused as dosing advice | `core/safety.py` `ADVICE_TERMS` |
| A9 | Stub medicine returns `price=0.0` | Reads as "free" if the stub is ever live | `core/stubs.py` |
| A13 | Facility wording: say "3 of N pharmacies in Aley, not ranked by distance"; never call a hospital "public" | Results are ordered by town then name, not distance; the source has no public/private flag | `core/prompts.py` |
| A10 | ~~Ask for the town on an empty directory result~~ **Done by A** (`467889a`) | — | — |
| A11 | Facility answers need "opening hours and stock not confirmed — call before going" and "© OpenStreetMap contributors" | We have no hours data; OSM data is ODbL | `core/prompts.py` |
| A12 | Do **not** add another `metadata` write | `data.transcripts.record` writes exactly one row per turn; a second writer would double-count | pipeline |
| A14 | The hotline fallback overwrites the tool (`tool="hotline"`) | An unanswered pharmacy or price question is counted under topic `other`, so the dashboard cannot say *what* went unanswered. Keep the routed tool on the fallback `Answer` | `core/pipeline.py` `_fallback` |
| A17 | ~~The local model invents a source link on facility answers~~ **Done by A** (`c3b3fc3` strips URLs not in the tool result) | — | — |
| A18 | `/chat` has no length limit on `text` (`ChatIn`) | One very long message ties up the worker (regex + model). The server's proxy now caps requests at 64 KB; add `Field(max_length=2000)` | `core/app.py` |
| A19 | `providers.py` swaps in a stub silently, and the stubs return FAKE data (`StubMedicine` price 0.0, `StubDirectory` "Example pharmacy", `StubProcedureSearch` an invented procedure) | A typo or missing package in any module turns the bot into a fake one with no log line. Log at ERROR in each `except`, and make the stubs return `[]` so the hotline fallback fires. `infra/vm_setup.sh` now fails if a stub is live | `core/providers.py`, `core/stubs.py` |
| A20 | `/health/channels`, `/docs` and `/openapi.json` are public | They show configuration flags, the sender number and provider names | `core/app.py`, `channels/web.py` |
| A21 | `router.py` docstring says the model picks the tool; keywords do unless `MODEL_ROUTER=1` | Misleading for anyone reading it | `core/router.py:4` |
| A16 | `OllamaLLM.available()` is true when the Ollama server is up, even with **no model pulled** | The app then picks Ollama, every model call fails, and every `/chat` reply becomes the 1787 fallback. Check that the configured model is present, else fall back to the stub | `core/llm_ollama.py` |
| A15 | `Inquiry.lang` is set only for voice notes (from Whisper); typed text leaves it empty | `metadata.lang` is empty for typed turns, so the dashboard's language mix under-counts | pipeline / channels |

## Dev B — AI (`src/ai`) — B1–B5 landed (ingest, search, redaction, voice, classifier)
| # | Missing | Why it matters |
|---|---------|----------------|
| B1 | Confirm the embedder is 1024-dim (bge-m3) | `procedures.embedding` is `vector(1024)`; any other size fails on insert |
| B2 | ~~`ai.redaction.redact`~~ **Landed.** It masks phones, IDs, emails and *introduced* names ("my name is …"); a bare name mid-sentence is not masked | Stored transcript text can still contain a name |
| B3 | `ai.classifier.classify` must return closed vocabulary only | `metadata` has CHECK constraints: `topic`/`subtopic` match `^[a-z_]{1,40}$`, `caza` must be a `cazas.name_en` or null |
| B6 | `ai/classifier.py` docstring says the retention job calls it. Nothing calls it at runtime | Misleading; see H2 |
| B7 | `redact()` misses numbers written with doubled spaces, underscores or invisible direction marks (`03  123  456`, `03_123_456`), and its email pattern is slow on very long input | The MODEL sees those numbers (D's `scrub` only protects what is stored). Strip `[\u200b-\u200f]` first and allow up to 3 separators; bound the email quantifiers |
| B5 | Redaction must not mask place names (Aley, Saida, Sour…) as if they were personal names | The directory lookup receives the *redacted* sentence; a masked place means no result |
| B4 | Eval set should include medicine near-misses | Concor 5 vs 10, Concor vs Concor Plus, a bare brand name, a drug we don't have (Lipitor) — expected answer is the right strength, "which one?", or the hotline |

## Dev C — channels (`src/channels`, `web`)
| # | Missing | Why it matters |
|---|---------|----------------|
| C1 | ~~Hide dashboard cells under 5~~ **Done by C** (`channels/metrics.py` withholds groups under 5) | — |
| C5 | ~~Docs said to run `channels.asgi:app`~~ **Done by C** (`cd0304b`) | — |
| C3 | ~~Mock dashboard rows used other topic names~~ **Done by C** (`e7a4159`) | — |
| C4 | The dashboard shows mock rows only while `metadata` is empty | After the first real turn it shows just the real rows; the demo reset (D7) will seed realistic ones |
| C2 | ~~OSM credit line~~ **Done by C** (`web/index.html`, `channels/render.py`) | — |

## Healthcare teammate
| # | Missing | Why it matters |
|---|---------|----------------|
| H1 | Call each hotline and record the date. **1214's purpose is unconfirmed** | `hotlines.verified_on` is empty for all four |
| H2 | The fixed topic list for metadata (suggest adding mental-health) | Today topics come from a fixed map in `data.transcripts` (`procedures`, `directory`, `drug_price`, `emergency`, `dosing_request`, `other`); B's classifier has a different vocabulary and is not called |
| H3 | Approve Arabic-script brand spellings (بنادول → Panadol, …) | `data.medicine.ALIASES` is empty until then, so Arabic-script drug names go to the hotline |
| H4 | Which drugs are free, and under what condition | `is_free` is unset on every row; the AMAN list looks like the ministry-dispensed set but nobody has confirmed it |
| H5 | Spot-check ~30 drug rows against the official list (name, strength, form, price) | Prices were fetched 10 Oct from the MoPH database search |
| H6 | ~~A list of PHCs we can load~~ **Done by D** (11 Oct): 220 PHCs from the MoPH Health Facility Locator | — |
| H7 | **Decide the fallback number.** moph.gov.lb labels 1787 "Hotline for Health Services for Displaced Lebanese" and 1214 "MoPH Hotline" | The bot sends every unanswered question to 1787 (`core/pipeline.py`, `core/prompts.py`, `core/stubs.py`, `channels/whatsapp.py`, `web/index.html`). Call both, then A and C change the number in one commit |

## Deployment (as of Sat 10 Oct, evening)
- **The demo runs on a teammate's MacBook** with the already-downloading `qwen2.5:7b` and a tunnel: `bash infra/laptop_setup.sh`, then `bash infra/run_demo.sh`. Steps in `infra/SETUP.md`.
- Still to do on that laptop: Twilio values + `PUBLIC_BASE_URL` in `.env`, the Twilio webhook, and B's procedure ingestion.
- Fallback: the AWS VM built by `infra/vm_setup.sh`, using the smaller `qwen3:4b` when local inference is needed. Verify its URL and loaded procedures before relying on it.
- `bash infra/reset_demo.sh` before each rehearsal. It deletes all transcripts and metadata and inserts 320 **made-up** metadata rows marked `subtopic='sample'` so the dashboard is not empty.

## Whoever runs the app (deploy / demo)
- **`SESSION_HASH_SALT` must be set to a real value in `.env`.** With the default `change-me`, no transcript rows are stored at all (metadata still is).
- `STORE_TRANSCRIPT_TEXT=1` to keep scrubbed text for the demo; default is off (rows stored with `[not stored]`).
- **Never run `pytest` on the demo server** (the DB tests reload seed tables and delete idle transcripts; `DALEEL_ENV=production` makes the suite refuse). Use `REQUIRE_DB=1 pytest -q` on a laptop for the pre-demo run so a down database fails instead of skipping.
- Start the retention loop: `PYTHONPATH=src python -m data.retention --loop` (`RETENTION_INTERVAL_SECONDS`, default 600; use ~20 for the demo). `infra/run_demo.sh` starts it with the app; on the AWS server it is the `daleel-retention` systemd unit.
- Masked before storage: phone numbers, IDs, emails and names introduced as "my name is …" (B's redactor), plus a digit/email backstop (D's `scrub`). **Not masked: a bare name, an address, a spelled-out number.** Demo input should contain a phone number, not a name.
- Emergency and refusal turns never store text. Voice-note turns store no user text (the transcript is produced inside the pipeline).
- Pitch wording: "temporary, masked, auto-deleted from our live database", not "keeps no transcripts".

## Data gaps (Dev D) — known, not blocking
- Drug coverage (11 Oct): the whole MoPH database, 5,240 rows, 4,646 priced. Lipitor is not in the ministry's database at all. 345 products sold in several pack sizes have no price (the seed has no pack column). A bare brand name now matches more products, so "which one?" is asked more often.
- `list_date` is 2026-10-05 on 4,166 rows (confirmed against the dated MoPH price list), empty elsewhere.
- Procedures: 59 verified URLs in `src/data/seeds/procedure_urls.txt` for B to ingest on the demo laptop. No French pages exist; chronic-medication card, disability card and NSSF claims have no official page we could reach.
- Directory: places resolve by caza name (any spelling) or by a town's first word as OSM spells it (Choueifat, Jounie/Jounieh, Achrafieh). Neighbourhoods not in the data (Hamra, Dahieh), regions ("the south") and Arabic-script town names do not resolve. `lat`/`lon` are ignored; nothing is ranked by distance. "clinic" / "مركز" map to `phc`, and no PHCs are loaded.
- Pharmacies have no phone numbers or opening hours (OSM has none). The scope's user story promises a phone number per entry. PHCs (215 of 220) and 32 governmental hospitals now have one. New PHC and hospital rows have no coordinates and Arabic addresses.
- `README.md:12` and `docs/GETTING_STARTED.md:20` still say "PostGIS".

## Dev D — still to build
Nothing — D0–D7 are done. Follow-up: terminate the AWS server after the demo.
