# syntax=docker/dockerfile:1
# Caddy with the public site and the app, built here, in front of the API.
# Build from the repository root: docker build -f deploy/web.Dockerfile .

FROM node:24-bookworm-slim AS build
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

FROM caddy:2.10.2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/site/dist /srv/site
COPY --from=build /src/apps/web/dist /srv/app
