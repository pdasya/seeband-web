"""The application factory."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from seeband_api.band_diagram import router as band_diagram_router
from seeband_api.calc import router as calc_router
from seeband_api.calc_pool import CalcPool
from seeband_api.demo import router as demo_router
from seeband_api.dpb_migration import router as migration_router
from seeband_api.errors import add_error_handlers
from seeband_api.fit import router as fit_router
from seeband_api.fit_runner import FitRunner
from seeband_api.guess import router as guess_router
from seeband_api.health import router as health_router
from seeband_api.models import router as models_router
from seeband_api.parse import router as parse_router
from seeband_api.processes import start_fork_server
from seeband_api.request_limits import RateLimiter, RequestLimitsMiddleware
from seeband_api.request_logging import RequestLoggingMiddleware, configure_logging
from seeband_api.settings import Settings
from seeband_api.version import API_VERSION

OPENAPI_PATH = "/api/openapi.json"
DOCS_PATH = "/api/docs"


def _operation_id(route: APIRoute) -> str:
    """Names operations after their function, which keeps generated client types readable."""
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.json_body_bytes < settings.json_body_bytes_needed:
            # Only settings, no request: a fit within `max_points` could get a 413 under them.
            logging.getLogger("seeband_api").warning(
                "json_body_limit_below_max_points",
                extra={
                    "fields": {
                        "max_json_body_bytes": settings.json_body_bytes,
                        "needed_bytes": settings.json_body_bytes_needed,
                    }
                },
            )
        # Before the pool, whose workers fork from it too. Its imports took about 0.3 s on a Mac.
        await asyncio.to_thread(start_fork_server)
        app.state.calc_pool = CalcPool(
            settings.calc_workers,
            settings.calc_timeout_s,
            max_waiting=settings.calc_max_waiting,
            max_per_client=settings.calc_max_per_client,
            wait_timeout_s=settings.calc_wait_timeout_s,
            max_running_per_client=settings.calc_max_running_per_client,
        )
        app.state.calc_pool.warm_up()
        app.state.fit_runner = FitRunner(
            settings.fit_max_running,
            settings.fit_max_waiting,
            settings.fit_timeout_s,
            settings.fit_max_per_client,
        )
        yield
        app.state.fit_runner.close()
        app.state.calc_pool.close()

    app = FastAPI(
        title="SeeBand API",
        lifespan=lifespan,
        version=API_VERSION,
        openapi_url=OPENAPI_PATH,
        docs_url=DOCS_PATH,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        generate_unique_id_function=_operation_id,
    )
    app.state.settings = settings
    add_error_handlers(app)
    per_minute = {
        "/api/calc": settings.calc_per_minute,
        "/api/band-diagram": settings.band_diagram_per_minute,
        "/api/dpb/migrate": settings.calc_per_minute,
        "/api/parse": settings.parse_per_minute,
        "/api/guess": settings.guess_per_minute,
        "/api/fit": settings.fit_per_minute,
    }
    app.add_middleware(
        RequestLimitsMiddleware,
        limiter=RateLimiter(per_minute),
        max_body_bytes=settings.max_body_bytes,
        max_body_bytes_by_path=dict.fromkeys(
            ("/api/calc", "/api/fit", "/api/guess", "/api/band-diagram", "/api/dpb/migrate"),
            settings.json_body_bytes,
        ),
        body_timeout_s=settings.body_timeout_s,
        body_idle_timeout_s=settings.body_idle_timeout_s,
        max_concurrent_requests=settings.max_concurrent_requests,
        # The routes whose jobs share the calculation pool.
        per_client_paths=frozenset({"/api/calc", "/api/parse", "/api/guess"}),
        max_per_client=settings.calc_max_per_client,
    )
    # Added last, so that it runs first and logs the requests that the limits refuse.
    app.add_middleware(
        RequestLoggingMiddleware,
        unparameterised_paths=frozenset({OPENAPI_PATH, DOCS_PATH, *per_minute}),
    )
    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(migration_router)
    app.include_router(calc_router)
    app.include_router(band_diagram_router)
    app.include_router(parse_router)
    app.include_router(guess_router)
    app.include_router(fit_router)
    app.include_router(demo_router)
    return app
