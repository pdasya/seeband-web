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

## Deploying from GitHub

`.github/workflows/deploy.yml` builds both images of each merge to main, pushes them to GHCR as
`ghcr.io/pdasya/seeband-api` and `-web` with the tag `sha-<first 12 characters of the commit>`,
and deploys that tag over SSH. Each tag stays in the registry, so any earlier one can be deployed
again.

On the host, `deploy.sh`, which the job copies there with the new `compose.yaml` as
`compose.yaml.new`:

1. puts the new Compose file in place, keeping the running one as `.previous-compose.yaml`;
2. pulls the tag's images and starts them, waiting for the API's health check;
3. asks `<SEEBAND_PUBLIC_URL>/api/health` for up to a minute, through Caddy, until it answers with
   this tag's commit, so an old container still answering does not pass. The site's name resolves
   to the host itself for this check, so it does not depend on the host reaching its own public
   address;
4. records the tag in `.deployed-tag`, and the one before in `.previous-tag`, and removes the
   images of every other tag, so the disk does not fill up;
5. if 2 or 3 fails, starts the previous tag again with the previous Compose file, checks it the
   same way, and fails the job.

The job then checks the health URL once more from outside. The host logs in to GHCR only for the
pull, with the job's short-lived token, and logs out again; nothing long-lived is stored there.

**Roll back:** run the Deploy workflow by hand (Actions → Deploy → Run workflow) with the tag to
go back to, such as the one in `.previous-tag` on the host or any `sha-…` tag of the package. That
skips the build and deploys the tag with the same checks.

**Settings.** Secrets live only in the repository's `production` environment. Two variables are
repository variables instead, because GitHub decides whether a job runs, and builds the images,
before any environment applies:

| Where       | Kind   | Name                 | Holds                                                                 |
| ----------- | ------ | -------------------- | --------------------------------------------------------------------- |
| environment | secret | `DEPLOY_SSH_KEY`     | a private key used only for deploying, its public half on the host    |
| environment | secret | `DEPLOY_KNOWN_HOSTS` | the host's line from `ssh-keyscan`, so the job checks the host key    |
| environment | var    | `DEPLOY_USER`        | a user on the host in the `docker` group                              |
| environment | var    | `DEPLOY_PATH`        | the directory with the host's `.env`, such as `/opt/seeband`          |
| environment | var    | `SEEBAND_PUBLIC_URL` | the public address, such as `https://seeband.example`                 |
| repository  | var    | `DEPLOY_HOST`        | the host's name or address; until it is set, no deploy runs           |
| repository  | var    | `SEEBAND_SITE_URL`   | empty until the move to the final host (I6), so the site stays closed |

**Limit the environment to `main`** (Settings → Environments → production → Deployment branches).
The deploy key belongs to a member of the `docker` group, so it is root on the host. The workflow
deploys only from main as well, but only the environment rule keeps the key from a workflow
changed on another branch. Add required reviewers if a deploy should wait for approval. The host's own
settings, `SEEBAND_SITE_ADDRESS`, the ports and the API's limits, stay in its `.env`, which no
workflow touches. Until `DEPLOY_HOST` is set, as before the machine exists (I3), each merge builds
and pushes the images and skips the deploy.

## A temporary host: Oracle Cloud Always Free

Until the planned host exists, an Always Free machine of Oracle Cloud can run the same images, to
show results. Its free machines are Ampere, arm64, which is why the images are built for both
architectures. It holds no data either: measurements are only used for the calculation asked for.

1. **The machine** (Oracle Cloud console, one time; needs an Oracle account):
   - Compute → Instances → Create: image Ubuntu 24.04, shape `VM.Standard.A1.Flex` (Ampere),
     2 OCPUs and 12 GB, within the free allowance; a public IPv4 address; your own SSH key.
   - In the instance's subnet, Security List → Ingress Rules: TCP 80 and 443, and UDP 443,
     from `0.0.0.0/0`. SSH (TCP 22) is open already.
2. **A name.** Until a domain is chosen (F7), `<ip with dashes>.sslip.io` resolves to the machine,
   such as `203-0-113-7.sslip.io` for 203.0.113.7, and Caddy gets an HTTPS certificate for it.
3. **A deploy key**, on your computer: `ssh-keygen -t ed25519 -N '' -C seeband-deploy -f seeband-deploy`.
4. **The machine's setup**: copy `deploy/host-setup.sh` there and run
   `sudo bash host-setup.sh "$(cat seeband-deploy.pub)" 203-0-113-7.sslip.io`. It installs
   Docker, creates the user `deploy` with only that key, opens the ports in the machine's own
   firewall, and writes `/opt/seeband/.env`.
5. **GitHub**, environment `production`, limited to `main`: the secret `DEPLOY_SSH_KEY` is the
   contents of `seeband-deploy`; `DEPLOY_KNOWN_HOSTS` is the output of
   `ssh-keyscan -t ed25519 <ip>`; the vars are `DEPLOY_USER` = `deploy`,
   `DEPLOY_PATH` = `/opt/seeband` and `SEEBAND_PUBLIC_URL` = `https://203-0-113-7.sslip.io`. As a
   repository variable, `DEPLOY_HOST` = the IP; `SEEBAND_SITE_URL` stays unset, so the site stays
   out of search engines.
6. **Deploy**: the next merge to main deploys, or run the Deploy workflow by hand with a tag.

Moving to the planned host later means repeating 4 and 5 there and changing the vars.

## Operations

- **Update or roll back:** by the Deploy workflow, below. By hand on the host, in its deploy directory: `./deploy.sh "$(cat .previous-tag)" https://<domain>/api/health`.
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
- **The deploy script, in CI.** The `Containers` job deploys a `sha-` tag of the commit with
  `deploy.sh` and checks that images of other tags were removed. It then deploys a tag whose API
  reports another commit, and checks that the script went back to the first tag and that this
  rollback passed its own check. Last, it deploys that tag with a new Compose file under which the
  API cannot start, and checks that the rollback used the Compose file before it. Locally, with stand-ins for Docker and curl, it also kept a good tag,
  recorded the previous one, rolled back from a tag whose API reported another commit, and failed
  plainly when the rollback failed too.
- **Not yet:** the Deploy workflow itself, which needs the host and its settings (I3), and a first
  real deploy with a deliberately failing health check on it.
- **Not yet, on the target machine (I3):**
  - the review's mixed load, with its p50/p95/p99, memory and orphan processes;
  - that IPv4 and IPv6 visitors count as separate clients, by `curl -4` and `curl -6` from two
    hosts. Until that passes, publish no AAAA record.
