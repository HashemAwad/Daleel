# Integration contracts

The single source of truth is `src/shared/contracts.py`. This page explains it so each agent can implement against it without reading anyone else's code.

## Rule
Adding an **optional** field to a model is safe. **Renaming or removing** a field, or changing a **Protocol signature**, can break another module — post in the channel and get a quick +1 first.

## Data models (Pydantic)
- **`Inquiry`** `{id, channel, text, lang?, user_ref, audio_url?}` — normalised inbound message. Channels build it; core consumes it. `user_ref` is a salted hash. `audio_url` set for voice notes.
- **`Doc`** `{id, title, content, source?, lang?, score?}` — a retrieved procedure passage. `source = {title, url, checked_on}`.
- **`Facility`** `{id, name, type, caza?, address?, phone?, lat?, lon?, distance_km?}`.
- **`DrugRecord`** `{name, price?, currency, generics[], is_free?, list_date?}`.
- **`Hotline`** `{name, number, purpose}`.
- **`ToolResult`** `{tool, docs[], facilities[], drugs[], hotlines[]}` — what a tool returns; `.is_empty()` drives the grounding fallback.
- **`Answer`** `{text, sources[], tool, grounded, outcome, lang?}` — what `/chat` returns. `outcome ∈ answered|unanswered|escalated|refused|emergency`.
- **`Metadata`** `{topic, subtopic?, caza?, lang?, outcome, day}` — the ONLY thing that survives a conversation. No free text, numbers, or names.

## Interfaces (Protocols) — who implements what
| Protocol | Method | Owner | Real class/fn (providers.py looks for this) |
|----------|--------|-------|---------------------------------------------|
| `LLMClient` | `generate(system, prompt, context)`, `classify(text, labels)`, `embed(texts)` | A | `core.llm.AnthropicLLM` |
| `Transcriber` | `transcribe(audio, mime) -> (text, lang?)` | B | `ai.transcribe.TranscriberImpl` |
| `ProcedureSearch` | `search(query, lang?, k) -> [Doc]` | B | `ai.retrieval.ProcedureSearchImpl` |
| `DirectorySearch` | `nearest(kind, caza?, lat?, lon?, k) -> [Facility]` | D | `data.directory.DirectorySearchImpl` |
| `MedicineLookup` | `find(name) -> [DrugRecord]` | D | `data.medicine.MedicineLookupImpl` |
| `redact` (fn) | `redact(text) -> text` | B | `ai.redaction.redact` |
| `classify` (fn) | `classify(transcript) -> Metadata` | B builds it. **Nothing calls it at runtime today**: metadata topics come from the route taken (`data.transcripts.topic`) | `ai.classifier.classify` |

## How integration happens (zero coordination)
`core/providers.py` does `try: import real … except: use stub`. The moment you push a module exposing the name above, core uses it — no one edits core. If your real class raises on import (missing dep/env), core silently keeps the stub, so a broken import never takes down the app.

## The DB schema is the other contract — D owns it
D publishes `src/data/init/schema.sql` in Sprint 0. Tables everyone else assumes:
`procedures(id, title, content, url, checked_on, lang, embedding vector(1024))` — bge-m3 dims, no vector index,
`facilities(id, name, type, caza, address, phone, lat, lon, + provenance)` — plain lat/lon, **no PostGIS**; `caza` must exist in `cazas`,
`drugs(name, price, currency, generics, is_free, list_date, + strength, form, provenance)` — `price` / `is_free` are NULL when unknown, never 0 / false,
`hotlines(name, number, purpose, + verified_on)`,
`transcripts(session_hash, turn, role, text, created_at, + outcome?, tool?, lang?)` — temporary; masked text or `[not stored]` (a bare name or an address is not masked),
`metadata(topic, subtopic, caza, lang, outcome, day)` — no id / timestamp / session key; `lang`, `outcome`, `caza` are closed sets, `topic` is a lowercase-word pattern.

Extra helper tables: `cazas`, `caza_aliases` (place spellings) and `drug_aliases` (unused today). Exact DDL: `src/data/init/schema.sql`.
Existing local volume? Re-apply with `PYTHONPATH=src python -m data.db` (idempotent). If you created your own `procedures` table by hand, drop it first.
B's `retrieval.py` reads `procedures`; C's dashboard reads `metadata`; `data.transcripts.record` writes one `metadata` row per turn (and the temporary `transcripts` rows); D's retention job only deletes `transcripts`.
