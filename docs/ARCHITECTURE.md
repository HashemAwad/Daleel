# Architecture — Daleel (MoPH Health Assistant)

A health-information assistant for Lebanon's Ministry of Public Health, on **WhatsApp** and a **web widget**, answering in Arabic / Arabizi / French / English. It answers four question types — **procedures**, **directory** (nearest pharmacy/hospital/PHC), **medicines**, **hotlines/escalation** — always from a verified source, never from the model's memory.

- **Phase 1 (this weekend):** the chatbot.
- **Phase 2 (later):** ministry dashboard from anonymized metadata.
- **Privacy by design:** redact before any model call; each conversation's transcript is deleted after its metadata is extracted.

See the full scope doc for problem evidence, user stories, demo script, and risks.

## Approach: Modular Monolith
One repo, one FastAPI deployable, split into **one-owner folders** that talk only through **contracts in `/src/shared`**. The model never answers from memory — it calls a tool, and the reply is built from the tool result.

## Stack
- **Backend:** Python + FastAPI (one service, both channels).
- **DB:** Postgres + pgvector + PostGIS, one Docker container.
- **Model (demo):** hosted API with tool calling, behind an `LLMClient` interface; open-weight self-host is a config toggle.
- **Channels:** Twilio WhatsApp sandbox + React web widget (RTL).

## Layout & ownership
```
/src
  /shared     # contracts + config — reviewed by all, stewarded by A
  /core       # A: FastAPI wiring, normalize, safety rules, tool router, grounding, LLMClient
  /app        # A: composes modules into the running app
  /ai         # B: ingestion, embeddings, vector search, prompts, redaction, classifier, eval
  /channels   # C: WhatsApp webhook + signature, web chat REST
  /data       # D: schema/migrations, directory+drug tables, retention job, seeds
/web          # C: React chat widget (RTL) + dashboard stub
/infra        # D: Docker, deployment, demo reset, secrets
/data_sources # 5th teammate: curated/verified source datasets
```

## Members (CS team of 4; 5th is healthcare, non-CS)
| Member | Owns | Responsibilities |
|--------|------|------------------|
| A — Backend core | `/src/core`, `/src/app` | FastAPI service; normalize→safety→redact→route→ground→reply pipeline; `LLMClient` + hosted impl + self-host toggle; deterministic hotline routing |
| B — AI & retrieval | `/src/ai` | Procedure ingestion/embeddings; `ProcedureSearch`; prompts (4 langs, citations); `redact()`; metadata `classify()`; eval runner |
| C — Channels & frontend | `/src/channels`, `/web` | Twilio webhook + signature + quick replies; web chat endpoint; React RTL widget; dashboard stub |
| D — Data & infra | `/src/data`, `/infra` | Postgres/pgvector/PostGIS schema + migrations; `DirectorySearch` (PostGIS); `MedicineLookup`; hotline seed; retention job; deploy + demo reset + backup |
| Healthcare (5th) | `/data_sources` | Verify 5–8 procedures; eval questions; topic list; answer wording; pitch |

## Shared contracts (agree day 1, in `/src/shared`)
| Contract | Implemented by | Called by |
|----------|----------------|-----------|
| `Inquiry`, `Answer`, `Doc`, `ToolResult` (types) | — (shared) | all |
| `LLMClient.generate/classify/embed` | A | A |
| `ProcedureSearch.search(query, lang) -> list[Doc]` | B | A (router) |
| `DirectorySearch.nearest(type, caza/latlon) -> list[Facility]` | D | A (router) |
| `MedicineLookup.find(name) -> list[DrugRecord]` | D | A (router) |
| `redact(text) -> text` | B | A (pipeline) |
| `classify(transcript) -> Metadata` | B | D (retention job) |
| DB schema / migrations | D | B, C, D |

Build against these with other modules **stubbed** — nobody is blocked. First dependency to settle: D publishes the DB schema in the day-1 huddle so B and C can build against real table shapes.

## Per-turn flow (owner in parentheses)
message in (C) → normalize (A) → safety rules (A) → redact (B, via A) → tool router (A) → one of: ProcedureSearch (B) / DirectorySearch (D) / MedicineLookup (D) / Hotline (A) → grounding check (A) → reply out (C) → transcript stored → retention job (D) extracts metadata (B's classifier) → deletes text.
