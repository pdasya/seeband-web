# SeeBand Web

Web version of the SeeBand desktop application. Calculations run only on the server.

## Commands

- All checks: `pnpm check`
- JavaScript and TypeScript: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm format`
- Python: `pnpm check:py`
- First setup: see `README.md`

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
