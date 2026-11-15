# apps/api

A thin FastAPI layer over `seeband_core`. It holds routes, validation and process management, and no formulas.

## Running

```sh
uv run python -m seeband_api
```

| Variable                              | Default                          | Applies to                                                                                                           |
| ------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `SEEBAND_API_HOST`                    | `127.0.0.1`                      | `python -m seeband_api` only                                                                                         |
| `SEEBAND_API_PORT`                    | `8000`                           | `python -m seeband_api` only                                                                                         |
| `SEEBAND_API_LOG_LEVEL`               | `INFO`                           | the API's own log lines, not uvicorn's own                                                                           |
| `SEEBAND_API_CALC_WORKERS`            | `2`                              | worker processes for calculations                                                                                    |
| `SEEBAND_API_CALC_TIMEOUT_S`          | `30`                             | how long a calculation request waits                                                                                 |
| `SEEBAND_API_FIT_MAX_RUNNING`         | `2`                              | fits at once, in each server process                                                                                 |
| `SEEBAND_API_FIT_MAX_WAITING`         | `4`                              | fits waiting, before a 429                                                                                           |
| `SEEBAND_API_FIT_TIMEOUT_S`           | `180`                            | how long one fit can run                                                                                             |
| `SEEBAND_API_FIT_MAX_PER_CLIENT`      | `2`                              | fits running or waiting for one client                                                                               |
| `SEEBAND_API_MAX_BODY_BYTES`          | `10000000`                       | size of a request to `/api/parse` and any route not below                                                            |
| `SEEBAND_API_MAX_JSON_BODY_BYTES`     | 1 MB, or what `max_points` needs | size of a request to calc, fit, guess and band-diagram; set below what `max_points` needs, the server warns at start |
| `SEEBAND_API_MAX_POINTS`              | `2000`                           | points of a quantity, or rows of a text                                                                              |
| `SEEBAND_API_CALC_PER_MINUTE`         | `600`                            | `POST /api/calc` for one client                                                                                      |
| `SEEBAND_API_BAND_DIAGRAM_PER_MINUTE` | `600`                            | `POST /api/band-diagram` for one client                                                                              |
| `SEEBAND_API_PARSE_PER_MINUTE`        | `60`                             | `POST /api/parse` for one client                                                                                     |
| `SEEBAND_API_GUESS_PER_MINUTE`        | `60`                             | `POST /api/guess` for one client                                                                                     |
| `SEEBAND_API_FIT_PER_MINUTE`          | `30`                             | `POST /api/fit` for one client                                                                                       |
| `SEEBAND_API_TRUSTED_PROXIES`         | `127.0.0.1,::1`                  | whose `X-Forwarded-For` to believe. `python -m seeband_api` only                                                     |

| Route                    | Purpose                     |
| ------------------------ | --------------------------- |
| `GET /api/health`        | status and version          |
| `GET /api/models`        | model descriptions          |
| `POST /api/calc`         | curves and RMSE             |
| `POST /api/band-diagram` | the sketch of E(k)          |
| `POST /api/parse`        | reading measured data       |
| `POST /api/guess`        | initial parameter estimates |
| `POST /api/fit`          | fitting, as event stream    |
| `GET /api/demo`          | synthetic dataset           |
| `GET /api/openapi.json`  | the contract                |
| `GET /api/docs`          | Swagger UI over the same    |

## Limits

Each limit answers in the usual error format. All the values are starting guesses, and should be checked on the VM and with real use.

| Limit                                  | Answer                                           | Applies to                                                               |
| -------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------ |
| Request rate of one client             | 429 `rate_limited`, with `Retry-After`           | the five `POST` routes, counted separately                               |
| Size of a request                      | 413 `request_too_large`                          | every route: 1 MB for calc, fit, guess and band-diagram, 10 MB otherwise |
| Points of a quantity                   | 422 `too_many_points` in `details`, at the field | `/api/calc`, `/api/fit`, `/api/guess`                                    |
| Rows of a text                         | 422 `too_many_rows` in `details`                 | `/api/parse`                                                             |
| Fits running or waiting for one client | 429 `client_fit_limit`, with `Retry-After`       | `/api/fit`                                                               |

These are fixed by the contract instead of a setting: 2000000 characters of `text`, 1000 for `points` and `rmse_points`, and in the core 10000 points of an interpolation grid. A wide fit range can give a grid over `max_points`, which `POST /api/fit` then refuses. Every list and dict of a request has a `maxItems` or `maxProperties` too: 100000 values in a list of points, which `max_points` cannot exceed, 64 parameters, one entry per quantity and 1000 columns in a mapping.

- **A large invalid request costs little** (A13). Before, a 9.6 MB body with a wrong value in each place took 18 s, answered 349 MB and peaked the server at 5.8 GB, holding up `/api/health` for 5.6 s. Now a body over its route's limit is refused before it is read, a list stops at its first wrong value, a list or dict over its bound is refused before its items, and an error lists at most 50 `details`. A body of 0.99 MB with a wrong value everywhere answers 422 in about 0.02 s, under 1 KB, through a test client on one Mac. `tests/test_request_bounds.py` checks this, and that `/api/health` answers within 100 ms during such requests, through a real server whose memory grows by less than 50 MB.
- **Parse counts rows before it reads them.** A text with more lines that start like a number than `max_points`, after a line break of any kind, gets `too_many_rows` without reaching the worker pool, as reading 300000 rows takes about a second. Such lines that are not good rows count too, so a text of more than `max_points` of them gets `too_many_rows` where the parser would list their problems.
- **A trailing slash changes no limit.** `/api/calc/` has the limits of `/api/calc`, which it redirects to.

- **A 413 can arrive as a network error.** The server closes the connection without reading the rest. Node's `fetch` read the 413 for bodies of 11 and 40 MB, and got an `EPIPE` error at 200 MB. So a client should check a file's size before sending it. A browser was not tried.
- **Why 2000 points:** input size remains bounded independently of the fit deadline. Historical legacy measurements on one Apple Silicon Mac took 7–11 s at 1000 points and 29–49 s at 5000 points; these are not timing estimates for the verified method. P19 adds independent derivative and final-vector audits. Its demo fit exceeded the old 60 s API deadline on a hosted Linux runner, so the default is now 180 s, configurable through `SEEBAND_API_FIT_TIMEOUT_S`. The queue wait does not count, and running/waiting/per-client concurrency limits remain in force.
- **The rate** is a bucket that refills steadily and holds a minute's requests, so a client can spend them at once. 600 curves a minute allow 10 a second for a slider, and FS6 and FS12 should check that. A refused request takes nothing from the bucket, and one that a route refuses does.
- **Refusals come early:** rate and size are checked before the body is read or parsed. A row count needs the text to be read first, which for 2000000 characters takes about 0.5 s, or about 1.4 s for very short rows.
- **A client is an address**, or one /64 for IPv6, as one user usually holds a whole /64. So users behind one router share a limit. The addresses stay only in memory, and are not logged. While requests keep coming, one is dropped within about 2 minutes of its client's last request. With no requests at all, it stays until the next one.
- **Limits are per server process**, so `--workers 2` doubles them.
- **Behind a proxy, set `SEEBAND_API_TRUSTED_PROXIES` to its address.** The server then takes the client's address from `X-Forwarded-For`, from the right, skipping trusted addresses, so a client cannot choose its own. Without this, the proxy is the only client, and all users share one limit. [I1](https://github.com/pdasya/seeband-web/issues/53) must set it, and must not expose the API directly if it trusts `*`. Plain `uvicorn` uses its own `FORWARDED_ALLOW_IPS` instead.

## Model descriptions

`GET /api/models` returns what a client builds its forms from: models, fit modes, parameters, scales, bounds and known issues. It comes from the model registry in `seeband_core`, so a new model needs no change here. Clients revalidate it: it sends `Cache-Control: no-cache` and an `ETag`, and answers 304 if nothing changed, because a client holding old descriptions could offer a mode that is now disabled.

`has_initial_guess` says that `POST /api/guess` provides estimates: numerical search for SPB and a neural network for DPB.

A mode with `disabled: true` must not be offered, and `disabled_by` names the `known_issues` entries that say why. Show their `message_key` through i18n. `meaning` and `name` are English, for a client with no translation. Fields that do not apply are left out, rather than `null`. `band_2_edge` names the parameter whose core value is the edge of band 2 above band 1, in K, so a client draws it without knowing a model's parameter names; a one-band mode leaves it out.

Requests and results use core units. Each parameter gives its control as `display_range`, what a user sees, and `core_range`, core units, both calculated by `seeband_core`. Send core values from `core_range` rather than calculating them from the scales, because the desktop divides where a multiplication changes the last bit. `step` is a keyboard increment, not a grid. `calc_scale` stays out, because it only reproduces a desktop path.

The contract holds the real response as its example, so `pnpm mock` serves real descriptions, and a change to a description shows in the diff of `openapi.json`.

## Fits

`POST /api/fit` runs a fit in a new process, and answers with a stream of Server-Sent Events.

- **Algorithm:** `algorithm` defaults to `verified-sequential-v2`. Select `legacy-sequential-v1` explicitly for the historical fitting path. The response records the method that ran; no implicit fallback occurs.
- **Status:** verified `converged` requires final-vector conditional-stage checks; it does not establish physical adequacy or identifiability. `stalled` retains an endpoint without a convergence certificate; `iteration_limit` reports a budget limit. `failed` is a 200, including invalid starts or unresolved numerical failures. Check `message`, `diagnostics`, `at_bounds` and `known_issues`. Diagnostics include per-quantity input-grid residuals, numerical consistency and detected unidentified parameters; residual adequacy and uncertainty remain `not_assessed`. Verified fits do not supply parameter error bars. Legacy `converged` retains its historical solver semantics, and legacy `parameter_errors` hold other stages fixed, so they can be far too small. See [the numerical contract](../../packages/seeband_core/docs/verified-sequential-fit.md).
- **Data:** send each quantity of the mode. Only points inside the fit range enter the fit, and a quantity with none gets a 422 `no_points_in_range`.
- **Bounds** are in core units, and override the description's. A parameter with `bounds_editable: false` refuses them, as on the desktop, as does one that this scattering type does not use.
- **Held parameters:** `held` names fitted parameters to keep at their start values, and the fit finds only the others (D30). The response names them in `held`, with their values as sent, and no error or at-bound mark for them. A name the mode does not fit for this scattering type is `parameter_not_fitted`, and holding every fitted parameter is `nothing_to_fit`. A held value outside its bounds fails as a start outside them does. The errors of the free parameters hold the held values exact. Holding m1 in DPB, or the mass in SPB S + ρ + R_H, skips the only stage that uses R_H, so the result is the S + ρ fit with that value.
- **A disabled mode** gets a 409 before any process starts.

Each event is a line `data: <JSON>`, and `type` says which it is. The types are `FitStarted`, `FitIteration`, `FitDone` and `FitError` in the contract. The generated type of the stream itself is `unknown`, so a client names these four.

| `type`      | Holds                     | Meaning                                                                                 |
| ----------- | ------------------------- | --------------------------------------------------------------------------------------- |
| `started`   |                           | the fit has left the queue, and its process is starting                                 |
| `iteration` | `iteration`, `parameters` | one iteration, in core units. A single-pass mode sends none, so it shows no counter     |
| `done`      | `result`                  | last event: the fit ended, whatever `result.status` says                                |
| `error`     | `error`                   | last event: no result, with the usual error body in `error`. See the second table below |

**Reading it:** use `fetch`, as `EventSource` cannot POST, and send `Accept: text/event-stream, application/json`. Check the status first, then read the body as it arrives. Ignore lines that start with `:`, which keep an idle connection open every 15 s. There is nothing to resume: another request starts another fit.

**Stop** is closing the connection, with `AbortController` in a browser. The server ends the process, and sends nothing more, so a client keeps the `parameters` of the last `iteration` it received, or its start values if none came. m1 keeps its start value there, because it is fitted after the loop. So the core's status `stopped` never reaches a client. Any disconnect counts as Stop. A client that was waiting gives back its place, and its fit never starts.

**A stream that ends with no `done` or `error`** means that the connection was lost or the server stopped. Show it as a failure, not as a Stop.

Refusals come before the stream, as plain errors in JSON:

| Answer                  | Meaning                                                                       |
| ----------------------- | ----------------------------------------------------------------------------- |
| 422 `invalid_fit`       | the request does not fit this mode. See `details`                             |
| 409 `fit_mode_disabled` | the mode is disabled, and no process starts                                   |
| 429 `fit_queue_full`    | 2 fits running and 4 waiting by default. It comes at once, with `Retry-After` |

So a 200 only means that the fit has a place. A waiting client has its 200 and no event until `started`. These come afterwards, as the code of an `error` event:

| Code               | Meaning                                                                                            |
| ------------------ | -------------------------------------------------------------------------------------------------- |
| `fit_timeout`      | the fit ran past 180 s by default, and its process has ended. The wait in the queue does not count |
| `fit_process_died` | the process ended without a result, and trying again is reasonable                                 |
| `fit_failed`       | the process raised something other than a fit's own failure. The API logs only its type            |
| `internal_error`   | the API itself failed, and logs the type and code location                                         |

The log line of a fit says 200 whichever event came last, or if the client left, since the response had already started.

A process starts for each fit, which takes about 0.5 s of the time below. It ends with its request, whichever way the request ends: past the time limit, on a disconnect, or at a stop of the server. It is terminated, and killed if it stays. A process also exits if the server dies.

Historical legacy timing before P19 for each fit of the 3 desktop examples, in all 11 working combinations of mode and scattering, from the default start values, 50 to 800 K, through a test client on an Apple Silicon Mac with 10 cores: median 1.0 s, at most 1.6 s, all `converged`. Set the limit after trying these on the VM, as a small VM will be slower.

**A client that stops reading** keeps its connection open until it closes, as the API has no limit on that. Its fit still ends by the time limit and gives back its place, and its unread events stay in memory until then, at most a few per iteration.

**Behind a proxy:** a proxy must pass events on as they come, and must close its connection to the API when the client closes its own, or a Stop will not reach the fit. The API sends `Cache-Control: no-cache` and `X-Accel-Buffering: no`. Neither has been tried through Caddy yet: [I1](https://github.com/pdasya/seeband-web/issues/53) should check both with a real request.

**A Stop relies on the server reporting a disconnect while a fit sends nothing.** Uvicorn 0.54 reports ASGI spec version 2.3, so Starlette listens for it, and a client that leaves is noticed at once. With version 2.4 or higher, Starlette only notices a failed send, so a silent fit would end at the next keepalive, up to 15 s later. `tests/test_fit_stream.py` would fail on such an upgrade of uvicorn.

**Stopping the server** waits 5 s for requests through `python -m seeband_api`, then cancels them, and their fits end. Their streams end with no last event. Requests cancelled this way write no `request` line to the log. Plain `uvicorn` has no such limit, so a stop waits for every running and queued fit.

A `failed` fit's `message` is English text with no code, so a client cannot translate it by code.

## Reading data

`POST /api/parse` reads measured data from the text of a file or table, and optionally interpolates it. [`input-data.md`](../../packages/seeband_core/docs/input-data.md) lists the format and every code, and [`interpolation.md`](../../packages/seeband_core/docs/interpolation.md) the interpolation.

- **Input** is JSON with `text`, up to 2 000 000 characters, not a file upload. A multipart parser writes large uploads to a temporary file, so with JSON nothing reaches the disk. The client reads the file and decodes it, and should look for a byte order mark: UTF-16 read as UTF-8 gives `wrong_encoding`, and a header in Latin-1 can lose a character, which `unit_differs` then reports.
- **A file with problems is a 200,** with the problems in `errors` and a `preview`, so that a client can show them and let a user assign columns. `measurements` is empty with any error. A 422 means that the request itself is wrong.
- **Units:** each `mapping` item can carry a `unit`, such as `uV/K`, `mV/K`, `Ohm*cm` or `mOhm*cm`. Without one, a column is read in the unit its header names, or in SI. The answer's `mapping` gives the unit each column was read in, and `unit_source` where it came from: `chosen` in the request, named by the `header`, or SI by `default` as nothing named one. A client resends only the units a user chose, so that a column read by default stays marked as such. `measurements` are in SI, `preview` shows the values as read, `preview_text` the same values exactly as the text writes them, and `preview_si` the same rows in SI. `implausible_magnitude` carries `direction`, `above` or `below` the quantity's limits, and no value. A unit the quantity cannot have is the error `unit_not_allowed`, and one outside the contract a 422.
- **Assigning columns:** send the text again with `mapping`, as the API keeps nothing between calls. A choice is kept even while some rows have errors. A column that does not exist gives a 422 `invalid_parse_request` with `unknown_column`. With no readable rows, there is nothing to check it against, and `mapping` stays the suggestion.
- **Conductivity:** σ in S/m or S/cm can take the place of ρ, as `expected: "conductivity"` for a file with no header, a header such as `sigma (S/cm)`, or the role `conductivity` in `mapping`. It comes back as `measurements.resistivity`, ρ = 1/σ in Ω·m, computed once in the core, with `loaded_as: "conductivity"`. Every other measurement has `loaded_as` equal to its quantity. Interpolation, fits, curves and the RMSE all use that ρ, so σ gives what 1/σ loaded as ρ gives (D31). `preview` and `preview_si` keep σ. A σ of 0 or below is the error `non_positive_conductivity`, and a mapping with both ρ and σ is `resistivity_and_conductivity`.
- **`interpolate`** gives each quantity on a grid over a fit range, in `interpolated`, next to the original `measurements`. A range the grid cannot use is a 422 `invalid_parse_request` with `invalid_interpolation_range`. A polynomial that overflows gives `null`, which a client must not send on to `POST /api/calc`, as it refuses it. One quantity that cannot be interpolated is named in `interpolation_failed`, and the others stay. Pass `extrapolated` on to `POST /api/calc` if any quantity sets it, as made-up points enter its results.
- **Size:** a text over the limit gets a 422, and over 2000 rows a 422 `invalid_parse_request` with `too_many_rows`, even if some rows have errors. See [Limits](#limits).

## Demo dataset

`GET /api/demo` answers with the synthetic dataset of [`demo-dataset.md`](../../packages/seeband_core/docs/demo-dataset.md): S, ρ and R_H at 31 points from 50 to 800 K. **It is not a measurement of any material.** Show `message_key` through i18n wherever the data appear, as `synthetic` is always true.

It holds every field of a `POST /api/parse` response, because it goes through the same parser, so a client can treat it as a parsed file. It has no `interpolated` values. It adds `model`, `fit_mode` and `scattering`, which can be sent as they are to `POST /api/fit` or `POST /api/calc`, and what generated it, in `true_parameters` and `noise`. `true_parameters` is in core units, and is not a whole set: the mode's other parameters were at their `core_range` defaults in `GET /api/models`. So to send it to `POST /api/calc`, merge it over those, as it alone gets a 422. `known_issues` is empty after the P2 Hall-prefactor correction and regeneration.

It has no rate limit and no `ETag`, as it costs almost nothing and is under 10 KB.

## Curves

`POST /api/calc` returns curves for given parameters, in core units. It keeps no state, and runs in a pool of worker processes, so that the event loop stays free. Add `measurements` to get an RMSE for each quantity. Send only points in the fit range.

- **Parameters:** all of a mode's parameters are needed, and values outside a control's range are allowed, because a fit can end there. Names are checked, and problems are listed in `details`. Numbers must be JSON numbers: `true` or `"1.5"` are refused.
- **A disabled mode** gets a 409 `fit_mode_disabled`, with the ids of its known issues as the `code` in `details`. Show `known_issue.<code>` through i18n.
- **A value that is not finite** usually comes back as `null`, with the rest of the curve, as with a band mass of 0.
- **`calculation_failed`** is a 422 that loses the whole curve, because the core raises. This happens at `m_eff` = 0, which divides by zero, and in DPB S + ρ + R_H where a value at low temperature is not finite: at 2 to 300 K, 55 of 100 random parameter sets inside the control ranges failed, and none at 10 to 300 K or 50 to 800 K. In DPB S + ρ, the same condition gives one `null` instead. A submitted measurement at a low temperature can cause a density-certification failure during RMSE evaluation too. A negative m1 fails too, as it gives complex values. The API logs the exception's type.
- **`measured_points`** holds points made from the `measurements` sent, with no model: `electrical_conductivity_s_per_m` is 1/ρ at each ρ temperature, with `null` for a ρ of 0 or below. They go with the data the request sent: points in the fit range, as a client sends for the RMSE, and of interpolated ρ when it sends interpolated values. `seeband_core.measured_points` makes them. There are no κ_e points: κ_e is not measured, and an estimate from ρ needs a Lorenz number, which was decided against in #159.
- **RMSE** for built-in SPB/DPB models evaluates the final parameters directly at each submitted measurement temperature. `points` and `rmse_points` do not affect this metric. Submitted points may be interpolated by the client. Custom registered models retain the grid-based fallback controlled by `rmse_points`. `/api/calc` retains its `422 zero_measured_value` rejection for submitted zero ρ/Hall measurements; the web preview excludes those points. The core metric helper itself returns an unavailable percentage for zeros. Fit diagnostics separately provide absolute RMSE and relative L2 when defined.
- **`calculation_unavailable`** is a 503: a worker died, and the next request gets a new pool.
- **`calculation_timeout`** is a 504. A worker cannot be interrupted, so it stays busy until the calculation ends.

Requests are parsed in the event loop, up to the size in [Limits](#limits). A body of 9 MB of numbers took about 0.13 s in all, and the largest allowed grids, `points` and `rmse_points` of 1000, take about 1.3 s each.

Historical response-time measurements before P19 (the RMSE evaluator has since changed): a 50-point curve, through the app in one process with a test client, 20 calls each, on an Apple Silicon Mac with 10 cores and Python 3.13. The RMSE column uses the 31 points per quantity of the demo dataset. Network time is not included, and FS12 measures that.

| Mode, with default scattering | Curves | Curves and RMSE |
| ----------------------------- | ------ | --------------- |
| `spb_s`                       | 9 ms   | 17 ms           |
| `spb_s_rho`                   | 15 ms  | 29 ms           |
| `dpb_s`                       | 16 ms  | 31 ms           |
| `dpb_s_rho`                   | 27 ms  | 52 ms           |
| `dpb_s_rho_rh`                | 40 ms  | 79 ms           |

## Derived curves

`kind` in `POST /api/calc` chooses the curves: `measured` by default, or μ, σ, κ, the contributions of each band, or n. Each mode lists what it offers in `curves` in `GET /api/models`, and asking for another answers 422 `curve_unavailable`, with its reason as the `code` in `details`. Show `curve_unavailable.<code>` through i18n. `measurements` need the `measured` kind.

`thermal_conductivity` is the electronic part only, κ_e. There is no lattice term.

| Reason              | Meaning                                                      |
| ------------------- | ------------------------------------------------------------ |
| `same_as_measured`  | the total S here is the `measured` curve                     |
| `single_band`       | SPB has one band, so there are no contributions              |
| `needs_resistivity` | the mode has no scattering parameters to calculate this from |
| `not_on_desktop`    | the desktop has no such graph, so there is nothing to port   |
| `not_provided`      | a new model did not say                                      |

[`curve-availability.md`](../../packages/seeband_core/docs/curve-availability.md) holds the full matrix and how it differs from the desktop.

## Initial guess

`POST /api/guess` takes `model`, `temperature_k` and `seebeck_v_per_k`, and answers with SPB numerical estimates or DPB start values from the neural net. SPB returns `status: numerical_guess`, `start_values`, and `warnings`; no network range or network prediction applies. For DPB data that fit the contract, it answers 200, apart from the errors listed below, and `status` says which of three answers it is:

| `status`     | Meaning                                                                                                               | Holds                                                                       |
| ------------ | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `guess`      | a net fits, and its prediction is finite                                                                              | `net_range`, `start_values`, `prediction`, `warnings`                       |
| `no_net`     | the actual temperature minimum/maximum span no net's range, with `reason` `temperature_span`. Keep the current values | `first_temperature_k`, `last_temperature_k`, `available_ranges`, `warnings` |
| `not_finite` | a net fits, but a value of its prediction is not finite. Keep the current values                                      | `net_range`, `warnings`                                                     |

P9 keeps the legacy `no_net` fields `first_temperature_k` and `last_temperature_k` for compatibility; they report the actual minimum and maximum temperature, including for unsorted direct requests.

- **Use `start_values`, unless the warning `m_eff_rounds_to_zero` is there.** They go into `parameters` of `POST /api/calc`, by the names in `GET /api/models`, and the mode's other parameters keep their values. `m_eff` is dimensionless, and `band_gap` and `fermi_energy` are in K. The API keeps energies in K; the controls display energies in eV using model metadata. They are rounded and limited as the desktop's sliders do, so they lie in `core_range`: a gap of 52464 K starts at 3000 K. `step` does not apply: 554 K is a valid gap.
- **`prediction` is the net's own result**, before rounding and limits, in `m_eff`, `band_gap_k` and `fermi_energy_k`. It equals the core's exactly.
- **`net_range` is the real range of the net that was used.** Show it, rather than a fixed text.
- **Send every row of the Seebeck data, in V/K.** The desktop reads the whole file, not the fit range, unlike `POST /api/calc`.
- **Read `has_initial_guess` in `GET /api/models`.** An unknown model gets a 422 `invalid_guess`. SPB needs at least three distinct positive temperatures, a nonzero S signal and no sign reversal; unsupported signals return 200 `unsupported` with a reason code.
- **`calculation_failed`** is a 422 for a fit that fails. It did not happen in 20000 random requests with extreme finite values, run through the core on one Mac, so it should be rare. `calculation_unavailable` and `calculation_timeout` are as in `POST /api/calc`.

For SPB, `sign_only_parameters` marks parameters whose magnitude must be preserved. `start_values.band_mass` is a signed reference, not a measured mass. `rmse_v_per_k` reports residual error; warnings identify search bounds, omitted low-temperature rows and a relative RMS residual above 20% (a quality heuristic, not a band-count diagnosis). Clients preserve the existing nonzero mass magnitude in each mode and apply the returned sign (zero uses the parameter's own core default magnitude). `fermi_energy` is in K. The bounded search uses up to 24 measured points and does not require a network temperature interval.

`warnings` holds codes for a client to show through i18n, as `guess_warning.<code>`. The answer still follows the data:

| Code                   | Meaning                                                                                                                                                                                                                                       |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `unsorted_temperature` | The submitted rows do not rise. P9 chooses the net from actual Tmin/Tmax and sorts paired T–S rows before preparing its input; this warning records original order. The parser already sorts files.                                           |
| `underdetermined_fit`  | The data do not set the degree-5 polynomial behind the net's input, which takes 6 distinct temperatures. The values then mean little                                                                                                          |
| `m_eff_rounds_to_zero` | The predicted `m_eff` is at most 0.005 in size, so it starts at 0. `POST /api/calc` then answers `calculation_failed`, and a fit from it fails. Constant S of -450 to -600 µV/K from 300 to 800 K gives this. Ask the user for a mass instead |

**Limits:**

- **The guess is a starting point, with no known error bar.** The synthetic references show that a straight line gets a guess too. Nothing here says that the data look like what the nets were trained on.
- **`not_finite` comes from real sizes of Seebeck.** A constant 1 mV/K from 100 to 800 K gives it, because the net's output reaches exactly 1, which the inverse transform turns into infinity.
- **Start values carry no known issues.** A curve from them lists its own in `known_issues`; a neural estimate is not evidence that the corrected valence–valence branch is universally valid.

`tests/test_guess.py` runs the 10 cases of the [neural net references](../../packages/seeband_core/docs/neural-net-references.md) through the route: 9 give the expected `desktop_start_values` exactly, and 1 gives `no_net`. The reversed-row case uses the documented P9 override, equal to its sorted reference; the original desktop capture remains unchanged.

**Differences from the desktop**, which sets its sliders directly when an S file loads:

- P9 uses actual Tmin/Tmax and sorts paired rows on a copy. Direct callers sending unsorted rows can therefore get a net, or a different net, where the desktop uses the first and last rows. Parsed web uploads are already sorted.
- At a prediction that is not finite, the desktop raises inside its thread. An unhandled exception in a `QThread` aborted a minimal PyQt5 5.15.11 script, and the desktop has no handler for it, so it probably exits. Here, nothing is applied. The real GUI was not run for this.
- A finite prediction too large for a slider, such as a band gap of 3355444200 K from a constant 660 µV/K, raises `OverflowError` on the desktop's slider, seen on a bare `QSlider`. Here it is limited, to 3000 K, so this answers `guess` where the desktop would fail. `prediction` shows the raw value.
- `m_eff` = 0 raises in the desktop's slider handler. Here, `m_eff_rounds_to_zero` says so.
- If the fit fails, this answers `calculation_failed`, and the desktop's thread raises `TypeError`.

Median response time, in the same setting as for curves above, 20 calls each: 1.9 ms for the 30 rows of `01_Fe2VAl09Si01`, 1.4 ms for the 50 rows of `03_AWI32_SI`, 1.0 ms for a `no_net` answer on the 12 rows of `02_SiP`, and 2.5 ms for 1000 synthetic rows. The first call that a worker makes to a net took 19 ms, because it loads the weights.

## Errors

Routes and the app answer errors with this body:

```json
{
  "code": "validation_error",
  "message": "Invalid request",
  "details": [
    {
      "location": ["body", "points", 3],
      "code": "float_parsing",
      "message": "..."
    }
  ]
}
```

Clients translate by `code`, because `message` is English text for developers. `details` is an empty list unless there is something to list, and holds at most 50 problems; `details_omitted` then counts the rest, and is left out otherwise. A list of values reports only its first wrong one. Routes report errors by raising `ApiError`.

Two kinds of answer do not use this format: uvicorn's plain text 400 for malformed HTTP, which never reaches the app, and the plain text 500 when a `BaseException` escapes.

A validation error leaves out Pydantic's `input` and `ctx`, which hold submitted values. Its `message` or `location` can still quote part of a request: a dictionary key, a field that is not allowed, a discriminator tag or the text of a custom validator. That goes only to the client that sent it, and is not logged.

## Logging

Requests can carry unpublished measurements, so logs must not reveal them. This follows the rule in the `architecture` skill. The data handling decision itself is still open in [F4](https://github.com/pdasya/seeband-web/issues/4).

Each request that reaches the app writes one JSON line to stderr, with `time` in UTC, `level`, `event`, `method`, `route`, `status` and `duration_ms`. `route` is the template, such as `/api/items/{item_id}`, or `<unmatched>` if no route matched. `method` is `OTHER` for a method outside the standard set. `status` is `null` if no response started, such as after a cancellation.

| Not logged               | Why                                                                         |
| ------------------------ | --------------------------------------------------------------------------- |
| Bodies and query strings | They hold the data. The server's access log is silenced, as it logs queries |
| Raw paths                | They can hold values, so only the route template is logged                  |
| Exception messages       | A message can quote its input                                               |

An unhandled `Exception` logs its type and its `file:line:function` frames. So debugging starts from the code location, and the value that caused the failure has to be reproduced separately. The frames are those of the outer exception: chained causes and members of an exception group are not listed.

**What this does not cover:**

- **Cancellation and other `BaseException`s** continue to the server, which can print them with their messages and any chained exception. For example, a route cancelled by `--timeout-graceful-shutdown` while handling an exception.
- **Output that bypasses the middleware:** a `print`, `warnings.warn`, an uncaught exception in a thread, asyncio's `Task exception was never retrieved`, and other loggers writing to stderr. So do not put values from a request in warnings or task and thread exceptions.
- **Your own log calls:** a later `logger.info(f"...{data}")` would leak, so do not log values from a request.
- **Other server settings:** uvicorn's `--log-level trace` logs the path, query and headers. With `websockets` installed and WebSockets on, uvicorn logs the path and query of a WebSocket request at `INFO`. `python -m seeband_api` turns WebSockets off, so deployment should start the API this way.

## The contract

`packages/api-client/openapi.json` is generated from this app. See [`packages/api-client`](../../packages/api-client/README.md).
