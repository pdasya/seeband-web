"""Runs the API server: `python -m seeband_api`."""

import uvicorn

# First, as importing it keeps numpy's linear algebra to one thread, before anything loads numpy.
import seeband_api.processes  # noqa: F401
from seeband_api.settings import Settings

GRACEFUL_SHUTDOWN_S = 5


def main() -> None:
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
