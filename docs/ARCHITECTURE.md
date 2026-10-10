# Architecture

> **Status: skeleton.** The module list below gets filled in once we lock the idea.

## Approach: Modular Monolith
One repo, one deployable app, split into **independent modules**. Each module:
- Is owned by **one person** (see `CODEOWNERS`).
- Talks to other modules only through **agreed interfaces/contracts**, never by reaching into another module's internals.
- Can be built and tested on its own (stub its dependencies).

This gives us the parallelism of microservices without the ops overhead — perfect for a hackathon.

## Why this prevents collisions
- People edit different folders → git rarely sees overlapping changes.
- Contracts are decided together once, then everyone codes against them independently.

## Proposed layout (to be finalized with the stack)
```
/src
  /shared        # types, contracts, config, utils — changes reviewed by all
  /modules
    /<module-a>  # owner: ___
    /<module-b>  # owner: ___
    /<module-c>  # owner: ___
    /<module-d>  # owner: ___
  /app           # wiring: composes the modules into the running app
```

## Module ownership (fill in after idea is chosen)
| Module | What it does | Owner | Depends on (contracts) |
|--------|--------------|-------|------------------------|
| TBD    | TBD          | TBD   | TBD                    |

## Contracts / interfaces
Define the shape of data passed between modules here (or in `/src/shared`) before anyone starts. Example to be added once we know the domain.
