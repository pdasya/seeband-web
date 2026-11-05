import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.main import create_app
from seeband_api.settings import Settings
from seeband_api.version import API_VERSION


class Body(BaseModel):
    seebeck_v_per_k: list[float]


def _app_with_test_routes() -> FastAPI:
    app = create_app()
    router = APIRouter(prefix="/api/test")

    @router.post("/validated")
    async def validated(body: Body) -> int:
        return len(body.seebeck_v_per_k)

    @router.get("/api-error")
    async def api_error() -> None:
        raise ApiError(
            409,
            "bad_state",
            "State is bad",
            details=[ErrorDetail(location=["body", 1], code="bad_item", message="Item is bad")],
        )

    @router.get("/crash")
    async def crash() -> None:
        raise RuntimeError("private text")

    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app_with_test_routes())


def test_health_returns_status_and_version(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": API_VERSION}


def test_unknown_path_uses_the_error_format(client: TestClient) -> None:
    response = client.get("/api/nothing-here")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found", "details": None}


def test_wrong_method_uses_the_error_format_and_keeps_allow(client: TestClient) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert response.headers["allow"] == "GET"


def test_validation_error_names_the_problem(client: TestClient) -> None:
    response = client.post("/api/test/validated", json={"seebeck_v_per_k": [1.0, "bad"]})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Invalid request"
    assert len(body["details"]) == 1
    assert body["details"][0]["location"] == ["body", "seebeck_v_per_k", 1]
    assert body["details"][0]["code"] == "float_parsing"
    assert set(body["details"][0]) == {"location", "code", "message"}


def test_validation_error_does_not_return_submitted_values(client: TestClient) -> None:
    # A string in place of a list ends in an error that Pydantic reports with the input.
    response = client.post("/api/test/validated", json={"seebeck_v_per_k": "PRIVATE-VALUE"})

    assert response.status_code == 422
    assert "PRIVATE-VALUE" not in response.text


@pytest.mark.parametrize(
    "content",
    [b"{not json PRIVATE-VALUE", b'{"seebeck_v_per_k": [1.0, NaN, "PRIVATE-VALUE"]}'],
)
def test_malformed_body_uses_the_error_format(client: TestClient, content: bytes) -> None:
    response = client.post(
        "/api/test/validated", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "PRIVATE-VALUE" not in response.text


def test_api_error_uses_the_error_format(client: TestClient) -> None:
    response = client.get("/api/test/api-error")

    assert response.status_code == 409
    assert response.json() == {
        "code": "bad_state",
        "message": "State is bad",
        "details": [{"location": ["body", 1], "code": "bad_item", "message": "Item is bad"}],
    }


def test_unhandled_exception_uses_the_error_format_without_its_message(
    client: TestClient,
) -> None:
    # TestClient raises any exception that leaves the app, so this also shows that none does.
    response = client.get("/api/test/crash")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
    }


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEEBAND_API_PORT", "9123")
    monkeypatch.setenv("SEEBAND_API_LOG_LEVEL", "WARNING")

    settings = Settings()

    assert settings.port == 9123
    assert settings.log_level == "WARNING"


def test_invalid_log_level_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEEBAND_API_LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings()
