# syntax=docker/dockerfile:1
# The API: FastAPI over seeband_core, installed from uv.lock, run as a non-root user.
# Build from the repository root: docker build -f deploy/api.Dockerfile .

FROM python:3.13-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
# Bytecode is compiled now, as the running container's file system is read-only.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
COPY packages/seeband_core packages/seeband_core
# Exactly the locked versions, as Stop depends on uvicorn's; no development tools.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package seeband-api

FROM python:3.13-slim-bookworm
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin seeband
COPY --from=build /opt/venv /opt/venv
# The commit names the build in /api/health and in every export.
ARG SEEBAND_COMMIT=
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SEEBAND_COMMIT=$SEEBAND_COMMIT \
    SEEBAND_API_HOST=0.0.0.0 \
    SEEBAND_API_PORT=8000 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1
USER seeband
EXPOSE 8000
# Ready, not only alive: the calculation workers have started.
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=2)"]
CMD ["python", "-m", "seeband_api"]
