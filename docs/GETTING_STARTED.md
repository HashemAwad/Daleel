# Getting started — setup & first moves

Everyone does Part 1 once. Then jump to your role in Part 2.

## Part 1 — One-time setup (all devs, ~10 min)
```bash
# 1. Clone and enter
git clone https://github.com/mariamelwirish/hack4health.git
cd hack4health

# 2. Python env + deps
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Secrets
cp .env.example .env                 # fill in ANTHROPIC_API_KEY (ask the team lead)

# 4. Database (needs Docker Desktop running)
docker compose up -d                 # Postgres + pgvector (+ pg_trgm) on :5432

# 5. Run the backend
PYTHONPATH=src uvicorn core.app:app --reload     # http://localhost:8000

# 6. Prove it works
PYTHONPATH=src pytest -q             # all green
curl -s localhost:8000/health        # {"ok":true,...}
```
Open `web/index.html` in a browser (or `python -m http.server -d web 5500`) and ask a question — you'll get a stubbed answer. **That means the repo is healthy and you can start.**

### Daily git flow (move fast, no collisions)
```bash
git checkout main && git pull
git checkout -b feat/<you>/<ticket-id>     # e.g. feat/b/B2-vector-search
# ...let your agent work ONLY inside your folder...
PYTHONPATH=src pytest -q                    # must stay green
git add -A && git commit -m "feat: B2 vector search"
git push -u origin feat/<you>/<ticket-id>   # open PR, get a quick +1, squash-merge
```
You edit only your folder (`CLAUDE.md` lists them). The app keeps running because missing modules fall back to stubs.

### How to drive your agent (AI-driven dev)
From the repo root, start Claude Code and paste your role's **kickoff prompt** (bottom of your ticket file). The agent reads `CLAUDE.md` automatically. Work one ticket at a time; after each, run `pytest -q` and open a PR.

## Part 2 — First moves by role
Each of you is independent after Sprint 0. Below is literally what to do in your first 30 minutes.

### Member A — backend core (`src/core`, `src/shared`)
1. Read `docs/tickets/dev-a.md`.
2. Announce **"contracts frozen"** in the channel (ticket A0) — this unblocks B/C/D.
3. Put a real `ANTHROPIC_API_KEY` in `.env`, start on **A2** (real LLM) so answers stop saying `[stub answer]`.
4. Kickoff prompt → ticket A1/A2.

### Member B — AI & retrieval + voice (`src/ai`)
1. Read `docs/tickets/dev-b.md`.
2. Wait for D's "schema is up" (usually minutes). Meanwhile seed 2 local `procedures` rows so you're never blocked (ticket B0).
3. Start **B1 (ingest)** → **B2 (vector search)**; the app shows real procedure answers the moment you push.
4. Protect time for **B4 (voice)** — it's a core feature.
5. Kickoff prompt → ticket B1.

### Member C — channels & frontend (`src/channels`, `web`)
1. Read `docs/tickets/dev-c.md`.
2. You're unblocked immediately — `/chat` already answers. Start on **C0/C1** (web widget, RTL).
3. Get Twilio sandbox creds into `.env` for **C2 (WhatsApp)**.
4. Kickoff prompt → ticket C0.

### Member D — data & infra (`src/data`, `infra`)
1. Read `docs/tickets/dev-d.md`.
2. **Do D0 (schema.sql) first and announce "schema is up"** — B and C are waiting on it.
3. Then D2/D3/D4 (hotlines, drugs, directory); your tools light up in `/chat` automatically.
4. Kickoff prompt → ticket D0.

### Healthcare teammate (5th, non-CS)
Pick the 5–8 procedures with sources, write the 40–60-question eval set, define the topic list for the classifier, and verify every answer's wording. Drop sources/links in `data_sources/` and the channel. You gate correctness — nothing ships without a source.

## Where everything lives
| Doc | What |
|-----|------|
| `CLAUDE.md` | Repo context your agent reads automatically |
| `docs/PLAN.md` | Sprints, timeline, **dependency map** |
| `docs/CONTRACTS.md` | The shared types/interfaces you implement against |
| `docs/ARCHITECTURE.md` | System design + per-turn flow |
| `docs/tickets/dev-*.md` | Your tasks + acceptance tests + agent kickoff prompt |
| `docs/WORKFLOW.md` | Branching / PR rules |
