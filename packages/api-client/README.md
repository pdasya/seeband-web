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

- `apps/api/tests/test_openapi.py`, and a CI step, compare `openapi.json` with the app.
- `pnpm test` in this package compares `src/schema.d.ts` with `openapi.json`.

`openapi-typescript` 7.13 declares a peer dependency on TypeScript 5, and the project uses 6. pnpm warns about this. Generation and type checks pass on 6.
