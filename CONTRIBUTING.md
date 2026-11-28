# Contributing

Work is tracked in [GitHub issues](https://github.com/pdasya/seeband-web/issues). Each issue title starts with a task ID, such as `[F3]`, and the pinned Roadmap issue shows the order.

## Branches

Name a branch `<task prefix>-<task number>-short-summary`, using the task ID from the issue title. Write the summary in lowercase with hyphens, because Git branch names cannot contain spaces.

| Issue title | Branch                  |
| ----------- | ----------------------- |
| `[F1] ...`  | `F-1-monorepo-skeleton` |
| `[FS8] ...` | `FS-8-run-and-stop`     |

## Commits

Write commit messages in English.

## Pull requests

- Start the title with the task ID, for example `[F3] Add NOTICE and contribution rules`.
- Close the issue from the description, for example `Closes #3`.
- Run `pnpm check` before pushing. The `Python` and `TypeScript` CI checks must pass before merging.
- `pnpm check` skips the extended core regressions. CI runs them when `packages/seeband_core/src` changes; for other changes to solvers, tolerances or fits, tick the box in the pull request template, or run `uv run pytest -m extended`.
- CI runs pytest on every CPU with `pytest-xdist`. A test that asserts wall-clock latency gets `@pytest.mark.timing`, and CI runs those alone afterwards. `pnpm check` still runs everything in one process; `uv run pytest -n auto -m "not timing"` is the faster local run.
- Merge with squash, and write a merge message that describes the result of the whole branch.
- Delete the branch after merging.

## Project rules

`CLAUDE.md` lists rules that linters cannot check. The `architecture` and `documentation` skills in `.claude/skills/` cover code boundaries, when calculated numbers may change, and which documents to update with a change.
