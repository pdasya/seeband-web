from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from running_server import read_events
from seeband_api.main import create_app
from seeband_api.parse import ParseResponse
from seeband_core.demo_dataset import demo_table_text, load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest
from seeband_core.model_scales import default_start

DATASET = load_demo_dataset()


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def demo(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/demo")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_it_has_the_shape_and_values_of_a_parsed_file(
    client: TestClient, demo: dict[str, Any]
) -> None:
    parsed = client.post("/api/parse", json={"text": demo_table_text(DATASET)})

    assert parsed.status_code == 200
    assert parsed.json() == {name: demo[name] for name in parsed.json()}
    assert set(ParseResponse.model_fields) - set(demo) == set()


def test_it_is_labelled_synthetic(demo: dict[str, Any]) -> None:
    assert demo["synthetic"] is True
    assert demo["message_key"] == "demo_dataset.synthetic"
    assert demo["known_issues"] == ["dpb_hall_prefactor"]


def test_it_says_what_generated_it(demo: dict[str, Any]) -> None:
    assert (demo["model"], demo["fit_mode"], demo["scattering"]) == ("dpb", "dpb_s_rho_rh", "acPh")
    assert demo["true_parameters"] == DATASET.true_parameters
    assert demo["noise"] == DATASET.noise


def test_it_holds_the_stored_data_exactly(demo: dict[str, Any]) -> None:
    assert demo["errors"] == []
    assert demo["warnings"] == []
    assert demo["row_count"] == 31
    assert set(demo["measurements"]) == set(DATASET.measurements)
    for quantity, measurement in DATASET.measurements.items():
        sent = demo["measurements"][quantity]
        assert np.array_equal(sent["temperature_k"], measurement.temperature_k)
        assert np.array_equal(sent["values"], measurement.values)


def test_a_client_can_fit_it_as_it_stands(client: TestClient, demo: dict[str, Any]) -> None:
    """What the response names and holds is enough for a fit, which equals the core's."""
    mode = registry.get(demo["model"]).describe().fit_mode(demo["fit_mode"])
    start = default_start(mode)
    expected = registry.get(demo["model"]).fit(
        FitRequest(mode.id, DATASET.measurements, start, scattering=demo["scattering"])
    )
    temperature_k = demo["measurements"]["seebeck"]["temperature_k"]

    response = client.post(
        "/api/fit",
        json={
            "model": demo["model"],
            "fit_mode": demo["fit_mode"],
            "scattering": demo["scattering"],
            "start": start,
            "min_temperature_k": min(temperature_k),
            "max_temperature_k": max(temperature_k),
            "measurements": {
                quantity: {
                    "temperature_k": measurement["temperature_k"],
                    "values": measurement["values"],
                }
                for quantity, measurement in demo["measurements"].items()
            },
        },
    )

    last = list(read_events(iter(response.text.splitlines())))[-1]
    assert last["type"] == "done"
    assert last["result"]["status"] == "converged"
    assert last["result"]["parameters"] == expected.parameters


def test_true_parameters_over_the_described_defaults_give_a_curve_near_the_data(
    client: TestClient, demo: dict[str, Any]
) -> None:
    """As the README says, and through what a client has: the two responses of the API."""
    models = client.get("/api/models").json()["models"]
    model = next(item for item in models if item["id"] == demo["model"])
    mode = next(item for item in model["fit_modes"] if item["id"] == demo["fit_mode"])
    defaults = {spec["name"]: spec["core_range"]["default"] for spec in mode["parameters"]}
    temperature_k = demo["measurements"]["seebeck"]["temperature_k"]
    body = {
        "model": demo["model"],
        "fit_mode": demo["fit_mode"],
        "scattering": demo["scattering"],
        "min_temperature_k": min(temperature_k),
        "max_temperature_k": max(temperature_k),
        "measurements": {
            quantity: {key: item[key] for key in ("temperature_k", "values")}
            for quantity, item in demo["measurements"].items()
        },
    }

    alone = client.post("/api/calc", json=body | {"parameters": demo["true_parameters"]})
    merged = client.post(
        "/api/calc", json=body | {"parameters": defaults | demo["true_parameters"]}
    )

    assert alone.status_code == 422
    assert merged.status_code == 200
    rmse = merged.json()["rmse"]["seebeck"]
    # The data's noise on S is 1 µV/K.
    assert rmse["unit"] == "uV/K"
    assert rmse["value"] < 2.0


def test_its_example_in_the_contract_is_the_real_response(demo: dict[str, Any]) -> None:
    contract = create_app().openapi()
    media = contract["paths"]["/api/demo"]["get"]["responses"]["200"]["content"]["application/json"]

    assert media["examples"]["demo"]["value"] == demo
