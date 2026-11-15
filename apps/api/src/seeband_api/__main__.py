"""Runs the API server: `python -m seeband_api`."""

import os

import uvicorn

from seeband_api.settings import Settings

# Each worker process runs one job at a time, so numpy's linear algebra takes one thread there.
# Otherwise each worker starts a thread for every core, and the processes fight over them. Set
# before anything loads numpy, and inherited by the worker processes.
_ONE_THREAD = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)

GRACEFUL_SHUTDOWN_S = 5


def main() -> None:
    for name in _ONE_THREAD:
        os.environ.setdefault(name, "1")
    settings = Settings()
    uvicorn.run(
        "seeband_api.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        access_log=False,
        forwarded_allow_ips=settings.trusted_proxies,
        # A stop otherwise waits for every running and queued fit, up to minutes. After this long,
        # requests are cancelled, and each fit's process ends with its request.
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_S,
        # Uvicorn logs the path and query of WebSocket requests. The API has none.
        ws="none",
        # A backstop past the app's own `max_concurrent_requests`, whose 503 is JSON and spares
        # health.
        limit_concurrency=settings.limit_concurrency,
    )


if __name__ == "__main__":
    main()
