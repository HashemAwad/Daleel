# Team Workflow

4 devs working in parallel with (almost) zero merge conflicts. Read this once before you start.

## The golden rule
**You only edit files inside _your_ module folder.** Shared code (types, interfaces, config) changes go through a quick PR review so everyone stays in sync.

## Branching
- `main` is always working/deployable. Never push directly to `main`.
- Branch per feature: `feat/<your-name>/<short-desc>` e.g. `feat/mariam/auth-login`
- Fixes: `fix/<your-name>/<short-desc>`

## Day-to-day loop
```bash
git checkout main
git pull                       # start from latest
git checkout -b feat/you/thing # your branch
# ...work only in your module folder...
git add -A && git commit -m "feat: add thing"
git push -u origin feat/you/thing
# open a PR on GitHub -> merge when green + 1 review
```

## Pull Requests
- Keep them small. One feature = one PR.
- At least **1 teammate approval** before merge (fast, even a 2-min look).
- Resolve conflicts on *your* branch, never force-push `main`.
- Squash-merge to keep `main` history clean.

## Avoiding collisions
1. **Own your folder.** See `CODEOWNERS` — each module has one owner.
2. **Agree on contracts first.** Interfaces/types between modules live in the shared folder and are decided together up front. Build against them; stub what you depend on so you're never blocked on a teammate.
3. **Small, frequent merges** beat giant end-of-day merges.

## Commit messages (keep it simple)
`feat:`, `fix:`, `docs:`, `refactor:`, `chore:` + short description.
