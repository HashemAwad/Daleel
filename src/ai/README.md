# /src/ai — Member B (AI & retrieval)

Your folder. Build these classes/functions; `core/providers.py` auto-picks them up.

| File | Must expose | Contract |
|------|-------------|----------|
| `retrieval.py` | `class ProcedureSearchImpl` with `.search(query, lang, k)` | `ProcedureSearch` |
| `redaction.py` | `def redact(text) -> str` | removes phone / Lebanese ID / names |
| `classifier.py` | `def classify(transcript) -> Metadata` | fixed topic list |
| `transcribe.py` | `class TranscriberImpl` with `.transcribe(audio, mime)` | `Transcriber` (voice notes) |
| `ingest.py` | CLI to load procedure pages into the vector table | — |
| `eval.py` | runs the eval set, prints pass rate | — |

Import types from `shared.contracts`. Full ticket: `docs/tickets/dev-b.md`.
