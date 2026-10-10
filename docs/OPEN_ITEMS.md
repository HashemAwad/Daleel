# Open items — what is missing, and from whom

Maintained by Dev D. Last updated Sat 10 Oct, after D5 and Dev B's B1–B4. Each item says who owns it and what breaks without it.
Status is as read from `main` at that time — check the code before assuming an item is still open.

## Dev A — core (`src/core`)
| # | Missing | Why it matters | Where |
|---|---------|----------------|-------|
| A1 | Render a missing price as "price not available", not `price None LBP` | Most drug rows have no price; the model may improvise "free" or a number | `core/prompts.py` `build_context` |
| A2 | System prompt: when several `[medicine]` records come back, ask "which one?" and quote no price | The lookup returns several products *without* prices on purpose; the model must not pick one | `core/prompts.py` |
| A3 | **Blocks the directory demo.** Router passes no place to `directory.nearest(kind)` | One-line fix in `run_tool`: `providers.directory.nearest(_directory_kind(inq.text), caza=inq.text)`. `caza` accepts the whole sentence; D resolves the caza or town from it. Without it every directory question gets the 1787 fallback | `core/router.py:62` |
| A4 | ~~Nothing writes the `transcripts` table~~ **Done by D (owner approved):** `pipeline.handle` now calls `data.transcripts.record(inq, answer)` after every turn, early returns included | — | `core/pipeline.py` |
| A5 | ~~Redaction flag~~ **No longer needed:** `record()` runs the redactor plus its own number/email scrub, and stores text only when `STORE_TRANSCRIPT_TEXT=1` | — | — |
| A6 | `/chat` still accepts a client-supplied `user_ref`, default `"anon"` | All such users share one session that never goes idle, so retention never fires for them. C now mints ids at `GET /api/session`; core should reject or replace `"anon"` | `core/app.py:29` |
| A7 | No Arabizi price words in the router ("se3er", "adde", "kam") | "kam se3er el nexium 40" goes to procedure search, never to the medicine lookup | `core/router.py` `MEDICINE_TERMS` |
| A8 | `"dose"` / `"mg of"` refuse before routing | "price of 5 mg of concor" is refused as dosing advice | `core/safety.py` `ADVICE_TERMS` |
| A9 | Stub medicine returns `price=0.0` | Reads as "free" if the stub is ever live | `core/stubs.py` |
| A13 | Facility wording: say "3 of N pharmacies in Aley, not ranked by distance"; never call a hospital "public" | Results are ordered by town then name, not distance; the source has no public/private flag | `core/prompts.py` |
| A10 | When `directory.nearest` returns `[]` (no location given), ask the user for their town. `data.directory.resolve_caza(text)` returns `None` in that case and never raises | Otherwise the reply is the generic "no official answer" | `core/pipeline.py` |
| A11 | Facility answers need "opening hours and stock not confirmed — call before going" and "© OpenStreetMap contributors" | We have no hours data; OSM data is ODbL | `core/prompts.py` |
| A12 | Do **not** add another `metadata` write | `data.transcripts.record` writes exactly one row per turn; a second writer would double-count | pipeline |
| A14 | The hotline fallback overwrites the tool (`tool="hotline"`) | An unanswered pharmacy or price question is counted under topic `other`, so the dashboard cannot say *what* went unanswered. Keep the routed tool on the fallback `Answer` | `core/pipeline.py` `_fallback` |
| A16 | `OllamaLLM.available()` is true when the Ollama server is up, even with **no model pulled** | The app then picks Ollama, every model call fails, and every `/chat` reply becomes the 1787 fallback. Check that the configured model is present, else fall back to the stub | `core/llm_ollama.py` |
| A15 | Nothing sets `Inquiry.lang` / `Answer.lang` | `metadata.lang` is empty, so the dashboard's language mix is empty | pipeline / channels |

## Dev B — AI (`src/ai`) — B1–B4 landed (ingest, search, redaction, voice); classifier not yet
| # | Missing | Why it matters |
|---|---------|----------------|
| B1 | Confirm the embedder is 1024-dim (bge-m3) | `procedures.embedding` is `vector(1024)`; any other size fails on insert |
| B2 | ~~`ai.redaction.redact`~~ **Landed.** It masks phones, IDs, emails and *introduced* names ("my name is …"); a bare name mid-sentence is not masked | Stored transcript text can still contain a name |
| B3 | `ai.classifier.classify` must return closed vocabulary only | `metadata` has CHECK constraints: `topic`/`subtopic` match `^[a-z_]{1,40}$`, `caza` must be a `cazas.name_en` or null |
| B5 | Redaction must not mask place names (Aley, Saida, Sour…) as if they were personal names | The directory lookup receives the *redacted* sentence; a masked place means no result |
| B4 | Eval set should include medicine near-misses | Concor 5 vs 10, Concor vs Concor Plus, a bare brand name, a drug we don't have (Lipitor) — expected answer is the right strength, "which one?", or the hotline |

## Dev C — channels (`src/channels`, `web`)
| # | Missing | Why it matters |
|---|---------|----------------|
| C1 | Dashboard should hide cells with fewer than 5 conversations | topic + caza + day can identify one person in a small district |
| C3 | Real topic values are `procedures`, `directory`, `drug_price`, `emergency`, `dosing_request`, `other` | The dashboard's mock rows use other names (`pharmacy_locator`, `hospital_admission`) |
| C4 | The dashboard shows mock rows only while `metadata` is empty | After the first real turn it shows just the real rows; the demo reset (D7) will seed realistic ones |
| C2 | Credit line "© OpenStreetMap contributors" wherever facilities are shown | ODbL licence condition |

## Healthcare teammate
| # | Missing | Why it matters |
|---|---------|----------------|
| H1 | Call each hotline and record the date. **1214's purpose is unconfirmed** | `hotlines.verified_on` is empty for all four |
| H2 | The fixed topic list for metadata (suggest adding mental-health and emergency) | Retention validates against it |
| H3 | Approve Arabic-script brand spellings (بنادول → Panadol, …) | `data.medicine.ALIASES` is empty until then, so Arabic-script drug names go to the hotline |
| H4 | Which drugs are free, and under what condition | `is_free` is unset on every row; the AMAN list looks like the ministry-dispensed set but nobody has confirmed it |
| H5 | Spot-check ~30 drug rows against the official list (name, strength, form, price) | Prices were fetched 10 Oct from the MoPH database search |
| H6 | A list of PHCs we can load (name, caza, address, phone) | The PHC network PDF in `data_source/` does not extract; "nearest PHC" returns nothing |

## Whoever runs the app (deploy / demo)
- **`SESSION_HASH_SALT` must be set to a real value in `.env`.** With the default `change-me`, no transcript rows are stored at all (metadata still is).
- `STORE_TRANSCRIPT_TEXT=1` to keep scrubbed text for the demo; default is off (rows stored with `[not stored]`).
- Start the retention loop: `PYTHONPATH=src python -m data.retention --loop` (`RETENTION_INTERVAL_SECONDS`, default 600; use ~20 for the demo). A compose service comes with D6.
- Scrubbing masks phone numbers, long digit runs and emails — **not names** until Dev B's redactor lands. Demo input should contain a phone number, not a name.
- Emergency and refusal turns never store text. Voice-note turns store no user text (the transcript is produced inside the pipeline).
- Pitch wording: "temporary, masked, auto-deleted from our live database", not "keeps no transcripts".

## Data gaps (Dev D) — known, not blocking
- Drug coverage: 30 common brands (first page of results each) + three ministry lists. 96 of 403 rows have a price. Common drugs such as Lipitor are absent. A single match can be the only form we fetched (Ventolin = nebuliser solution).
- No `list_date`: the MoPH search page states none. Only the date we checked is stored.
- Directory: places resolve by caza name (any spelling) or by a town's first word as OSM spells it (Choueifat, Jounie/Jounieh, Achrafieh). Neighbourhoods not in the data (Hamra, Dahieh), regions ("the south") and Arabic-script town names do not resolve. `lat`/`lon` are ignored; nothing is ranked by distance. "clinic" / "مركز" map to `phc`, and no PHCs are loaded.
- Pharmacies have no phone numbers or opening hours (OSM has none). The scope's user story promises a phone number per entry.
- `data_source/` is untracked and not in `.gitignore`.
- `README.md:12` and `docs/GETTING_STARTED.md:20` still say "PostGIS".

## Dev D — still to build
D6 deploy (incl. retention loop service) · D7 demo reset (incl. seeding metadata). (D0–D5 done.)
