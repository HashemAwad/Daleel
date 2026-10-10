# Daleel — Sprint plan, timeline & dependency map

Mode: **move fast, ship vertical slices.** Prioritise foundations + MVP; polish last. AI-driven: each dev drives their own agent inside their folder. The repo is wired so **after Sprint 0, all four work independently** against stubs and integrate automatically via `core/providers.py`.

## Are we independent? Yes — by design. Here's the one shared moment.
There is exactly **one hard, shared dependency: Sprint 0.** Two things must exist before anyone can go heads-down:
1. **`src/shared/contracts.py`** (already committed, owner A) — the types everyone imports.
2. **`src/data/init/schema.sql`** (owner D) — the DB tables B and C read/write.

After S0, nobody is blocked: the stub layer answers for any module that isn't done yet, so each of you builds and tests your slice alone and it "lights up" in the running app the moment you push. Cross-module needs are **soft dependencies** (work against a stub now, integrate later) — never blockers.

### Dependency map (read this before worrying about who's ahead)
| Need | Needed by | Type | How you're unblocked meanwhile |
|------|-----------|------|--------------------------------|
| `contracts.py` | everyone | **HARD (S0)** | Already in repo. Frozen. |
| `schema.sql` (D) | B (reads `procedures`), C (reads `metadata`) | **HARD (S0)** | D ships it first thing in S0; until then B seeds a few rows locally, C renders mock metadata |
| A's pipeline/`/chat` | C (calls it) | **SOFT** | `/chat` already runs on stubs — C integrates immediately |
| B's `ProcedureSearchImpl` | A's router | **SOFT** | `StubProcedureSearch` answers until B pushes |
| B's `redact()` | A's pipeline | **SOFT** | identity stub until B pushes |
| B's `TranscriberImpl` | C's voice flow | **SOFT** | `StubTranscriber` returns placeholder text until B pushes |
| B's `classify()` | D's retention job | **SOFT** | `stub_classify` returns a Metadata row until B pushes |
| D's `DirectorySearchImpl` / `MedicineLookupImpl` | A's router | **SOFT** | stubs answer until D pushes |
| D's `metadata` table rows | C's dashboard | **SOFT** | C renders mock rows until real data flows |

**Takeaway for your agent:** "Build against `shared.contracts`. If something you depend on isn't ready, the stub in `core/stubs.py` covers it — do not wait, do not edit the stub." This line is in `CLAUDE.md`.

## Timeline (Sat 10 Oct → Sun 11 Oct, submission closes **14:00 Sun**)
| Sprint | Window | Theme | Checkpoint (demo-able) |
|--------|--------|-------|------------------------|
| **S0** | now → Sat 15:30 | Foundations | Repo runs for all 4; `pytest` green; schema up; each dev's first file imports |
| **S1** | Sat 15:30 → 17:00 | First vertical slice | **One procedure answered end-to-end on the web widget, with a source link** |
| **S2** | Sat 17:00 → 20:00 | Real retrieval + real data + WhatsApp | Procedure RAG live; drug + 1 directory loaded; WhatsApp echoes a real answer |
| **S3** | Sat 20:00 → 23:00 | All 4 tools + safety + redaction + **voice** | All question types work; emergency/advice rules on; **voice note answered**; redaction on |
| **S4** | Sat 23:00 → Sun 02:00 | Privacy + deploy | Retention job deletes transcript & writes metadata; app on a public HTTPS URL |
| **S5** | Sun 02:00 → 09:00 | Phase-2 stub + eval + polish | Dashboard stub reads metadata; eval pass-rate on a slide; Arabizi/FR fixes |
| **S6** | Sun 09:00 → 14:00 | Freeze + demo | **Feature freeze 10:00**; backup video; 2 rehearsals; submit by 14:00 |

Rule: if a sprint slips >2h, **cut scope (fewer procedures / one directory), never the privacy pieces.** Sleep in shifts; keep 2 people awake overnight.

## MVP priority (if time runs out, this is the order)
1. `/chat` answers **one procedure** with a source on the **web widget** (S1). ← the demo's spine
2. WhatsApp delivers the same answer (S2).
3. Directory + medicine + hotline tools (S2–S3).
4. Safety rules + redaction (S3).
5. **Voice note** → transcription → answer (S3). *Core feature — protect its time.*
6. Retention job + deployment (S4).
7. Dashboard stub + eval (S5).

## Per-dev tickets
- A — backend core: `docs/tickets/dev-a.md`
- B — AI & retrieval (+ voice): `docs/tickets/dev-b.md`
- C — channels & frontend: `docs/tickets/dev-c.md`
- D — data & infra: `docs/tickets/dev-d.md`

Every ticket lists: goal, steps, **Independent? / Depends on**, and **Done when** (a command or action that proves it works).

## Checkpoints — how we prove a sprint is done
At each checkpoint boundary, on `main`:
1. `PYTHONPATH=src pytest -q` is green.
2. The checkpoint's demo action works live (see the table above).
3. Each dev posts a one-line status in the channel: ticket IDs merged + what's demo-able.
