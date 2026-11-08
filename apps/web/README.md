# apps/web

The application served at `/fit` and `/results`: Vite, React and TypeScript. It shows data and results and holds no physics formulas.

```sh
pnpm --filter @seeband/web dev      # http://localhost:5173/fit
pnpm --filter @seeband/web build    # into apps/web/dist, every asset under /assets/
pnpm --filter @seeband/web preview  # the production build
```

## Shell

| Path          | Shows                                                    |
| ------------- | -------------------------------------------------------- |
| `/fit`        | the fit screen                                           |
| `/results`    | the results screen                                       |
| `/`           | the public site. With no site, as in development, `/fit` |
| anything else | a not-found view, where the server sends it to the app   |

`src/routes.tsx` holds the routes, and `src/shell` what screens share: the header, the two columns that wrap, the page heading with its slot for a status badge, and panels. The fit and results screens are frames for now.

- **Overview and Conventions** are plain links to the public site, which does not exist before S1, so they lead nowhere in development.
- **The app has no path prefix, so a server must list its paths.** [I1](https://github.com/pdasya/seeband-web/issues/53) must answer `/fit` and `/results` with `index.html`, as a reload there otherwise gets a 404, and serve `/assets/` and `/licenses/` from this build. `vite preview` answers any path with `index.html`. A new screen needs a line there, and in `robots.txt` ([S6](https://github.com/pdasya/seeband-web/issues/68)), and the site must not use these paths.
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
- **Nothing persists.** Measurements stay in memory, as they must not be stored, so a reload clears them, and the browser asks first while any file is loaded. The two ways of loading keep their own files, and only the open one counts. The store holds codes and numbers, and no text in any language.
- **The store does not call the API.** A change after a result clears it, but a change during a fit leaves it running, so FS8 decides whether to stop it.
- **`tests` run the client against the real mock,** in `api/mock.integration.test.ts`.

## Data

`data/DataPanel.tsx` holds a slot for each of S, ρ and R_H. A file goes straight to `POST /api/parse`, as parsing belongs on the server, and it took 6 ms for 1000 rows through a test client on one Mac. The result goes to the session store, and its text stays in memory, for interpolation.

- **A read can be cancelled** with the button on its card, which stops the request.
- **A new file replaces the old one,** and stops a read under way. If it fails, the old data go too, as a fit from them would look like a fit from the new file.
- **A file over 8 MB or 2000000 characters is refused before sending,** as a 413 for a large body can arrive as a network error.
- **Text in UTF-16 with a byte order mark is decoded here.** Anything else is read as UTF-8, and the server reports what that spoils.
- **Only the slot's quantity is taken** from a file in a slot.
- **One file can hold them all,** under Single file. The server suggests the columns, and a change sends the text again, as the API keeps nothing, so the text stays in memory until the file goes. The server also says if a mapping will not do: `missing_temperature` and `repeated_role`. A repeated temperature is only a warning, as a real example file measures 100 K twice.
- **Interpolation has one switch,** for all the data. Values come from `POST /api/parse`, and sit beside the measured data, so that turning it off restores those exactly. Each change of the data or fit range asks again, after 300 ms, so the text of each file stays in memory. Use `fitData` for what a fit reads: with the switch on and no usable values, it gives null rather than quietly falling back to measured data. Its flags say when values are made up. It uses the fit range of the selection, or the default of `GET /api/models` until FS4 sets one. It runs in the shell, so moving between screens sends nothing again. If one file's request fails, the others stay, and the flags name it. With only one bound selected, the other is the default, so FS4 must set both together.
- **There is one source at a time.** Changing between separate files and a single file clears the data, as what the other way loaded no longer shows.

`e2e/examples.spec.ts` loads the 9 example files through a real API, and runs only when `SEEBAND_API_TARGET` is set:

```sh
uv run python -m seeband_api
SEEBAND_API_TARGET=http://127.0.0.1:8000 pnpm --filter @seeband/web exec playwright test examples
```

## Model

`model/ModelPanel.tsx` chooses which fit can run. All of it comes from `GET /api/models`, so a new model needs no change here. A fit mode's name comes from its quantities, and a model's from its id. `model/selection.ts` keeps a choice only where it still holds, so a disabled mode is never chosen.

- **A disabled mode cannot be chosen,** and its reason shows under the options, from the text for its known issue. A new known issue that disables a mode needs a line in `strings.ts`, or it gets a general text.
- **Each model keeps its own mode, scattering and degeneracies,** as the design does. The fit range is shared.
- **A number being typed stays in its field.** It reaches the session on leaving the field or on Enter, and only if it holds, so the steps on the way to it send nothing and clear no result. N₁ and N₂ are any numbers above 0, and the two bounds of the range go together.

## Live curves

`model/useLiveCurves.ts` asks `POST /api/calc` for the current values whenever they change and data are loaded. Without data for the fit mode, nothing is sent.

- **One request at a time.** `model/latestOnly.ts` sends the latest values when the running request has its answer, so requests cannot pile up on a slower server. A change does not abort a running request, because the server cannot stop a calculation that has started. So an old answer cannot arrive after a newer one. Only leaving the page or removing the data aborts one, and a request with no answer ends after 60 s.
- **A request waits** for 250 ms of rest, or 300 ms at the latest during a long drag. FS12 tunes these over a real network.
- **The chart keeps the last curve** while waiting and after an error, and the RMSE says then that it is not current. An indicator appears 600 ms after a change, as a quick answer would make it flicker.
- **A 429 with `Retry-After`** of up to 30 s holds requests back until then, and sends the latest values by itself. Any other error waits for the next change.
- **Measured and interpolated points are two series.** Measured points always show. With the switch on, interpolated points show too, in another colour, as these are what the RMSE and a fit use.
- **Only points in the fit range** go with a request, for the RMSE, and the `extrapolated` flag goes with them. Points of ρ and R_H with a value of 0 stay out, as the API refuses a relative RMSE there, and the panel says so.

## Chart tabs

`model/chartTabs.ts` says what each tab of the fit screen draws, in the units of its axis: S in µV/K, ρ in µΩ·m, R_H in m³/C and μ in K.

- **S, ρ and R_H** use the curves that measurements go with. With no data, a tab says so. With data that the fit mode does not use, it shows the points and says that the mode has no model for them.
- **μ and band contributions** are other kinds of curve, which the API refuses to mix with measurements. So they are a second request, only while their tab is open, and also one at a time. They need no data. The contributions take their total S from the first request.
- **An answer shows only for its own curve.** It counts while the model, mode, scattering and kind match, so a new value keeps the curve while waiting, and a change of mode takes it away at once. A tab shows the state of a request only if it draws its curves.
- **Whether a mode offers a curve** comes from `curves` in `GET /api/models`, with its text from the reason. μ draws the band edges, and E_g comes from a mode's `band_gap` where it has one.

## Fits

`model/fitRun.ts` runs a fit through `POST /api/fit`, outside any component, so it goes on while another screen is open. `model/fitRequest.ts` builds the request, or says why there can be none, which shows beside Run fit.

- **A fit moves the values on screen.** Each iteration's parameters go into the session in the store, so the sliders follow, the live curves redraw at their own pace, and a Stop keeps the last ones. The last answer's parameters do the same, so the curve on screen is the fitted one. A value that is not finite leaves the last one.
- **Parameters cannot be changed while a fit runs,** as it would overwrite them. A change of data, mode, scattering, degeneracies or range stops the fit, as it would be one of something no longer on screen.
- **Stop is closing the connection,** and a stream that ends by itself is a failure, not a Stop. A single-pass mode shows no counter.
- **Failures show in our own words,** as the server's text is for developers. Reset goes back to a mode's defaults, and stops a fit.

## Initial guess

`model/guessRun.ts` asks `POST /api/guess` for start values, with every row of S, whatever the fit range. The Initial guess button does this, for a model with `has_initial_guess`, and so does each new file of S, as on the desktop.

- **It writes to every mode of the model,** as the desktop does to all its DPB windows, so also from another model's screen. Only the parameters a mode has, and the rest keep their values.
- **An edit or a fit while it waits wins,** as the user has moved on, and so does S going away, as the values would describe nothing on screen. Edits before a new file are overwritten, as on the desktop. Coming back to a tab or reading the same S under a new mapping is no new load, and keeps what was edited.
- **The badge shows the net's real range,** from the API, while its values stand. With no net, a prediction that is not finite, or `m_eff` of about 0, the values stay, and a line says why.

## Demo data

`/fit?demo=1` loads `GET /api/demo` into the slots of S, ρ and R_H, and opens the fit the data were made for, as the link from Overview will (S2). The address then drops that, so that coming back cannot replace what the user did since. After a failure it stays, so a reload tries again.

- **The panel has a link to them,** Try demo data, while no file is loaded, so that they can be reached with no Overview.
- **They say what they are wherever they appear:** "Demo data" on each card, "Measurements (demo)" in the chart legend, and a notice for as long as any are in use. Results and exports must keep this (R1, R4).
- **They take the path of a file.** S starts the initial guess. Interpolating sends their rows as text, because the API has no text of them, and a reload warns as it does for a file.
- **Files of the user's are never replaced, or mixed with the demo.** With one loaded or still being read when the demo arrives, the demo does not load, and the link is not offered. Clear demo data removes only the demo.

## Band diagram

The E(k) tab draws `POST /api/band-diagram` for the current values, with one request at a time like the curves, and only while it is open. It is the desktop's sketch, with no ticks on k and the same formula, grid and bands, which a test checks against the desktop's recorded calls. It differs where the desktop rounds values to its sliders, also after Adjust to fit, draws 200 points before the first change, and takes N₁ and N₂ as whole numbers (D24). Its formula is a known error (`band_diagram_formula`, #108), so a note under it says so. It needs no data.

## Bounds

`model/BoundsEditor.tsx`, a dialog opened beside the title of the parameters, sets the bounds of a fit for each mode, where the description has `bounds_editable`. They go in `bounds` on `POST /api/fit` in core units, only those that differ from the description, and only for the scattering in use. The result table shows them, and the parameter's slider and field take them as their range, as on the desktop.

- **Values do not move with them,** unlike on the desktop (D27). A start outside its bounds stops Run, and says which, but does not stop a fit that runs, whose own values can read past them when N₂/N₁ is not 1 (D12). Only bounds the user set are checked here: a start outside the description's own is for the API to report.
- **The lower bound must be below the upper.** Both ends count together, and are checked as focus leaves the row, so a range can move past its old end. Otherwise the last valid bounds stay, and Done does not close the dialog on them. Escape and the corner button do, and a click beside it does not.
- **Reset restores them,** with the values. Default bounds restores only them.
- **The fit range** is in the model panel, shared by all modes, as on the desktop.

## Result

`model/ResultPanel.tsx` shows what the values on screen give, from `model/resultSummary.ts`.

- **Metrics:** the RMSE of each measured quantity, and the iterations with their limit. A single-pass mode has no iterations, so it shows neither.
- **Parameters:** the values in use, with the bounds a fit uses, in the units the user sees. A parameter a fit does not change says so. A value at a bound is marked, unless the fit failed.
- **A fit that did not converge** says what the values are: last values, start values, or, after a failure, not a fitted result. The status badge stays beside the page title.
- **Known errors** show their text from `fit.knownIssueTexts`, never their id. The flags of the fit and of the curves count together, as curves from a fit carry its errors. One that changes a measured curve marks that RMSE and goes under the metrics. One about the fit alone goes under the parameters. A new id shows a general text until it has its own.

## Numbers

The app shows numbers with a decimal comma, in fields, labels, messages and charts, whatever the browser's region. `lib/numbers.ts` holds this. Number fields are text fields, because `type="number"` shows the separator of the computer's region. They accept a comma or a point. Files and the API keep their points.

## Parameters

`model/ParametersPanel.tsx` shows the parameters of the chosen fit mode and scattering type from their descriptions, so a new parameter needs no change here. Without a line in `strings.ts`, it shows its name.

- **Values are in core units, per fit mode.** `model/parameters.ts` holds the only conversion to what a user sees, and `parameterValues` gives every parameter of a mode for a request, with defaults from `core_range`.
- **The slider moves by whole control units,** as on the desktop. Arrow keys move by the description's `step`, and Page keys or Shift with an arrow by ten. `step` is not a grid, so values between steps stay as they are.
- **A field shows 6 digits,** with the full value on hover, as a fit's values have more than fit. The session and requests keep them all.
- **A typed number** counts on leaving the field or on Enter, and only within the range. It may lie between whole control units, unlike on the desktop (D26). Advanced ranges come in FS13.
- **Whole control units reach the core exactly,** as from the desktop's slider, so 2.55 at a display scale of 0.01 gives 255, not 254.99999999999997.
- **The SPB mass is one slider across negative and positive,** as on the desktop, where the sign sets the carrier type.

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
