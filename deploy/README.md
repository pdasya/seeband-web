# deploy

The whole service on one machine, in one Docker Compose project: the API, and Caddy, which serves
the public site and the app and proxies the API. Everything has one origin, so the app needs no
CORS.

## Run it

From the repository root, with Docker:

```sh
cp deploy/.env.example deploy/.env   # optional; the defaults run locally
docker compose -f deploy/compose.yaml up --build
```

Then open http://localhost:8080. `docker compose -f deploy/compose.yaml down` stops it.

On a host, set `SEEBAND_SITE_ADDRESS` to the domain and the ports to 80 and 443 in `deploy/.env`.
Caddy then gets a certificate from Let's Encrypt and keeps it in the `caddy_data` volume. The same
images run on both hosts; only `deploy/.env` differs. It holds every setting and any secret, and
stays out of the repository.

## What runs

| Container | Image                                                                      | Serves                                               |
| --------- | -------------------------------------------------------------------------- | ---------------------------------------------------- |
| `api`     | `api.Dockerfile`: Python 3.13 slim, packages exactly as in `uv.lock`       | the API on port 8000, inside the network only        |
| `web`     | `web.Dockerfile`: the site and the app built with Node 24, served by Caddy | ports 80 and 443 of the host (8080 and 8443 locally) |

**Caddy** (`Caddyfile`) routes by path:

- `/api/*` to the API. Each event of a fit's stream goes on at once (`flush_interval -1`), and a
  stream that the browser closes, as on Stop, ends the upstream request, which stops the fit's
  process. Responses are not compressed, so the stream is not held back.
- `/fit`, `/results` and below them: the app's `index.html`, which routes in the browser, with
  `X-Robots-Tag: noindex`. A new screen needs its path here and in `APP_SCREENS` of
  `apps/site/src/strings.ts`.
- `/assets/*` and `/licenses/*`: the app's files; assets are cached for a year, as their names
  change with their contents.
- Everything else: the site, one directory per page, with its `404.html`.
- On every answer: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Permissions-Policy`, and no `Server`. No `Content-Security-Policy` or HSTS yet.

**Logs** hold method, path, status and duration. Caddy's access log drops headers, cookies and
addresses, and the API logs no bodies, as the overview promises. Measurements only travel in
bodies.

**The API**

- **Runs as a user, not root.** The file system is read-only, with `/tmp` in memory for the fork
  server's socket.
- **Linear algebra uses one thread in each process.** `OMP_NUM_THREADS` and its kin are set to 1.
- **Trusts `X-Forwarded-For` only from Caddy's network** (`SEEBAND_API_TRUSTED_PROXIES`). Each user
  therefore counts as their own client for the rate limits and the queue.
- **Health check.** Docker checks `GET /api/ready`, which answers only once the calculation workers
  have started. Caddy starts after that.
- **Stopping.** On a stop, running requests get 5 s, then each fit's process ends with its request.

**The process budget** is set by `SEEBAND_API_CALC_WORKERS` and `SEEBAND_API_FIT_MAX_RUNNING`. Their
defaults, 2 and 2, are meant for the planned 2 vCPUs. The independent review of 2026-11-11 found
that they oversubscribe such a machine under mixed load, so measure them on the machine itself
(I3, #55) before changing them.

## Checked

- **CI.** The `Containers` job of CI builds both images and starts the stack. It then checks the
  site, the app, `noindex` on the app, the 404 page, readiness, the commit in `/api/health`, and a
  calculation, all through Caddy. It also checks that the API runs as a user on a read-only file
  system.
- **Locally, without Docker.** The `Caddyfile` was run with Caddy 2.10.2 in front of the API and
  production builds of the site and the app. Every route above answered as described. A DPB
  S + ρ + R_H fit streamed its iterations through Caddy, and Stop ended it together with its
  process.
- **Not yet.** A run on the target machine, with the review's mixed load and its p50/p95/p99, memory
  and orphan processes, is part of I3.
