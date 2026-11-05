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
| `GET /api/openapi.json` | the contract             |
| `GET /api/docs`         | Swagger UI over the same |

## Model descriptions

`GET /api/models` returns what a client builds its forms from: models, fit modes, parameters, scales, bounds and known issues. It comes from the model registry in `seeband_core`, so a new model needs no change here. Clients revalidate it: it sends `Cache-Control: no-cache` and an `ETag`, and answers 304 if nothing changed, because a client holding old descriptions could offer a mode that is now disabled.

A mode with `disabled: true` must not be offered, and `disabled_by` names the `known_issues` entries that say why. Show their `message_key` through i18n. `meaning` and `name` are English, for a client with no translation. Fields that do not apply are left out, rather than `null`.

Requests and results use core units. Each parameter gives its control as `display_range`, what a user sees, and `core_range`, core units, both calculated by `seeband_core`. Send core values from `core_range` rather than calculating them from the scales, because the desktop divides where a multiplication changes the last bit. `step` is a keyboard increment, not a grid. `calc_scale` stays out, because it only reproduces a desktop path.

The contract holds the real response as its example, so `pnpm mock` serves real descriptions, and a change to a description shows in the diff of `openapi.json`.

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

`kind` in `POST /api/calc` chooses the curves: `measured` by default, or μ, σ, κ, the contributions of each band, or n. Each mode lists what it offers in `curves` in `GET /api/models`, and asking for another answers 422 `curve_unavailable`, with its reason as the `code` in `details`.

| Reason              | Meaning                                                      |
| ------------------- | ------------------------------------------------------------ |
| `same_as_measured`  | the total S here is the `measured` curve                     |
| `single_band`       | SPB has one band, so there are no contributions              |
| `needs_resistivity` | the mode has no scattering parameters to calculate this from |
| `not_on_desktop`    | the desktop has no such graph, so there is nothing to port   |
| `not_provided`      | a new model did not say                                      |

[`curve-availability.md`](../../packages/seeband_core/docs/curve-availability.md) holds the full matrix and how it differs from the desktop.

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
