# Dev B — AI & retrieval (+ voice notes)

You own `src/ai/`. You expose classes/functions that `core/providers.py` auto-detects. **Your independence: high.** Your only real prerequisite is D's `procedures` table schema (S0). Until it exists you seed a few rows yourself. Everything else you build and test in isolation; the stub layer stands in for you in the app until you push.

Branch per ticket: `feat/b/<ID>`. Done = the check passes **and** `PYTHONPATH=src pytest -q` is green.

---
### B0 · Confirm you can read the DB — Sprint 0 · **Hard-dep: D's schema.sql**
After D publishes `src/data/init/schema.sql` and `docker compose up -d`, connect and read the `procedures` table (empty is fine).
**Unblock meanwhile:** create a tiny local `procedures` table yourself with 2 rows so you're never waiting.
**Done when:** `ai/retrieval.py` connects and runs a `SELECT` without error.

### B1 · Procedure ingestion — Sprint 1–2 · **Independent** (needs schema only)
`ai/ingest.py`: fetch 2–3 verified MoPH procedure pages (healthcare teammate picks them), clean, chunk ~300–500 words, embed, insert into `procedures` with `url`, `title`, `lang`, `checked_on`.
**Done when:** `python src/ai/ingest.py` loads rows; `SELECT count(*) FROM procedures` > 0.

### B2 · Vector search — Sprint 1–2 · **Independent**
`ai/retrieval.py`: `class ProcedureSearchImpl.search(query, lang, k)` → embed query, pgvector nearest-neighbour, return `[Doc]` with `source` + `score`. Use a multilingual embedder (e.g. bge-m3) so Arabizi matches AR/FR text.
**Done when:** `ProcedureSearchImpl().search("كيف آخذ دوا السرطان")` returns a relevant `Doc`; and `/chat` now returns a real procedure answer (providers auto-picks it up).

### B3 · Redaction — Sprint 2–3 · **Independent**
`ai/redaction.py`: `def redact(text) -> str` removes phone numbers, Lebanese ID patterns, and obvious names before the model sees text.
**Done when:** `redact("أنا محمد رقمي 70123456")` returns text with the number masked; add `tests/test_redaction.py`.

### B4 · Voice-note transcription — Sprint 3 · **Independent** (core feature — protect the time)
`ai/transcribe.py`: `class TranscriberImpl.transcribe(audio, mime) -> (text, lang)`. Use Whisper (local `faster-whisper`) or a hosted STT; must handle Arabic + French audio. C hands you bytes; you return text + detected language.
**Done when:** a sample AR voice clip transcribes to correct text; `/chat` with that text produces the right answer. Add `tests/test_transcribe.py` with a short fixture.

### B5 · Metadata classifier — Sprint 4 · **Independent** (D calls it; stub covers D meanwhile)
`ai/classifier.py`: `def classify(transcript) -> Metadata` using the fixed topic list from the healthcare teammate (coverage, referral/admission, chronic-med, acute-med, procedures, directory, other). **Output must contain no free text/numbers/names.**
**Done when:** classifying a sample transcript returns a valid `Metadata`; `tests/test_classifier.py` asserts no raw PII leaks into fields.

### B6 · Prompts + eval set runner — Sprint 3–5 · **Independent**
Refine `core/prompts.py` wording with A (grounding, 4 languages, citations). Build `ai/eval.py` to run the healthcare teammate's 40–60 Q&A set and print a pass rate.
**Done when:** `python src/ai/eval.py` prints a pass-rate number you can put on a slide.

**Agent kickoff prompt:**
> You are working ONLY in `src/ai/` of the Daleel repo. Read `CLAUDE.md`, `docs/CONTRACTS.md`, and `docs/tickets/dev-b.md`. Implement ticket B<N>, importing types from `shared.contracts`. Expose exactly the class/function names in `docs/CONTRACTS.md` so `core/providers.py` auto-detects them. Don't touch other folders. Run `PYTHONPATH=src pytest -q` before finishing; keep it green.
