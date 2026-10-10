# Daleel · دليل — MoPH Health Assistant

A health-information assistant for Lebanon's Ministry of Public Health, on **WhatsApp** and the **web**, in Arabic / Arabizi / French / English. It answers procedures, directory, medicine and hotline questions — always from a verified source, never model memory. Voice notes supported. Privacy by design: transcripts are deleted after anonymised metadata is extracted.

Built for the Hack for Health hackathon (AUB). **Phase 1:** the chatbot. **Phase 2:** a ministry dashboard from anonymised metadata.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY
docker compose up -d            # Postgres + pgvector (+ pg_trgm)
PYTHONPATH=src uvicorn core.app:app --reload
PYTHONPATH=src pytest -q        # all green
```
Then open `web/index.html`. Full setup: **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

## For the team
| Start here | |
|---|---|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | Setup + first moves for each developer |
| [docs/PLAN.md](docs/PLAN.md) | Sprints, timeline, dependency map |
| [CLAUDE.md](CLAUDE.md) | Context your AI agent reads automatically |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | The interfaces each module implements |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/tickets/](docs/tickets/) | Per-developer task lists (A/B/C/D) |

## Ownership
A → `src/core` (backend) · B → `src/ai` (retrieval + voice) · C → `src/channels` + `web` (channels/UI) · D → `src/data` + `infra` (data/infra). You edit only your folder; modules integrate automatically through `src/core/providers.py`.
