# Engineering Review & Hardening Plan

Goal: a platform that **answers accurately** (not fallback-to-call), is **demo-ready**, and is **deployable for real usage**. This is an honest audit of the current system and the plan to get there. No sugar-coating.

## Verdict first
The **design is sound** — modular monolith, clean contracts, grounding gate, safety rails, thoughtful multi-script redaction, a properly-calibrated vector retrieval, a clean DB schema. The reasons the bot "falls back" are **operational and quality gaps, not architecture**:
1. The procedure knowledge base is **empty** and its search libraries aren't installed.
2. The answer model (3B) is **too small** for accurate Arabic.
3. There's **no conversation memory**, so multi-turn breaks.
4. It's **local-only** (per-laptop DB + local model) — fine for a demo, not yet deployable.

Fix those four and the "falling back" problem is largely solved.

---

## Problems, by severity

### P0 — directly causes "no answer / falls back" (fix for an accurate demo)
| # | Problem | Evidence | Root cause |
|---|---------|----------|------------|
| 1 | **Procedures never loaded** — every "how do I…" fails | `procedures` table = 0 rows | ingestion never run; `sentence_transformers`/`trafilatura` not installed |
| 2 | **Answer model too weak** — wrong language, rambling, mild hallucination ("use Google Maps", "الوزارة herself") | observed in live tests | qwen **3B**; too small for reliable Arabic/Arabizi |
| 3 | **No conversation memory** — "which town?" → "Beirut" doesn't connect | pipeline is stateless per request | no session state |

### P1 — accuracy & robustness (fix before we trust it)
| # | Problem | Impact |
|---|---------|--------|
| 4 | **Routing is brittle** — keyword lists + small-model classify, Arabizi patched ad-hoc; Arabizi town names ("tarablos") unresolved | misroutes → fallback |
| 5 | **Medicine data completeness** — many drugs have NULL price → "call 1787" | looks like a failure to the user |
| 6 | **No accuracy measurement** — we can't prove "accurate" | can't tune or defend it to judges |
| 7 | **Flaky test isolation** — C's metrics test fails whenever the DB has real rows | breaks the green-tests contract for everyone |
| 8 | **Channels not mounted in the main app** — `/dashboard`, `/join` 404 under `core.app` | WhatsApp/dashboard only run via a separate entrypoint |

### P2 — deployment & real usage (fix to go beyond one laptop)
| # | Problem | Impact |
|---|---------|--------|
| 9 | **Per-laptop database** — data loaded on one machine isn't on others | no shared truth; demo must be one machine |
| 10 | **Local Ollama model** — runs on a laptop, not a server | not reachable for real users |
| 11 | **No public deployment** (D6) + **no Twilio creds** | WhatsApp can't reach us; no real traffic |
| 12 | **Privacy at scale** — retention job must run on a schedule in prod, not manually | privacy is scored + a real obligation |

---

## Root causes (the few things behind most symptoms)
- **The data pipeline was built but never operated** (procedures). → run it with real content.
- **Heavy downloads vs a flaky network** (embedding model, bigger LLM). → manage with background auto-retry + a working baseline that doesn't block on them.
- **Local-first infra** chosen for speed. → good for demo; needs a hosted DB + served model for deployment.
- **No evaluation loop** → we're tuning blind. → build a small labelled question set and measure pass-rate.

---

## The plan (phased, each step has a measurable "done")

### Phase 0 — Accurate demo, no network dependency (do now)
Everything here works offline/guaranteed; nothing waits on a big download.
- **0.1 Load REAL procedure content.** Fetch actual MoPH/UNHCR pages (small HTML, not GB) and store the cleaned text. Embedding column is nullable, so text lands even without the ML model. *Done = `procedures` has rows from real sources.*
- **0.2 Hybrid retrieval (proper, not a hack).** Vector search when the embedding model is present; **lexical search (Postgres full-text / `pg_trgm`) as the fallback** so procedures answer today and auto-upgrade to semantic later. *Done = "how do I renew the chronic-med booklet?" returns the real page with its source link.*
- **0.3 Conversation memory.** Minimal per-session context so a town answer completes the prior question. *Done = "nearest pharmacy" → "which town?" → "Beirut" returns pharmacies.*
- **0.4 Prompt hardening.** Enforce: answer only from context, reply in the user's language/script, be concise, never invent. *Done = Arabic question → Arabic answer, grounded, with source.*
- **0.5 Wire channels into the app** (`register(app)`), fix the flaky metrics test. *Done = `/dashboard`, `/join` work; full suite green regardless of DB contents.*

### Phase 1 — Quality upgrade (background downloads, auto-retry)
- **1.1 Bigger model** (qwen 7B — downloading now; Aya 8B optional) for better Arabic. *Done = side-by-side answers clearly better; flip via one `.env` line.*
- **1.2 Semantic retrieval** (install `sentence_transformers` + bge-m3, embed the ingested pages). *Done = Arabizi query matches Arabic page content.*
- **1.3 Evaluation set** — 40–60 labelled questions (healthcare teammate), run on every change. *Done = a pass-rate number we can put on a slide and improve.*

### Phase 2 — Deployment & real usage
- **2.1 Hosted Postgres** (one shared DB, not per-laptop) with the schema + data loaded once.
- **2.2 Served model** — run Ollama/vLLM on a small server (or a always-on machine) so it's not tied to a laptop.
- **2.3 Public HTTPS URL** (D6) + **Twilio credentials** → WhatsApp live for real numbers.
- **2.4 Scheduled retention job** running in prod (privacy obligation), verified end-to-end.
- **2.5 Observability** — basic logging/metrics (no PII) so we can see usage and failures.

---

## Decisions needed to proceed cleanly
1. **Scope/timeline:** "excellent demo this weekend, with deployment designed-in" vs "must be publicly deployed now." This changes how much Phase 2 we do before Sunday.
2. **Retrieval:** approve the **hybrid** approach (lexical now, semantic when downloads land) — it's the robust choice under a flaky network.
3. **Deployment target (for Phase 2):** where does it run for real usage? (a cloud VM + managed Postgres is the usual answer) — needed before we can do 2.1–2.3.

Once these are set, Phase 0 starts immediately (it's all safe/offline) and the big downloads continue in the background for Phase 1.
