# Open items — what is missing, and from whom

Maintained by Dev D. Last updated Sat 10 Oct, after D3. Each item says who owns it and what breaks without it.
Status is as read from `main` at that time — check the code before assuming an item is still open.

## Dev A — core (`src/core`)
| # | Missing | Why it matters | Where |
|---|---------|----------------|-------|
| A1 | Render a missing price as "price not available", not `price None LBP` | Most drug rows have no price; the model may improvise "free" or a number | `core/prompts.py` `build_context` |
| A2 | System prompt: when several `[medicine]` records come back, ask "which one?" and quote no price | The lookup returns several products *without* prices on purpose; the model must not pick one | `core/prompts.py` |
| A3 | Router passes no caza / lat / lon to `directory.nearest(kind)` | "pharmacy in Aley" cannot work until the router calls `data.directory.resolve_caza(text)` (ships with D4) | `core/router.py:19` |
| A4 | Nothing writes the `transcripts` table | The retention job (privacy demo) has nothing to delete. D will ship `data.transcripts.log_turn(...)` with D5; the pipeline has to call it, **after redaction** | `core/pipeline.py` |
| A5 | No way to tell whether redaction is real or the identity stub | If `ai.redaction` fails to import, raw text would be stored. Needs a flag such as `providers.REDACTION_REAL` so storage is skipped when it is false | `core/providers.py` |
| A6 | `/chat` still accepts a client-supplied `user_ref`, default `"anon"` | All such users share one session that never goes idle, so retention never fires for them. C now mints ids at `GET /api/session`; core should reject or replace `"anon"` | `core/app.py:29` |
| A7 | No Arabizi price words in the router ("se3er", "adde", "kam") | "kam se3er el nexium 40" goes to procedure search, never to the medicine lookup | `core/router.py` `MEDICINE_TERMS` |
| A8 | `"dose"` / `"mg of"` refuse before routing | "price of 5 mg of concor" is refused as dosing advice | `core/safety.py` `ADVICE_TERMS` |
| A9 | Stub medicine returns `price=0.0` | Reads as "free" if the stub is ever live | `core/stubs.py` |
| A10 | When `directory.nearest` returns `[]` (no location given), ask the user for their town | Otherwise the reply is the generic "no official answer" | `core/pipeline.py` |
| A11 | Facility answers need "opening hours and stock not confirmed — call before going" and "© OpenStreetMap contributors" | We have no hours data; OSM data is ODbL | `core/prompts.py` |
| A12 | Do **not** write a `Metadata` row per turn | The retention job is the only writer, or the dashboard double-counts. `CLAUDE.md` still says "every turn writes a Metadata row" | `CLAUDE.md`, pipeline |

## Dev B — AI (`src/ai`) — nothing pushed yet
| # | Missing | Why it matters |
|---|---------|----------------|
| B1 | Confirm the embedder is 1024-dim (bge-m3) | `procedures.embedding` is `vector(1024)`; any other size fails on insert |
| B2 | `ai.redaction.redact` | Until it exists the pipeline uses the identity stub: nothing is redacted |
| B3 | `ai.classifier.classify` must return closed vocabulary only | `metadata` has CHECK constraints: `topic`/`subtopic` match `^[a-z_]{1,40}$`, `caza` must be a `cazas.name_en` or null |
| B4 | Eval set should include medicine near-misses | Concor 5 vs 10, Concor vs Concor Plus, a bare brand name, a drug we don't have (Lipitor) — expected answer is the right strength, "which one?", or the hotline |

## Dev C — channels (`src/channels`, `web`)
| # | Missing | Why it matters |
|---|---------|----------------|
| C1 | Dashboard should hide cells with fewer than 5 conversations | topic + caza + day can identify one person in a small district |
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

## Data gaps (Dev D) — known, not blocking
- Drug coverage: 30 common brands (first page of results each) + three ministry lists. 96 of 403 rows have a price. Common drugs such as Lipitor are absent. A single match can be the only form we fetched (Ventolin = nebuliser solution).
- No `list_date`: the MoPH search page states none. Only the date we checked is stored.
- Pharmacies have no phone numbers or opening hours (OSM has none). The scope's user story promises a phone number per entry.
- `data_source/` is untracked and not in `.gitignore`.
- `README.md:12` and `docs/GETTING_STARTED.md:20` still say "PostGIS".

## Dev D — still to build
D4 directory search + `resolve_caza` · D5 `log_turn` + retention job · D6 deploy · D7 demo reset.
