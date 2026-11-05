"""Runs the API server: `python -m seeband_api`."""

import uvicorn

from seeband_api.settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "seeband_api.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
