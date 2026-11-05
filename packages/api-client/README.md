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

It runs [Prism](https://github.com/stoplightio/prism) behind a small proxy, and restarts its routes when `openapi.json` changes. It serves the routes and examples in the contract, so a route appears once its API task adds it. Requests that break the contract get a 422 in the API's error format. Responses are always the example, and do not depend on the request.

The client calls `/api` on its own origin, so switching is a matter of where the dev server forwards `/api`: the mock on port 4010, or the API on port 8000. [U4](https://github.com/pdasya/seeband-web/issues/39) adds this setting.

To test loading and failure states:

| Case                | Command or request header                                  |
| ------------------- | ---------------------------------------------------------- |
| Slow responses      | `MOCK_DELAY_MS=800 pnpm mock`                              |
| Every request fails | `MOCK_PREFER="code=500, example=internal_error" pnpm mock` |
| One request fails   | `Prefer: code=500, example=internal_error`                 |
| Invalid request     | `Prefer: code=422, example=validation_error`               |
| Not found           | `Prefer: code=404, example=not_found`                      |

Give `example` with `code`, as otherwise Prism returns the first example whatever the status. A request's own `Prefer` header replaces `MOCK_PREFER`. `MOCK_PORT` changes the port.

The mock cannot do what depends on the request, such as real curves, or stream events. Check those against the API.
