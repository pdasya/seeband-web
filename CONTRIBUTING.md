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
- Merge with squash, and write a merge message that describes the result of the whole branch.
- Delete the branch after merging.

## Project rules

`CLAUDE.md` lists rules that linters cannot check. The `architecture` and `documentation` skills in `.claude/skills/` cover code boundaries, when calculated numbers may change, and which documents to update with a change.
