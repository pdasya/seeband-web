# apps/web

The application served at `/app`: Vite, React and TypeScript. It shows data and results and holds no physics formulas.

```sh
pnpm --filter @seeband/web dev      # http://localhost:5173/app/
pnpm --filter @seeband/web build    # into apps/web/dist, every asset under /app/
pnpm --filter @seeband/web preview  # the production build at /app/
```

## Shell

| Path           | Shows               |
| -------------- | ------------------- |
| `/app/`        | leads to `/app/fit` |
| `/app/fit`     | the fit screen      |
| `/app/results` | the results screen  |
| anything else  | a not-found view    |

`src/routes.tsx` holds the routes, and `src/shell` what screens share: the header, the two columns that wrap, the page heading with its slot for a status badge, and panels. The fit and results screens are frames for now.

- **Overview and Conventions** are plain links to the public site, which does not exist before S1, so they lead nowhere in development.
- **A server must answer any path under `/app/` with `index.html`,** as a reload at `/app/results` otherwise gets a 404, and send `/app` to `/app/`. `vite preview` does the first, and answers `/app` and a path with broken percent-encoding with its own 404. [I1](https://github.com/pdasya/seeband-web/issues/53) must set it in Caddy.
- **The error views show no details,** as an error's message could quote a user's data. An error in a page appears inside the shell, and one in the shell appears without it.
- **A move inside the app takes focus to `main`,** so that a screen reader follows it. Scroll position is not handled, as the pages are short so far.
- **Headings on the fit screen come in the design's order:** Data and Model come before the `h1`, as the side panel does. V2 should check this with a screen reader.
- **All text is in `src/strings.ts`** until [U3](https://github.com/pdasya/seeband-web/issues/36) brings i18n. Add new text there.
- **The header stays here until [U6](https://github.com/pdasya/seeband-web/issues/37)** shares it with the site, and adds the language switch. The design's Export button comes with R4.

## Talking to the API

```sh
pnpm mock                             # in one terminal, the mock from the contract
pnpm --filter @seeband/web dev        # the app, with /api going to the mock on port 4010

uv run python -m seeband_api          # or the real API
pnpm --filter @seeband/web dev:api    # the app, with /api going to port 8000
```

The app always calls `/api` on its own origin, so there is no base URL to set, and `SEEBAND_API_TARGET` chooses where the dev server sends it. Neither the API nor the mock send CORS headers, so a browser would hide their errors from a client on another origin.

| File               | Holds                                                                   |
| ------------------ | ----------------------------------------------------------------------- |
| `api/client.ts`    | a typed call for each route, with types only from `@seeband/api-client` |
| `api/fitStream.ts` | `streamFit`, the events of `POST /api/fit`, over `fetch`                |
| `api/errors.ts`    | `ApiError`: every failure, in the form of the server's errors           |
| `api/queries.ts`   | the TanStack Query client and its retry rule                            |
| `session/store.ts` | the session in Zustand: data, selection, parameters, fit                |

- **Show `ApiError.code` through i18n.** `message` is English text for developers. The client adds `network_error`, `unexpected_response` and `stream_ended`, a stream with no last event.
- **Retries** are one, and only for a network failure or a 503. A 429 gives `retryAfterS`, for the screen to act on. A mutation never repeats by itself.
- **Each fit is a run.** `fitRequested` returns its id, which goes with each call after it, so that late events of an old fit cannot reach a new one.
- **Stop a fit by aborting** the signal of `streamFit`, then call `fitStopped`, which keeps the last values received. An abort throws an `AbortError`, so do not report it as a failure.
- **Nothing persists.** Measurements stay in memory, as they must not be stored, so a reload clears them. The store holds codes and numbers, and no text in any language.
- **The store does not call the API.** A change after a result clears it, but a change during a fit leaves it running, so FS8 decides whether to stop it.
- **`tests` run the client against the real mock,** in `api/mock.integration.test.ts`.

## Base components

`src/components/ui` holds Button, Input, Select, Switch, Slider, Tabs, Table, Badge and Alert. They are copies from [shadcn/ui](https://ui.shadcn.com), and they are ours to change. They differ from upstream, to match the design:

- Sizes, radii and colours are the design's. Badge has the status variants and Alert a `warning` variant.
- There are no dark variants, as the design has none.
- Focus comes from one rule in `src/index.css`, the design's outline, rather than a ring on each component. Select's options draw it inside themselves, as their menu would clip it. Transitions cover colours only, so that the outline appears at once.
- Slider with no value has one thumb, as Radix treats it. Upstream draws a second one with no value.
- Slider puts `aria-label` and `aria-labelledby` on its thumb, which is what has the role of slider. Upstream leaves them on the root, where a screen reader does not find them.
- Slider is a Radix slider with the design's colours and size. The design uses the browser's own range input, so the two differ a little in look.

**Rem stays 16 px.** The design's text is 14 px, set on `body`. Tailwind's sizes are in rem, so a smaller root makes a 36 px button 31.5 px.

## Adding a component

The `shadcn` skill in `apps/web/.claude/skills` is pinned to this version of the CLI. See [`THIRD_PARTY.md`](../../.claude/skills/THIRD_PARTY.md).

```sh
cd apps/web
pnpm dlx shadcn@4.23.0 add <name> --dry-run
```

**Check the result before keeping it.** With version 4.23.0, the registry's components import `cn` from the npm package `cn`, which shadcn publishes as a replacement for `clsx` and `tailwind-merge`, and the CLI installs it. This project keeps those two in `src/lib/utils.ts`, as `cn` is at 0.5 and its last release was days old when this was written. On 14 sample calls, the two gave the same classes. So after adding, change the import to `@/lib/utils`, run `pnpm --filter @seeband/web remove cn`, and apply the differences above. To move to `cn` later, change that import in `src/components/ui`, and remove `src/lib/utils.ts`.
