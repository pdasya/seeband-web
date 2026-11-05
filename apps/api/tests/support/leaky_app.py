"""An app whose routes handle data badly on purpose, for testing what reaches the logs."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from seeband_api.main import create_app as create_real_app


class Measurements(BaseModel):
    note: str
    seebeck_v_per_k: list[float]


def create_app() -> FastAPI:
    app = create_real_app()
    router = APIRouter(prefix="/api/test")

    @router.post("/echo/{item_id}")
    async def echo(item_id: str, query: str, body: Measurements) -> dict[str, str]:
        return {"item_id": item_id, "query": query, "note": body.note}

    @router.post("/crash")
    async def crash(body: Measurements) -> None:
        raise RuntimeError(f"cannot fit {body.note}")

    @router.post("/crash-while-streaming")
    async def crash_while_streaming(body: Measurements) -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"first chunk"
            raise RuntimeError(f"cannot fit {body.note}")

        return StreamingResponse(chunks())

    app.include_router(router)
    return app
