# seeband-web

Web version of the SeeBand desktop application, in progress. See the pinned Roadmap issue for the plan.

## Repository

| Folder                  | Purpose                                 |
| ----------------------- | --------------------------------------- |
| `apps/web`              | application at `/app`                   |
| `apps/site`             | public pages                            |
| `apps/api`              | FastAPI layer over the core             |
| `packages/seeband_core` | calculations and fits                   |
| `packages/ui`           | design tokens and shared header         |
| `packages/api-client`   | TypeScript types generated from OpenAPI |
| `deploy`                | Docker Compose and Caddy                |

## Setup

Requires [Node.js](https://nodejs.org) 24 or newer, [pnpm](https://pnpm.io) 12 and [uv](https://docs.astral.sh/uv/). uv installs Python 3.13 if needed.

```sh
pnpm install
uv sync
```

## Checks

```sh
pnpm check
```

GitHub Actions runs the same checks on every pull request and on pushes to `main`.

## Claude Code

Plugins are enabled for this repository in `.claude/settings.json`, but each person installs them once:

```sh
claude plugin install pr-review-toolkit@claude-plugins-official --scope project
claude plugin install claude-md-management@claude-plugins-official --scope project
claude plugin install skill-creator@claude-plugins-official --scope project
claude plugin install pyright-lsp@claude-plugins-official --scope project
claude plugin install typescript-lsp@claude-plugins-official --scope project
```

The two language server plugins need these programs on your `PATH`:

```sh
uv tool install pyright
npm install -g typescript typescript-language-server
```

Link the FastAPI skill bundled in the installed package:

```sh
sh scripts/setup-claude.sh
```

Run this script again after recreating `.venv` or changing the Python version.
