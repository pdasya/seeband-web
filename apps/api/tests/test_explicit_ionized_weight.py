"""Mechanism-specific explicit DPB weight metadata and backward compatible inputs."""

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_explicit_metadata_exposes_overrides_without_changing_legacy(client):
    for parameterization in ("explicit_density_v1", "explicit_fermi_v1"):
        response = client.get("/api/models", params={"parameterization": parameterization})
        assert response.status_code == 200
        dpb = next(m for m in response.json()["models"] if m["id"] == "dpb")
        for mode in dpb["fit_modes"]:
            weight = mode["parameter_overrides"]["ionized"][0]
            assert weight["name"] == "B"
            assert weight["core_range"]["default"] == 1
            if mode["id"] == "dpb_s":
                assert weight["role"] == "fixed"
                assert weight.get("fit_bounds") is None
            else:
                assert weight["role"] == "fitted" and weight["bounds_editable"]
                assert weight["fit_bounds"] == {"lower": 0, "upper": 10000}
    legacy = client.get("/api/models")
    assert legacy.headers["etag"] != response.headers["etag"]
    for model in legacy.json()["models"]:
        assert all(not mode.get("parameter_overrides") for mode in model["fit_modes"])


def test_explicit_s_ionized_accepts_optional_weight(client):
    parameters = dict(m1=1.2, mass_ratio=2, band_offset_k=140)
    request = dict(
        model="dpb",
        fit_mode="dpb_s",
        scattering="ionized",
        parameterization="explicit_density_v1",
        band_configuration="cb_cb",
        net_electron_density_per_m3=2e25,
        parameters=parameters,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        min_temperature_k=180,
        max_temperature_k=510,
        points=4,
    )
    old = client.post("/api/calc", json=request)
    one = client.post("/api/calc", json=request | {"parameters": parameters | {"B": 1}})
    four = client.post("/api/calc", json=request | {"parameters": parameters | {"B": 4}})
    assert old.status_code == one.status_code == four.status_code == 200, four.text
    assert old.json()["curves"] == one.json()["curves"]
    assert old.json()["curves"] != four.json()["curves"]
    invalid = client.post("/api/calc", json=request | {"parameters": parameters | {"B": -1}})
    assert invalid.status_code == 422
    diagram = client.post(
        "/api/band-diagram",
        json={
            key: value
            for key, value in request.items()
            if key
            in {
                "model",
                "fit_mode",
                "parameterization",
                "band_configuration",
                "net_electron_density_per_m3",
                "band_1_degeneracy",
                "band_2_degeneracy",
            }
        }
        | {"parameters": parameters | {"B": 4}},
    )
    assert diagram.status_code == 200, diagram.text


def test_s_only_weight_is_fixed_during_api_fit_and_omission_defaults_to_one(client):
    from running_server import read_events

    parameters = dict(m1=1.2, mass_ratio=2, band_offset_k=140)
    common = dict(
        model="dpb",
        fit_mode="dpb_s",
        scattering="ionized",
        parameterization="explicit_density_v1",
        band_configuration="cb_cb",
        net_electron_density_per_m3=2e25,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        min_temperature_k=180,
        max_temperature_k=510,
    )
    for weight in ({}, {"B": 4}):
        target = parameters | weight
        curve = client.post("/api/calc", json=common | dict(parameters=target, points=5)).json()
        request = common | dict(
            start=target | {"band_offset_k": 145},
            held=["mass_ratio"],
            measurements={
                "seebeck": dict(
                    temperature_k=curve["temperature_k"],
                    values=curve["curves"]["seebeck_v_per_k"],
                )
            },
            bounds={"band_offset_k": dict(lower=100, upper=200)},
        )
        response = client.post("/api/fit", json=request)
        assert response.status_code == 200, response.text
        result = list(read_events(iter(response.text.splitlines())))[-1]["result"]
        assert result["status"] == "converged", result
        assert result["parameters"]["B"] == weight.get("B", 1)
        assert result["parameter_status"]["B"] == "fixed"
        assert result["parameters"]["band_offset_k"] == pytest.approx(140, rel=1e-5)
        for change in (
            {"start": target | {"B": -1}},
            {"held": ["mass_ratio", "B"]},
            {"bounds": request["bounds"] | {"B": dict(lower=0, upper=10)}},
        ):
            assert client.post("/api/fit", json=request | change).status_code == 422
