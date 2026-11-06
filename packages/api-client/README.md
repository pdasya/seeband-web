# packages/api-client

TypeScript types generated from the API's OpenAPI contract. Do not edit `openapi.json` or `src/schema.d.ts` by hand.

```ts
import type { components } from "@seeband/api-client";

type ErrorResponse = components["schemas"]["ErrorResponse"];
```

After changing the API, run this from the repository root:

```sh
pnpm api:generate
```

Two checks catch files that are out of date, in `pnpm check` and in CI:

- `apps/api/tests/test_openapi.py` compares `openapi.json` with the app.
- `pnpm test` in this package compares `src/schema.d.ts` with `openapi.json`.

`openapi-typescript` 7.13 declares a peer dependency on TypeScript 5, and the project uses 6, so pnpm warns. The generated file passes the type check here on TypeScript 6. This package turns off `skipLibCheck`, because its only source is a `.d.ts` file.

## Mock server

To work on the client without the API, serve the contract at `http://127.0.0.1:4010`:

```sh
pnpm mock
```

It runs [Prism](https://github.com/stoplightio/prism) behind a small proxy. It serves the routes and examples in the contract, so a route appears once its API task adds it. It reloads when `openapi.json` changes, and requests during a reload can get a 502. If the file becomes invalid, the mock stops and has to be started again.

A request that breaks the contract gets a 422 `validation_error`, with its problems in `details`, as from the API. Their `code` and `message` values are Prism's, and differ from the API's.

### Switching between the mock and the API

The client calls `/api` on its own origin, and the dev server forwards `/api` to the mock on port 4010 or the API on port 8000. Use this forwarding rather than a base URL for another origin, because neither the API nor the mock's error responses send CORS headers, so a browser would hide those errors from the client. [U4](https://github.com/pdasya/seeband-web/issues/39) adds this setting.

### Testing loading and failure states

| Case                | Command or request header                                  |
| ------------------- | ---------------------------------------------------------- |
| Slow responses      | `MOCK_DELAY_MS=800 pnpm mock`                              |
| Every request fails | `MOCK_PREFER="code=500, example=internal_error" pnpm mock` |
| One request fails   | `Prefer: code=500, example=internal_error`                 |
| Invalid request     | `Prefer: code=422, example=validation_error`               |
| Not found           | `Prefer: code=404, example=not_found`                      |
| No curve            | `Prefer: code=422, example=calculation_failed`             |
| No net              | `Prefer: code=200, example=no_net`                         |
| Guess not finite    | `Prefer: code=200, example=not_finite`                     |
| Guess refused, SPB  | `Prefer: code=422, example=guess_unavailable`              |
| Disabled mode       | `Prefer: code=409, example=fit_mode_disabled`              |
| Too slow            | `Prefer: code=504, example=calculation_timeout`            |
| Worker died         | `Prefer: code=503, example=calculation_unavailable`        |
| Too many requests   | `Prefer: code=429, example=rate_limited`                   |
| Too many fits       | `Prefer: code=429, example=client_fit_limit`               |
| Request too large   | `Prefer: code=413, example=request_too_large`              |
| Iterative fit       | `Prefer: example=iterative`                                |
| Fit past its limit  | `Prefer: example=fit_timeout`                              |
| Fit process died    | `Prefer: example=fit_process_died`                         |
| Fit failed          | `Prefer: example=fit_failed`                               |

Give `example` with `code`, as otherwise Prism returns the first example whatever the status. An example name that does not exist gives `mock_error`. A request's own `Prefer` header replaces `MOCK_PREFER`. `MOCK_PORT` changes the port.

### Where the mock differs from the API

- Responses are the examples, and do not depend on the request, so `POST /api/calc` always returns the same 5-point curves and `POST /api/parse` the same 3 rows. A route's response cannot show `null` in a required field, because FastAPI drops `null` from examples. Check real curves against the API.
- `POST /api/guess` always returns the same `guess` for DPB or SPB, unless `Prefer` asks for another answer. Its `warnings` are always empty, so check those against the API.
- `POST /api/fit` sends its made-up events all at once, so a slow fit cannot be seen, and neither can a Stop. It serves `single_pass` by default. Check those against the API. `MOCK_DELAY_MS` delays the whole answer.
- A `Prefer` for an error with `Accept: text/event-stream` alone gives `mock_error`, so send `Accept: text/event-stream, application/json`, as the API's own errors are JSON too.
- A 405 has no `Allow` header, and `Accept: application/xml` gives a 406 `mock_error`, where the API answers with JSON.
- `GET /api/models` sends its `ETag`, but never answers 304.
- `POST /api/parse` checks only the shape of a request, so a mapping to a missing column or a range under 20 K passes. Its examples are `clean`, `with_errors` and `interpolated`, chosen with `Prefer: example=<name>`.
- A body over 10 MB gets Prism's own 413 format. The mock has no other limits, so it never answers `rate_limited` or `too_many_points` by itself.
