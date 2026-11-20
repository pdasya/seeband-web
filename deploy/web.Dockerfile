# syntax=docker/dockerfile:1
# Caddy with the public site and the app, built here, in front of the API.
# Build from the repository root: docker build -f deploy/web.Dockerfile .

# Base images are pinned by digest; Dependabot proposes updates (.github/dependabot.yml).
FROM node:26-bookworm-slim@sha256:5df79989ed685e09f0a98019db4cebfb22fb9df1a53c0161664a011f7ff6b0f1 AS build
RUN corepack enable
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
# The public address, for canonical links and the sitemap. Empty, the site keeps every page out
# of search engines, as the prototype host must (S6).
ARG SEEBAND_SITE_URL=
# The commit the app names in its exports.
ARG SEEBAND_COMMIT=
RUN SEEBAND_SITE_URL="$SEEBAND_SITE_URL" SEEBAND_COMMIT="$SEEBAND_COMMIT" \
    pnpm --filter ./apps/web run build \
 && SEEBAND_SITE_URL="$SEEBAND_SITE_URL" pnpm --filter @seeband/site run build

FROM caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/site/dist /srv/site
COPY --from=build /src/apps/web/dist /srv/app
