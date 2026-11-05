# seeband-web

Web version of [SeeBand](https://github.com/xAngelswordx/SeeBand), a desktop application by Michael Parzer and Alexander Riss for fitting parabolic band models to the temperature dependence of the Seebeck coefficient, resistivity and Hall coefficient.

The project is in progress, and there is no working application yet. See the [Roadmap](https://github.com/pdasya/seeband-web/issues/90) for the plan.

## Architecture

Calculations run only on the server. The React client shows data and results, and FastAPI is a thin layer over the `seeband_core` calculation package. Public pages are static HTML built with Astro. Everything runs in Docker Compose on one VM.

## Source documents

The [project overview](https://claude.ai/artifact/5WDV9nBj7G9vXTihrtkGmd) and [design](https://claude.ai/artifact/LnPAS7rxCdM2YDrgJhfBny) are private for now, so outside readers may not be able to open them.

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

Requires [Node.js](https://nodejs.org) 24.18 or newer, [pnpm](https://pnpm.io) 12 and [uv](https://docs.astral.sh/uv/). uv installs Python 3.13 if needed.

```sh
pnpm install
uv sync
```

## Checks

```sh
pnpm check
```

GitHub Actions runs the same checks on every pull request and on pushes to `main`.

To work on the client without the API, run `pnpm mock`. See [`packages/api-client`](packages/api-client/README.md).

After changing the API, regenerate its contract and TypeScript types. The checks fail if they are out of date:

```sh
pnpm api:generate
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch, commit and pull request rules.

## License

[MIT](LICENSE). Code ported from SeeBand stays under its original license, reproduced in [NOTICE](NOTICE).

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
