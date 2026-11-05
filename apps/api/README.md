# apps/api

A thin FastAPI layer over `seeband_core`. It holds routes, validation and process management, and no formulas.

## Running

```sh
uv run python -m seeband_api
```

The server listens on `127.0.0.1:8000`. These environment variables change that:

| Variable                | Default     |
| ----------------------- | ----------- |
| `SEEBAND_API_HOST`      | `127.0.0.1` |
| `SEEBAND_API_PORT`      | `8000`      |
| `SEEBAND_API_LOG_LEVEL` | `INFO`      |

| Route                   | Purpose                  |
| ----------------------- | ------------------------ |
| `GET /api/health`       | status and version       |
| `GET /api/openapi.json` | the contract             |
| `GET /api/docs`         | Swagger UI over the same |

## Errors

Every error, from any route, has this body:

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

Clients translate by `code`, because `message` is English text for developers. `details` is `null` unless there is something to list.

Routes report errors by raising `ApiError`. A validation error never returns the submitted value.

## Logging

Requests can carry unpublished measurements, so logs must not reveal them. This follows the rule in the `architecture` skill. The data handling decision itself is still open in [F4](https://github.com/pdasya/seeband-web/issues/4).

Each request writes one JSON line to stderr, with `time`, `level`, `event`, `method`, `route`, `status` and `duration_ms`. `route` is the template, such as `/api/items/{item_id}`, or `<unmatched>` if no route matched. `status` is `null` if the request was cancelled before a response started.

| Never logged             | Why                                                                    |
| ------------------------ | ---------------------------------------------------------------------- |
| Bodies and query strings | They hold the data. The server's access log is off, as it logs queries |
| Raw paths                | They can hold values, so only the route template is logged             |
| Exception messages       | A message can quote its input                                          |

An unhandled exception logs its type and its `file:line:function` frames. So debugging starts from the code location, and the value that caused the failure has to be reproduced separately.

These rules hold for what goes through the middleware. A later `logger.info(f"...{data}")` would still leak, so do not log values from a request.

## The contract

`packages/api-client/openapi.json` is generated from this app. See [`packages/api-client`](../../packages/api-client/README.md).
