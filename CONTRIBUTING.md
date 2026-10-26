# Contributing

## Branches
- `main` — always releasable. No direct commits.
- Work branches: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, `chore/<topic>`.
- One branch = one cohesive change = one PR.

## Commits (Conventional Commits)
`type(scope): subject`

Types: `feat` `fix` `docs` `refactor` `test` `chore` `style` `perf` `ci`.
Scope: a module (`api`, `extraction`, `ui`, `storage`, `providers`, `preprocessing`, …).

Example: `feat(extraction): structured evidence trail with block_id + bbox`.

## Pull requests
- Open against `main`.
- Include: motivation, summary of change, tests added/updated, breaking changes.
- Squash-merge on approval; delete the branch.
- If a change alters any number in `results/paper_numbers.yaml`, say so in the PR
  and re-run `scripts/build_summary.py`.

## Local dev loop
```bash
pre-commit install
pytest -m "not slow"
ruff check . && ruff format --check .
```
