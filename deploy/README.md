# deploy

The whole service on one machine, in one Docker Compose project: the API, and Caddy, which serves
the public site and the app and proxies the API. Everything has one origin, so the app needs no
CORS.

## Run it

From the repository root, with Docker 27 or newer:

```sh
cp deploy/.env.example deploy/.env   # optional; the defaults run locally
docker compose -f deploy/compose.yaml up --build
```

Then open http://localhost:8080. `docker compose -f deploy/compose.yaml down` stops it.

On a host, set in `deploy/.env`:

- `SEEBAND_SITE_ADDRESS` to the domain;
- the ports to 80 and 443.

Caddy then gets a certificate from Let's Encrypt and keeps it in the `caddy_data` volume. The same
images run on both hosts; only `deploy/.env` differs. That file holds every setting and any secret,
and stays out of the repository. Set `SEEBAND_COMMIT` in the shell when building, not in the file:
the file also goes into the API container, where an empty value would hide the image's commit.

## What runs

| Container | Image                                                                      | Serves                                               |
| --------- | -------------------------------------------------------------------------- | ---------------------------------------------------- |
| `api`     | `api.Dockerfile`: Python 3.13 slim, packages exactly as in `uv.lock`       | the API on port 8000, inside the network only        |
| `web`     | `web.Dockerfile`: the site and the app built with Node 24, served by Caddy | ports 80 and 443 of the host (8080 and 8443 locally) |

Base images are pinned by digest. Dependabot proposes new digests and patch releases monthly (`.github/dependabot.yml`), and Caddy's minor releases. Python stays on 3.13 and Node on 24, the versions CI tests: a move to a new version is a task of its own, with the tests, golden results and CI moved too.

**Caddy** (`Caddyfile`) routes by path:

- `/api/*` to the API.
  - Each event of a fit's stream goes on at once (`flush_interval -1`).
  - A stream the browser closes, as on Stop, ends the upstream request, which stops the fit's
    process.
  - Responses are not compressed, so the stream is not held back.
  - Bodies over 10 MB, the API's largest limit, are refused here.
  - Idle connections to the API close after 4 s, before uvicorn closes them after 5 s, so a request
    never goes out on a closing connection.
- `/fit`, `/results` and below them: the app's `index.html`, which routes in the browser, with
  `X-Robots-Tag: noindex`. A new screen needs its path here and in `APP_SCREENS` of
  `apps/site/src/strings.ts`.
- `/assets/*` and `/licenses/*`: the app's files. Assets are cached for a year, as their names
  change with their contents.
- Everything else: the site, one directory per page. `/guide` redirects to `/guide/`, so each page
  has one address.
- Errors: Caddy's own errors, a missing page (with the site's `404.html`) or the API down, get the
  same headers as any answer.
- On every answer:
  - `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy`, and no
    `Server`;
  - while `SEEBAND_SITE_URL` is empty, as on the prototype host, `X-Robots-Tag: noindex` on every
    file, whatever the site was built with.
  - No `Content-Security-Policy` or HSTS yet.

**Logs**

- They hold method, URI, status and duration. Caddy drops headers, cookies and addresses from every
  message, not only from its access log: the proxy's own message when a browser leaves a fit's
  stream carries the request too. The API logs no bodies. So the logs keep the overview's promise.
- Measurements only travel in bodies. The API takes no query parameters.
- Docker keeps 5 files of 10 MB per container.

**The API**

- **Runs as a user, not root.** The file system is read-only, with `/tmp` in memory for the fork
  server's socket.
- **Has no capabilities.** `no-new-privileges` is set.
- **tini is PID 1.** It reaps a fit's process if the fork server dies before it.
- **Memory and processes are capped** at `SEEBAND_MEM_LIMIT_API` (default 3 GB) and 256 PIDs, so a
  spike stops in the container rather than in the host's OOM killer.
- **Linear algebra uses one thread in each process.** `OMP_NUM_THREADS` and its kin are set to 1.
- **Trusts `X-Forwarded-For` only from Caddy's network** (`SEEBAND_API_TRUSTED_PROXIES`, IPv4 and
  IPv6). Each user therefore counts as their own client for the rate limits and the queue. The
  network has IPv6 so that an IPv6 visitor reaches Caddy with their own address. Without it, Docker
  would pass every IPv6 visitor in from the bridge's address, and they would all share one client.
- **Health check.** Docker checks `GET /api/ready`, which answers only once the calculation workers
  have started. Caddy starts after that.
- **Stopping.** On a stop, running requests get 5 s, then each fit's process ends with its request.

**Caddy** runs with only the capability to bind ports, on a read-only file system, with its
certificates and settings in volumes and at most 256 MB of memory.

**The process budget** is set by `SEEBAND_API_CALC_WORKERS` and `SEEBAND_API_FIT_MAX_RUNNING`. Their
defaults, 2 and 2, are meant for the planned 2 vCPUs. The independent review of 2026-11-11 found
that they oversubscribe such a machine under mixed load, so measure them on the machine itself
(I3, #55) before changing them. Size the memory limit there too.

## Operations

- **Update or roll back:** `SEEBAND_TAG=<tag> docker compose -f deploy/compose.yaml up -d`.
- **A change of the `Caddyfile` recreates the `web` container,** as Caddy's admin endpoint is off.
  That ends the open fit streams, and with them their fits, so do it when nobody is fitting.
- **Nothing restarts an API that turns unhealthy.** `restart` only covers an exit, and
  `depends_on` only the first start. Watch `docker inspect -f '{{.State.Health.Status}}'` (I4).
  Readiness covers the calculation workers, not the fits' processes.
- **Firewall:** open TCP 80 and 443, and UDP 443 for HTTP/3. Docker's published ports bypass `ufw`,
  so the provider's firewall decides what is reachable.
- **Subnets:** `172.30.0.0/24` and `fd5e:eba0:d000::/64` must not overlap a network of the host.

## Checked

- **CI.** The `Containers` job builds both images and starts the stack. Through Caddy it then checks:
  - the site and the redirect to `/guide/`;
  - the app, with `noindex`, and `noindex` on the site while it has no public address;
  - the 404 page with its headers;
  - readiness, the commit in `/api/health`, and a calculation.

  It also checks that:
  - both containers run on read-only file systems without capabilities, the API as a user with
    tini;
  - Caddy's logs hold no addresses or headers.

- **Locally, without Docker.** The `Caddyfile` ran with Caddy 2.10.2 in front of the API and
  production builds of the site and the app. Every route and header above answered as described,
  also for a missing page and the API down. A DPB S + ρ + R_H fit streamed its iterations through
  Caddy, and Stop ended it together with its process. Caddy's message about the closed stream held
  no address or header.
- **Not yet, on the target machine (I3):**
  - the review's mixed load, with its p50/p95/p99, memory and orphan processes;
  - that IPv4 and IPv6 visitors count as separate clients, by `curl -4` and `curl -6` from two
    hosts. Until that passes, publish no AAAA record.
