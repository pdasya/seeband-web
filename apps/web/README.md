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
- **The header comes from `packages/ui`,** shared with the site. `shell/AppHeader.tsx` only gives it the app's links. The language switch stays hidden until [U3](https://github.com/pdasya/seeband-web/issues/36), and the design's Export button comes with R4.

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

## Charts

`charts/TransportChart.tsx` draws a quantity against temperature with Plotly: measurements, model curves, the area outside the fit range, reference lines, a legend and a switch for the measurements. `charts/figure.ts` turns those into Plotly's terms, and calculates no physics. All text comes in as props, for i18n, and is English for now.

- **Plotly loads on first use,** as it is 400 KB compressed, and an empty state does not load it. This is the `basic` bundle, the smallest published: scatter, bar and pie.
- **Colours and fonts come from the tokens,** read from CSS when drawing, so a token change reaches the chart.
- **New data goes through `Plotly.react`,** which updates the drawing. Keep `curves` and the other props stable between renders, for example with `useMemo`, as new arrays draw again.
- **If Plotly cannot load or draw,** the chart shows a message rather than taking the page with it. It stays until the chart next appears.
- **The y axis ends on round ticks beyond the values,** so its top and bottom have labels: a largest value of 121 gives an axis up to 140.
- **A value of null leaves a gap,** and the switch for measurements is the chart's own state.

`e2e/` tests the chart in a browser with fixed data, through `pnpm --filter @seeband/web test`. It uses your Chrome, and in CI Playwright's Chromium. `test-results/chart.png` is a picture of it.

## Base components

`src/components/ui` holds Button, Input, Select, Switch, Slider, Tabs, Table, Badge and Alert. They are shadcn/ui as the CLI gives them, which build on Radix. **Style them through the tokens in `packages/ui`, not by changing their classes**, so that they stay easy to update.

They differ from upstream only here:

- **Badge** has the design's status variants, and **Alert** a `warning` variant.
- **Slider** puts `aria-label` and `aria-labelledby` on its thumb, which is what has the role of slider, and with no value it has one thumb, as Radix treats it. Upstream leaves the name on the root, where a screen reader does not find it, and draws a second thumb with no value.
- They import `cn` from `@/lib/utils`.

So a few sizes differ a little from the design: for example, Switch is 32 × 18 px rather than 44 × 24, a button's padding is 16 px rather than 14, and tabs use 14 px text rather than 13.

## Adding a component

The `shadcn` skill in `apps/web/.claude/skills` is pinned to this version of the CLI. See [`THIRD_PARTY.md`](../../.claude/skills/THIRD_PARTY.md).

```sh
cd apps/web
pnpm dlx shadcn@4.23.0 add <name> --dry-run
```

With version 4.23.0, the registry's components import `cn` from the npm package `cn`, which shadcn publishes as a replacement for `clsx` and `tailwind-merge`, and the CLI installs it. This project keeps those two in `src/lib/utils.ts`, as `cn` is at 0.5 and its last release was days old when this was written. So after adding, change the import to `@/lib/utils`, and run `pnpm --filter @seeband/web remove cn`. To move to `cn` later, change that import in `src/components/ui`, and remove `src/lib/utils.ts`.
