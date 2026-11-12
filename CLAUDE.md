# SeeBand Web

Web version of the SeeBand desktop application. Calculations run only on the server.

## Commands

- All checks: `pnpm check`
- JavaScript and TypeScript: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm format`
- Python: `pnpm check:py`
- First setup: see `README.md`
- Branch, commit and pull request rules: see `CONTRIBUTING.md`

## Rules linters cannot check

- Make units explicit in names and schemas, for example `temperature_k`.
- Do not mutate inputs in `seeband_core`.
- Send all visible strings through i18n.
- Use shared components from `packages/ui`.
- Do not hand-write API types. Generate them from OpenAPI.

## Skills

- `architecture`: boundaries, data handling and when numbers may change.
- `documentation`: what to update alongside a change.
- `fastapi`, `vercel-composition-patterns`: framework guidance. Project rules win over them.
- Third-party skills are recorded in `.claude/skills/THIRD_PARTY.md`.

## Agents

- `python-reviewer`, `fastapi-reviewer`, `typescript-reviewer`, `react-reviewer`, `security-reviewer`, `code-reviewer`: read-only reviewers in `.claude/agents/`. Run them when asked.
- They are third-party, recorded in `.claude/skills/THIRD_PARTY.md`.
- `physics-reviewer`: written for this project. Checks formulas, limits, scales and whether fits mean anything. It does not replace a physicist's confirmation.
- Review team, written for this project and read-only by default: `review-coordinator`, `physics-contract-reviewer`, `numerics-inference-engineer`, `performance-engineer`, `compute-runtime-engineer`, `scientific-ux-reviewer`, `reproducibility-engineer`, `independent-validation-reviewer`. Run them when asked. Order: physics contract, then numerics, then independent validation; runtime and performance in parallel; reproducibility and UX after the schema is agreed. An author is never the only reviewer of their own change.
