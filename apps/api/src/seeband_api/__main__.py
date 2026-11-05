"""Runs the API server: `python -m seeband_api`."""

import uvicorn

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
        # A stop otherwise waits for every running and queued fit, up to minutes. After this long,
        # requests are cancelled, and each fit's process ends with its request.
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_S,
        # Uvicorn logs the path and query of WebSocket requests. The API has none.
        ws="none",
    )


if __name__ == "__main__":
    main()
