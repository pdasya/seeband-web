# syntax=docker/dockerfile:1
# Caddy with the public site and the app, built here, in front of the API.
# Build from the repository root: docker build -f deploy/web.Dockerfile .

# Base images are pinned by digest; Dependabot proposes updates (.github/dependabot.yml).
# The site and the app are the same files on every architecture, so they are built once, natively.
FROM --platform=$BUILDPLATFORM node:24-bookworm-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54 AS build
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

FROM caddy:2.11.9-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/site/dist /srv/site
COPY --from=build /src/apps/web/dist /srv/app
