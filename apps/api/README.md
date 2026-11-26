# apps/api

A thin FastAPI layer over `seeband_core`. It holds routes, validation and process management, and no formulas.

## Running

```sh
uv run python -m seeband_api
```

| Variable                                  | Default                          | Applies to                                                                                                           |
| ----------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `SEEBAND_API_HOST`                        | `127.0.0.1`                      | `python -m seeband_api` only                                                                                         |
| `SEEBAND_API_PORT`                        | `8000`                           | `python -m seeband_api` only                                                                                         |
| `SEEBAND_API_LOG_LEVEL`                   | `INFO`                           | the API's own log lines, not uvicorn's own                                                                           |
| `SEEBAND_API_CALC_WORKERS`                | `2`                              | worker processes for calculations                                                                                    |
| `SEEBAND_API_CALC_TIMEOUT_S`              | `30`                             | how long a calculation, parse or guess can run once a worker has it                                                  |
| `SEEBAND_API_CALC_MAX_WAITING`            | `8`                              | jobs waiting for a worker, beyond one for each                                                                       |
| `SEEBAND_API_CALC_WAIT_TIMEOUT_S`         | `10`                             | how long a job may wait for a worker                                                                                 |
| `SEEBAND_API_CALC_MAX_PER_CLIENT`         | `4`                              | calc, parse and guess requests of one client at once, counted before their body is read                              |
| `SEEBAND_API_CALC_MAX_RUNNING_PER_CLIENT` | workers − 1                      | jobs of one client running at once, so another client always has a worker                                            |
| `SEEBAND_API_BODY_TIMEOUT_S`              | `60`                             | how long a request's body may take to arrive in all                                                                  |
| `SEEBAND_API_BODY_IDLE_TIMEOUT_S`         | `10`                             | how long a request's body may pause                                                                                  |
| `SEEBAND_API_MAX_CONCURRENT_REQUESTS`     | `100`                            | requests at once, past which 503 `server_busy`; `/api/health` is never refused                                       |
| `SEEBAND_API_LIMIT_CONCURRENCY`           | `1000`                           | uvicorn's own cap, a backstop: its 503 is plain text and refuses health too; `python -m seeband_api` only            |
| `SEEBAND_API_FIT_MAX_RUNNING`             | `2`                              | fits at once, in each server process                                                                                 |
| `SEEBAND_API_FIT_MAX_WAITING`             | `4`                              | fits waiting, before a 429                                                                                           |
| `SEEBAND_API_FIT_TIMEOUT_S`               | `180`                            | how long one fit can run                                                                                             |
| `SEEBAND_API_FIT_MAX_PER_CLIENT`          | `2`                              | fits running or waiting for one client                                                                               |
| `SEEBAND_API_MAX_BODY_BYTES`              | `10000000`                       | size of a request to `/api/parse` and any route not below                                                            |
| `SEEBAND_API_MAX_JSON_BODY_BYTES`         | 1 MB, or what `max_points` needs | size of a request to calc, fit, guess and band-diagram; set below what `max_points` needs, the server warns at start |
| `SEEBAND_API_MAX_POINTS`                  | `2000`                           | points of a quantity, or rows of a text                                                                              |
| `SEEBAND_API_CALC_PER_MINUTE`             | `600`                            | `POST /api/calc` for one client                                                                                      |
| `SEEBAND_API_BAND_DIAGRAM_PER_MINUTE`     | `600`                            | `POST /api/band-diagram` for one client                                                                              |
| `SEEBAND_API_PARSE_PER_MINUTE`            | `60`                             | `POST /api/parse` for one client                                                                                     |
| `SEEBAND_API_GUESS_PER_MINUTE`            | `60`                             | `POST /api/guess` for one client                                                                                     |
| `SEEBAND_API_FIT_PER_MINUTE`              | `30`                             | `POST /api/fit` for one client                                                                                       |
| `SEEBAND_API_TRUSTED_PROXIES`             | `127.0.0.1,::1`                  | whose `X-Forwarded-For` to believe. `python -m seeband_api` only                                                     |

| Route                    | Purpose                      |
| ------------------------ | ---------------------------- |
| `GET /api/health`        | status, version and commit   |
| `GET /api/ready`         | whether calculations can run |
| `GET /api/models`        | model descriptions           |
| `POST /api/calc`         | curves and RMSE              |
| `POST /api/band-diagram` | local parabolic bands E(k)   |
| `POST /api/parse`        | reading measured data        |
| `POST /api/guess`        | initial parameter estimates  |
| `POST /api/fit`          | fitting, as event stream     |
| `GET /api/demo`          | synthetic dataset            |
| `GET /api/openapi.json`  | the contract                 |
| `GET /api/docs`          | Swagger UI over the same     |

`GET /api/health` says the server answers; `GET /api/ready` answers 200 only once the calculation workers have started and answered their warm-up, and 503 `not_ready` with `Retry-After` while they start or are replaced after a crash. A proxy or a container's health check should use readiness before sending traffic. Neither is ever refused as too busy.

`commit` in `GET /api/health` is the commit the API runs from: `SEEBAND_COMMIT`, which an image should set as it is built, or git's in a checkout, with `-dirty` for uncommitted changes, or null when neither knows. The app's own build reads its commit the same way, and exports and the report name both.

## Limits

**Calculations go through a queue** (A14). Calc, parse and guess run in a pool of worker processes, and a queue in the API admits their jobs.

- **One slot for each worker,** held until the worker has finished, also after a 504, so the pool never holds a backlog of abandoned jobs. A job still running at twice `calc_timeout_s` is stuck: its workers are replaced, and other jobs on them end as 503.
- **Clients take turns.** A free slot goes to the waiting client served longest ago, one job each, and one client runs at most `calc_max_running_per_client` jobs at once, by default one fewer than the workers. So a client sending heavy jobs without pause always leaves a worker for others.
- **A bounded wait.** Past the slots, at most `calc_max_waiting` jobs wait, each for at most `calc_wait_timeout_s`. A waiting job whose client has gone leaves within 100 ms, before it reaches a worker, and a new job finding the queue full waits that long for such jobs before it is refused.
- **Before the body.** One client can have `calc_max_per_client` requests to these routes at once, counted before their body is read, so a client over it is refused before its 3 MB text is decoded.
- **Refusals are fast, with `Retry-After`:** 429 `client_calc_limit`, or 503 `calculation_busy` with a wait estimated from the jobs ahead and their usual run time, between 1 and 30 s. The web app tries again after it, as for a 429.
- **A worker that dies** breaks the pool, which is replaced at once, also when no request is waiting for that worker any more, as after its 504.
- **Logs.** Each job logs `calc_job` with its `job`, `queue_wait_ms`, `run_ms`, `abandoned` and `timed_out`, never its arguments. A request dropped for its client leaving answers 499 `calculation_abandoned`, which nobody reads, so it stays apart from overload.
- **Threads.** `python -m seeband_api` sets `OMP_NUM_THREADS` and its kin to 1, so each worker's linear algebra takes one core.

Measured through a real server on one Mac, with default settings and raised rates: one address ran 16 loops of heavy calcs of 1000 points (0.7 s each) and 4 of parses of the largest text (2.5 s each) for 8 s, while another asked for light curves. The other's p95 was 0.05 to 0.06 s, against 1.43 s before the turns, and the flooder's refusals took 0.03 s at p95. `tests/test_calc_flood.py` checks a p95 under 1 s and refusals under 0.1 s. `tests/test_calc_admission.py` checks the turns and caps, 12 aborted heavy jobs at the default queue, a worker that dies after its 504, a stuck job and closing the pool in the middle of a job.

**A request's body must arrive within `body_timeout_s`, with no pause over `body_idle_timeout_s`**, or the answer is 408 `request_timeout` and the connection closes. So half-sent bodies do not hold the server, while a large file on a slow but steady link gets through: 3 MB at 2 Mbit/s takes about 12 s. The limits end before a route runs, so they do not cut a fit's stream. **Past `max_concurrent_requests` at once**, the answer is a fast 503 `server_busy` in JSON with `Retry-After`, never for `/api/health`, so a probe does not restart a server that is only busy. Timeouts for headers and idle connections belong to the proxy (#53).

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
- **Behind a proxy, set `SEEBAND_API_TRUSTED_PROXIES` to its address,** in Compose the network of the proxy's container, never `*` on a reachable port. Otherwise every user counts as the proxy's one address, and the per-client limits act as limits for all. The server then takes the client's address from `X-Forwarded-For`, from the right, skipping trusted addresses, so a client cannot choose its own. Without this, the proxy is the only client, and all users share one limit. [I1](https://github.com/pdasya/seeband-web/issues/53) must set it, and must not expose the API directly if it trusts `*`. Plain `uvicorn` uses its own `FORWARDED_ALLOW_IPS` instead.

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
- **Parameter status:** `parameter_status` says how the fit found each parameter, the first that applies of `held`, `fixed`, `not_assessed` (a failed fit, or a stage never reached, as m1 in a stopped Hall fit), `at_bound`, `not_assessed` (a stage with no more points than parameters to fit, or a legacy stage error that is not finite: scipy then gives no covariance, while the values may fit exactly), `not_determined`, `not_assessed` (any other parameter of a fit that is stopped, at its iteration limit or stalled), `did_not_move` (within 1e-9 relative of its start) and `estimated`. `not_determined` comes from a legacy stage error of exactly 0, which is a Jacobian column of zeros, an unidentified parameter of the verified method, or the DPB E_F in the gap, 0 ≤ E_F ≤ E_g, with m_eff > 0: both bands are then empty at 0 K for every such E_F, so the curves are the same to the bit, and the data say only that E_F lies in the gap. `estimated` means only that no signal said otherwise. `uncertainty` is `not_assessed` for every fit until #182. A verified fit with E_F inside the gap fails its derivative check, so E_F is `not_assessed` there.
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

A process starts for each fit. It is forked from a fork server that the app starts at startup, which has imported the core and scipy.optimize, so it reaches its job in about 5 ms. A fresh interpreter took about 0.44 s, mostly for imports (A16). If the fork server dies, the next fit starts it again and waits for its imports, about 0.3 s. A fit already running then has no exit code to report, which multiprocessing takes for ended, so a stop signals its pid directly. The fork server's children then belong to PID 1, so in a container PID 1 must reap them: run it with `init: true` or tini. Startup fails if the fork server has not finished its imports after 60 s.

A script that starts the app, rather than `python -m seeband_api` or `python -m uvicorn`, needs an `if __name__ == "__main__":` guard, as under `spawn` before: each child runs the script again, and without the guard it starts a server of its own. It ends with its request, whichever way the request ends: past the time limit, on a disconnect, or at a stop of the server. It is terminated, and killed if it stays, about 1 ms after a Stop. A process also exits if the server dies.

An SPB S fit of the demo dataset from the default start, posted 7 times in a row with `urllib` to `python -m seeband_api` on an Apple Silicon Mac with 10 cores, median: legacy 509 → 103 ms, verified 779 → 351 ms, before and after A16. The same fit called in the core takes 75 and 325 ms. A Stop ended the fit's process in about 1 ms, and `tests/test_fit_runner.py` checks for less than 0.1 s.

The calc pool's workers fork from the same server, and a new pool, at startup or after a worker died, gives out no job until its warm-up jobs have answered. So a job's time limit starts on a pool that serves. The workers share one queue, so this shows that each was started, not that each has answered. A warm-up that has not answered after 10 s gets new workers and logs `calc_warm_up_stuck`, and a worker that dies in its warm-up gets new workers at once. A replacement starts the fork server again in a thread, if it has died, so the event loop goes on meanwhile.

Each process keeps numpy's linear algebra to one thread, as `seeband_api.processes` sets `OMP_NUM_THREADS` and its kin to 1 unless they are set, also when the server is started other than by `python -m seeband_api`.

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
- **A nonfinite curve point** usually comes back as `null`, with the rest of the curve.
- **`calculation_failed`** is a 422 with no curve. If the band parameters are
  outside the finite-root domain, the response names the reason in `details`
  at `body.parameters`:
  - `chemical_potential_zero_mass` for zero band mass in SPB or a zero mass ratio in DPB.
  - `chemical_potential_spb_fermi_energy` for `sign(m) × E_F ≤ 0`.
  - `chemical_potential_dpb_fermi_energy` for two valence bands with `E_F ≥ max(0, E_g)`.

  Clients can map these calculation detail codes directly to user guidance.
  Known-issue IDs come from the model registry. An uncertifiable root or an
  invalid transport result gets the general error. The API logs only the
  exception type.

- **`measured_points`** holds points made from the `measurements` sent, with no model: `electrical_conductivity_s_per_m` is 1/ρ at each ρ temperature, with `null` for a ρ of 0 or below. They go with the data the request sent: points in the fit range, as a client sends for the RMSE, and of interpolated ρ when it sends interpolated values. `seeband_core.measured_points` makes them. There are no κ_e points: κ_e is not measured, and an estimate from ρ needs a Lorenz number, which was decided against in #159.
- **RMSE** for built-in SPB/DPB models evaluates the final parameters directly at each submitted measurement temperature. `points` and `rmse_points` do not affect this metric. Submitted points may be interpolated by the client. Custom registered models retain the grid-based fallback controlled by `rmse_points`. `/api/calc` retains its `422 zero_measured_value` rejection for submitted zero ρ/Hall measurements; the web preview excludes those points. The core metric helper itself returns an unavailable percentage for zeros. Fit diagnostics separately provide absolute RMSE and relative L2 when defined.
- **`calculation_unavailable`** is a 503: a worker died, and the next request gets a new pool.
- **`calculation_timeout`** is a 504. A worker cannot be interrupted, so it stays busy until the calculation ends, and its slot in the queue stays taken until then.
- **`calculation_busy`** is a 503 with `Retry-After`, when the queue is full or a job waited `calc_wait_timeout_s` for a worker. **`client_calc_limit`** is a 429 with `Retry-After`, when the client already has `calc_max_per_client` jobs. Both come at once, rather than after a run's whole time.

Requests are parsed in the event loop, up to the size in [Limits](#limits). A body of 9 MB of numbers took about 0.13 s in all, and the largest allowed grids, `points` and `rmse_points` of 1000, take about 1.3 s each.

Median response time for a 50-point curve, with P19 and A15, through the app in one process with a test client, 20 calls each, on an Apple Silicon Mac with 10 cores and Python 3.13. The RMSE column uses the 31 points per quantity of the demo dataset. Network time is not included, and FS12 measures that.

| Mode, with default scattering | Curves | Curves and RMSE |
| ----------------------------- | ------ | --------------- |
| `spb_s`                       | 7 ms   | 11 ms           |
| `spb_s_rho`                   | 7 ms   | 15 ms           |
| `dpb_s`                       | 11 ms  | 17 ms           |
| `dpb_s_rho`                   | 11 ms  | 23 ms           |
| `dpb_s_rho_rh`                | 12 ms  | 35 ms           |

Before A15 (#174), on main with P19, the same run on the same Mac gave 13, 22, 20, 35 and 53 ms for curves, and 20, 37, 32, 57 and 96 ms with RMSE. Two changes made it faster, and neither changes a number, to the bit:

- A Fermi integral of one value calls `fdint_robust` directly instead of through `np.vectorize`.
- Within one curve or fit, μ(T) is solved once for each temperature array and set of band parameters, and S, ρ and R_H reuse that root. Only solved roots are kept, at most 32, and nothing is kept after the call returns.

Fits on `01_Fe2VAl09Si01` from the default start, in the core without a worker process, on the same Mac, before and after:

| Mode, scattering     | Verified, the default | Legacy        |
| -------------------- | --------------------- | ------------- |
| `dpb_s`              | 4.8 s → 2.4 s         | 0.8 s → 0.3 s |
| `spb_s_rho`, acPh    | 0.7 s → 0.3 s         | 0.2 s → 0.1 s |
| `dpb_s_rho`, acPh    | 73 s → 36 s           | 1.1 s → 0.4 s |
| `dpb_s_rho_rh`, acPh | 46 s → 23 s           | 1.1 s → 0.5 s |

Each fit ends with the same status and number of iterations as before. The verified `dpb_s_rho_rh` fit ends at `iteration_limit` after 20 iterations.

`packages/seeband_core/tests/test_calc_speed_equivalence.py` compares every model, mode, scattering and curve kind, and fits of both algorithms, also with solves that fail on the way, with both changes off and on.

For `POST /api/band-diagram`, `wavevector_nm_inv` gives k in nm⁻¹ and
each energy curve gives E/k_B in K. The Fermi level is constant across k.
The response sets `reference_mass_assumed` in modes without Hall data, SPB or
DPB, where no data set the size of a mass, so band 1's curvature takes a mass
magnitude of one electron mass, keeping its sign. With Hall data the curvature
follows the current masses, which the data set only once a fit has run.

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

## Ionized impurity scattering

Core 0.3.0 exposes `ionized` alongside `acPh` and `dis` for SPB and DPB,
including S-only. `acPhDis` and C/D parameters are no longer public choices.
Ionized fits require `verified-sequential-v2`; legacy requests are rejected.
`POST /api/guess` accepts optional `scattering`; SPB numerical estimates use
it, while ionized DPB requests return `unsupported` with reason
`scattering_not_supported` without running the acoustic-trained neural net.
See [the physical contract](../../packages/seeband_core/docs/ionized-impurities.md).

### Explicit double parabolic bands (core 0.4.0)

From core 0.4.1, apply the selected scattering entry in
`fit_modes[].parameter_overrides` by parameter name before building the
editor, fit or curve request. Explicit ionized `dpb_s` accepts an optional
fixed `parameters.B` (or `start.B` in a fit), default 1. In the two modes with
resistivity B uses fitted bounds [0, 10000] by default. The empirical
conductivity prefactor is (N₂/N₁)B/M. Omitting the fixed S-only input
replays old requests with unit weight.

New explicit DPB sessions request `GET /api/models?parameterization=explicit_fermi_v1`.
Send the same discriminator, the band configuration and both positive integer
valley counts on calculation, fit and diagram requests.
Include `fermi_energy` in the parameter vector, in kelvin from the first band
edge at zero temperature. Fit it with researcher-selected bounds or hold it
at its supplied value. The model computes the signed electron excess from
the trial energy and band parameters and conserves it across temperature.
The band populations determine the sign, including exact compensation.
Historical requests that explicitly supply `carrier_type` retain their sign constraint. The API rejects a simultaneous fixed density input.

The band diagram draws a supplied Fermi energy and both dispersions even
when that energy is outside the transport domain. In VB+VB, transport
requires `fermi_energy < max(0, band_offset_k)`; CB+CB requires
`fermi_energy > min(0, band_offset_k)`. For calculations and fits, HTTP 422
includes the detail code `fermi_energy_unoccupied_bands` for a same-type
pair with zero carrier population, or `fermi_energy_carrier_mismatch` when
the mixed-band excess conflicts with a supplied historical carrier type.

`GET /api/dpb/parameter-domain` returns the admissible interval for one
manual control (`fermi_energy`, `band_offset_k` or `mass_ratio`) at the
current values of the other parameters. Energies use kelvin. A null endpoint
is unbounded. The response distinguishes inclusive endpoints and empty intervals.
In VB+CB the interval includes exact electron–hole compensation, including
the whole gap when the bands are separated. With overlapping bands the
compensation energy depends on the mass ratio and both valley multiplicities.
A signed request can use this endpoint to inspect a one-parameter slice.
The researcher chooses fit bounds independently.

Request `GET /api/models?parameterization=explicit_density_v1` for the saved fixed-density
parameter names and bounds. On calculation, fit and diagram requests send
`model: "dpb"`, `parameterization: "explicit_density_v1"`, `band_configuration`
(`vb_vb`, `vb_cb` or `cb_cb`), `net_electron_density_per_m3` and both positive integer
`band_1_degeneracy` and `band_2_degeneracy`. Use `mass_ratio`, `band_offset_k`,
`m1` and the mode's listed scattering parameters in the parameter vector.
Fit requests supply bounds for each active free parameter. The explicit
model uses verified sequential fitting with manual starts. Direct requests
omitting the discriminator use the historical Fermi-energy parameterization.

`POST /api/dpb/migrate` converts one legacy parameter vector. Supply
`parameters`, the absolute `m1` and both multiplicities; the reply supplies
the explicit vector, configuration and carrier excess. Old fit bounds must
be chosen again in the new coordinates. The physical band diagram returns
wavevector in nm⁻¹. For a supplied Fermi energy the diagram draws one Fermi
line. A historical density-only intrinsic sample with a positive gap returns
the two endpoints of its admissible zero-temperature interval.
