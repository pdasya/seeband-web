# apps/api

A thin FastAPI layer over `seeband_core`. It holds routes, validation and process management, and no formulas.

## Running

```sh
uv run python -m seeband_api
```

| Variable                     | Default     | Applies to                                 |
| ---------------------------- | ----------- | ------------------------------------------ |
| `SEEBAND_API_HOST`           | `127.0.0.1` | `python -m seeband_api` only               |
| `SEEBAND_API_PORT`           | `8000`      | `python -m seeband_api` only               |
| `SEEBAND_API_LOG_LEVEL`      | `INFO`      | the API's own log lines, not uvicorn's own |
| `SEEBAND_API_CALC_WORKERS`   | `2`         | worker processes for calculations          |
| `SEEBAND_API_CALC_TIMEOUT_S` | `30`        | how long a calculation request waits       |

| Route                   | Purpose                  |
| ----------------------- | ------------------------ |
| `GET /api/health`       | status and version       |
| `GET /api/models`       | model descriptions       |
| `POST /api/calc`        | curves and RMSE          |
| `POST /api/parse`       | reading measured data    |
| `POST /api/guess`       | neural net start values  |
| `GET /api/openapi.json` | the contract             |
| `GET /api/docs`         | Swagger UI over the same |

## Model descriptions

`GET /api/models` returns what a client builds its forms from: models, fit modes, parameters, scales, bounds and known issues. It comes from the model registry in `seeband_core`, so a new model needs no change here. Clients revalidate it: it sends `Cache-Control: no-cache` and an `ETag`, and answers 304 if nothing changed, because a client holding old descriptions could offer a mode that is now disabled.

`has_initial_guess` says that a model has the neural net of `POST /api/guess`, which is DPB only.

A mode with `disabled: true` must not be offered, and `disabled_by` names the `known_issues` entries that say why. Show their `message_key` through i18n. `meaning` and `name` are English, for a client with no translation. Fields that do not apply are left out, rather than `null`.

Requests and results use core units. Each parameter gives its control as `display_range`, what a user sees, and `core_range`, core units, both calculated by `seeband_core`. Send core values from `core_range` rather than calculating them from the scales, because the desktop divides where a multiplication changes the last bit. `step` is a keyboard increment, not a grid. `calc_scale` stays out, because it only reproduces a desktop path.

The contract holds the real response as its example, so `pnpm mock` serves real descriptions, and a change to a description shows in the diff of `openapi.json`.

## Reading data

`POST /api/parse` reads measured data from the text of a file or table, and optionally interpolates it. [`input-data.md`](../../packages/seeband_core/docs/input-data.md) lists the format and every code, and [`interpolation.md`](../../packages/seeband_core/docs/interpolation.md) the interpolation.

- **Input** is JSON with `text`, up to 2 000 000 characters, not a file upload. A multipart parser writes large uploads to a temporary file, so with JSON nothing reaches the disk. The client reads the file and decodes it, and should look for a byte order mark: UTF-16 read as UTF-8 gives `wrong_encoding`, and a header in Latin-1 can lose a character, which `unit_differs` then reports.
- **A file with problems is a 200,** with the problems in `errors` and a `preview`, so that a client can show them and let a user assign columns. `measurements` is empty with any error. A 422 means that the request itself is wrong.
- **Assigning columns:** send the text again with `mapping`, as the API keeps nothing between calls. A choice is kept even while some rows have errors. A column that does not exist gives a 422 `invalid_parse_request` with `unknown_column`. With no readable rows, there is nothing to check it against, and `mapping` stays the suggestion.
- **`interpolate`** gives each quantity on a grid over a fit range, in `interpolated`, next to the original `measurements`. A range the grid cannot use is a 422 `invalid_parse_request` with `invalid_interpolation_range`. A polynomial that overflows gives `null`, which a client must not send on to `POST /api/calc`, as it refuses it. One quantity that cannot be interpolated is named in `interpolation_failed`, and the others stay. Pass `extrapolated` on to `POST /api/calc` if any quantity sets it, as made-up points enter its results.
- **Body size** has no general limit until [A10](https://github.com/pdasya/seeband-web/issues/33), so a larger body is read into memory before `text` is refused.

## Curves

`POST /api/calc` returns curves for given parameters, in core units. It keeps no state, and runs in a pool of worker processes, so that the event loop stays free. Add `measurements` to get an RMSE for each quantity. Send only points in the fit range.

- **Parameters:** all of a mode's parameters are needed, and values outside a control's range are allowed, because a fit can end there. Names are checked, and problems are listed in `details`. Numbers must be JSON numbers: `true` or `"1.5"` are refused.
- **A disabled mode** gets a 409 `fit_mode_disabled`, with the ids of its known issues as the `code` in `details`. Show `known_issue.<code>` through i18n.
- **A value that is not finite** usually comes back as `null`, with the rest of the curve, as with a band mass of 0.
- **`calculation_failed`** is a 422 that loses the whole curve, because the core raises. This happens at `m_eff` = 0, which divides by zero, and in DPB S + ρ + R_H where a value at low temperature is not finite: at 2 to 300 K, 55 of 100 random parameter sets inside the control ranges failed, and none at 10 to 300 K or 50 to 800 K. In DPB S + ρ, the same condition gives one `null` instead. A measured point at a low temperature can cause it through the RMSE grid too. A negative m1 fails too, as it gives complex values. The API logs the exception's type.
- **RMSE** uses a grid of 50 points by default, for speed. Ask for `rmse_points: 200` for a value to report: on the demo dataset, 50 points changed an RMSE by about 0.3 % at default parameters, and up to about 4 % near a good fit.
- **`calculation_unavailable`** is a 503: a worker died, and the next request gets a new pool.
- **`calculation_timeout`** is a 504. A worker cannot be interrupted, so it stays busy until the calculation ends.

Requests are parsed in the event loop, and there are no size limits until [A10](https://github.com/pdasya/seeband-web/issues/33). A body of 137 MB held up other requests for about a second, and the largest allowed grids, `points` and `rmse_points` of 1000, take about 1.3 s each.

Median response time for a 50-point curve, through the app in one process with a test client, 20 calls each, on an Apple Silicon Mac with 10 cores and Python 3.13. The RMSE column uses the 31 points per quantity of the demo dataset. Network time is not included, and FS12 measures that.

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

`POST /api/guess` takes `model`, `temperature_k` and `seebeck_v_per_k`, and answers with DPB start values from the neural net. For DPB data that fit the contract, it answers 200, apart from the errors listed below, and `status` says which of three answers it is:

| `status`     | Meaning                                                                                                | Holds                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| `guess`      | a net fits, and its prediction is finite                                                               | `net_range`, `start_values`, `prediction`, `warnings`                       |
| `no_net`     | the first and last rows span no net's range, with `reason` `temperature_span`. Keep the current values | `first_temperature_k`, `last_temperature_k`, `available_ranges`, `warnings` |
| `not_finite` | a net fits, but a value of its prediction is not finite. Keep the current values                       | `net_range`, `warnings`                                                     |

- **Use `start_values`, unless the warning `m_eff_rounds_to_zero` is there.** They go into `parameters` of `POST /api/calc`, by the names in `GET /api/models`, and the mode's other parameters keep their values. `m_eff` is dimensionless, and `band_gap` and `fermi_energy` are in K. For these three, the core and displayed numbers are the same in every DPB mode. They are rounded and limited as the desktop's sliders do, so they lie in `core_range`: a gap of 52464 K starts at 3000 K. `step` does not apply: 554 K is a valid gap.
- **`prediction` is the net's own result**, before rounding and limits, in `m_eff`, `band_gap_k` and `fermi_energy_k`. It equals the core's exactly.
- **`net_range` is the real range of the net that was used.** Show it, rather than a fixed text.
- **Send every row of the Seebeck data, in V/K.** The desktop reads the whole file, not the fit range, unlike `POST /api/calc`.
- **SPB gets a 422 `guess_unavailable`**, as only DPB has nets. A client should read `has_initial_guess` in `GET /api/models`, rather than name DPB. An unknown model gets a 422 `invalid_guess`.
- **`calculation_failed`** is a 422 for a fit that fails. It did not happen in 20000 random requests with extreme finite values, run through the core on one Mac, so it should be rare. `calculation_unavailable` and `calculation_timeout` are as in `POST /api/calc`.

`warnings` holds codes for a client to show through i18n, as `guess_warning.<code>`. The answer still follows the data:

| Code                   | Meaning                                                                                                                                                                                                                                       |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `unsorted_temperature` | The rows do not rise. The net is still chosen by the first and last rows, as on the desktop, until [P9](https://github.com/pdasya/seeband-web/issues/88). The parser sorts its rows, so it does not send these                                |
| `underdetermined_fit`  | The data do not set the degree-5 polynomial behind the net's input, which takes 6 distinct temperatures. The values then mean little                                                                                                          |
| `m_eff_rounds_to_zero` | The predicted `m_eff` is at most 0.005 in size, so it starts at 0. `POST /api/calc` then answers `calculation_failed`, and a fit from it fails. Constant S of -450 to -600 µV/K from 300 to 800 K gives this. Ask the user for a mass instead |

**Limits:**

- **The guess is a starting point, with no known error bar.** The synthetic references show that a straight line gets a guess too. Nothing here says that the data look like what the nets were trained on.
- **`not_finite` comes from real sizes of Seebeck.** A constant 1 mV/K from 100 to 800 K gives it, because the net's output reaches exactly 1, which the inverse transform turns into infinity.
- **Start values carry no known issues.** A curve from them lists its own in `known_issues`, such as `negative_m_eff_weight`.

`tests/test_guess.py` runs the 10 cases of the [neural net references](../../packages/seeband_core/docs/neural-net-references.md) through the route: the 8 with a net give the recorded `desktop_start_values` exactly, and the 2 without give `no_net`.

**Differences from the desktop**, which sets its sliders directly when an S file loads:

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

Clients translate by `code`, because `message` is English text for developers. `details` is an empty list unless there is something to list. Routes report errors by raising `ApiError`.

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
