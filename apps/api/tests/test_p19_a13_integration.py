"""Both fit algorithms retain A13 request guards before a task can be admitted."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from running_server import read_events
from seeband_api.errors import MAX_ERROR_DETAILS
from seeband_api.main import create_app
from seeband_api.request_checks import MAX_PARAMETERS
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest

ALGORITHMS = (None, "verified-sequential-v2", "legacy-sequential-v1")


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def body(algorithm: str | None) -> dict[str, Any]:
    parameters = {"band_mass": 1.0, "fermi_energy": 300.0}
    curve = registry.get("spb").calculate(CurveRequest("spb_s", parameters, 100.0, 400.0, 3))
    request: dict[str, Any] = {
        "model": "spb",
        "fit_mode": "spb_s",
        "start": parameters,
        "min_temperature_k": 100.0,
        "max_temperature_k": 400.0,
        "measurements": {
            "seebeck": {
                "temperature_k": curve.temperature_k.tolist(),
                "values": curve.curves["seebeck_v_per_k"].tolist(),
            }
        },
    }
    if algorithm is not None:
        request["algorithm"] = algorithm
    return request


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_valid_fit_keeps_selected_method_and_diagnostics(
    client: TestClient, algorithm: str | None
) -> None:
    response = client.post("/api/fit", json=body(algorithm))

    assert response.status_code == 200
    last = list(read_events(iter(response.text.splitlines())))[-1]
    assert last["type"] == "done"
    result = last["result"]
    selected = algorithm or "verified-sequential-v2"
    assert result["algorithm"] == selected
    assert result["status"] == "converged"
    if selected == "verified-sequential-v2":
        assert result["diagnostics"]["stage_consistent"] is True
        assert result["diagnostics"]["uncertainty"] == "not_assessed"
    else:
        assert "diagnostics" not in result


@pytest.fixture
def no_admission(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("An invalid request reached the fit queue")

    monkeypatch.setattr(client.app.state.fit_runner, "submit", forbidden)


@pytest.mark.usefixtures("no_admission")
@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("field", ("start", "bounds", "measurements"))
def test_oversized_mapping_is_rejected_before_items_and_admission(
    client: TestClient, algorithm: str | None, field: str
) -> None:
    request = body(algorithm)
    count = 4 if field == "measurements" else MAX_PARAMETERS + 1
    request[field] = {f"invalid_{i}": "not a number or measurement" for i in range(count)}

    response = client.post("/api/fit", json=request)

    assert response.status_code == 422
    assert [(d["location"], d["code"]) for d in response.json()["details"]] == [
        (["body", field], "too_long")
    ]


@pytest.mark.usefixtures("no_admission")
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_routed_errors_remain_capped_for_each_method(
    client: TestClient, algorithm: str | None
) -> None:
    request = body(algorithm)
    request["start"] = {f"unknown_{i}": 1.0 for i in range(MAX_PARAMETERS)}

    response = client.post("/api/fit", json=request)

    assert response.status_code == 422
    assert len(response.json()["details"]) == MAX_ERROR_DETAILS
    assert response.json()["details_omitted"] > 0
