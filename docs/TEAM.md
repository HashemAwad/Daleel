# For the team

| Start here | |
|---|---|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Setup + first moves for each developer |
| [PLAN.md](PLAN.md) | Sprints, timeline, dependency map |
| [../CLAUDE.md](../CLAUDE.md) | Context your AI agent reads automatically |
| [CONTRACTS.md](CONTRACTS.md) | The interfaces each module implements |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design |
| [tickets/](tickets/) | Per-developer task lists (A/B/C/D) |

## Ownership

A → `src/core` (backend) · B → `src/ai` (retrieval + voice) · C → `src/channels` + `web` (channels/UI) · D → `src/data` + `infra` (data/infra). You edit only your folder; modules integrate automatically through `src/core/providers.py`.
