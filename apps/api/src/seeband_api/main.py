"""The application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from seeband_api.calc import router as calc_router
from seeband_api.calc_pool import CalcPool
from seeband_api.errors import add_error_handlers
from seeband_api.health import router as health_router
from seeband_api.models import router as models_router
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
        app.state.calc_pool = CalcPool(settings.calc_workers, settings.calc_timeout_s)
        app.state.calc_pool.warm_up()
        yield
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
    add_error_handlers(app)
    app.add_middleware(
        RequestLoggingMiddleware,
        unparameterised_paths=frozenset({OPENAPI_PATH, DOCS_PATH}),
    )
    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(calc_router)
    return app
