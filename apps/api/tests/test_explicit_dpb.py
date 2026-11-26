"""Public contract for density-parametrized DPB and conversion of historical points."""

from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient
from running_server import read_events
from seeband_api.main import create_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_public_explicit_registry_and_fit(client):
    url = "/api/models?parameterization=explicit_density_v1"
    response = client.get(url)
    legacy = client.get("/api/models")
    assert legacy.headers["etag"] != response.headers["etag"]
    dpb = next(d for d in response.json()["models"] if d["id"] == "dpb")
    assert not dpb["has_initial_guess"]
    mode = next(m for m in dpb["fit_modes"] if m["id"] == "dpb_s")
    assert {p["name"] for p in mode["parameters"]} == {"m1", "mass_ratio", "band_offset_k"}
    body = dict(
        model="dpb",
        fit_mode="dpb_s",
        parameterization="explicit_density_v1",
        band_configuration="cb_cb",
        net_electron_density_per_m3=2e25,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
    )
    p = dict(m1=1.2, mass_ratio=1.7, band_offset_k=140)
    grid = dict(min_temperature_k=180, max_temperature_k=510)
    curve_request = body | grid | dict(parameters=p, points=4)
    curve = client.post("/api/calc", json=curve_request)
    assert curve.status_code == 200, curve.text
    measured = curve.json()
    assert max(measured["curves"]["seebeck_v_per_k"]) < 0
    data = {
        "seebeck": dict(
            temperature_k=measured["temperature_k"], values=measured["curves"]["seebeck_v_per_k"]
        )
    }
    rmse = client.post("/api/calc", json=curve_request | dict(measurements=data))
    assert rmse.status_code == 200, rmse.text
    assert rmse.json()["rmse"]["seebeck"]["value"] == pytest.approx(0)
    fit = (
        body | grid | dict(start=p | {"band_offset_k": 145}, measurements=data, held=["mass_ratio"])
    )
    assert client.post("/api/fit", json=fit).status_code == 422
    result = client.post(
        "/api/fit", json=fit | {"bounds": {"band_offset_k": {"lower": 100, "upper": 200}}}
    )
    assert result.status_code == 200, result.text
    event = list(read_events(iter(result.text.splitlines())))[-1]
    assert event["type"] == "done"
    assert event["result"]["status"] == "converged"
    assert event["result"]["parameters"]["band_offset_k"] == pytest.approx(140, rel=1e-5)
    for change in (
        {"band_configuration": "vb_vb"},
        {"net_electron_density_per_m3": 0},
        {"model": "spb"},
        {"parameterization": "legacy_fermi"},
        {"parameters": p | {"fermi_energy": 0}},
    ):
        assert client.post("/api/calc", json=curve_request | change).status_code == 422
    assert (
        client.post(
            "/api/guess", json=body | dict(temperature_k=[300], seebeck_v_per_k=[1e-4])
        ).status_code
        == 422
    )


def test_migrated_point_and_intrinsic_diagram(client):
    request = dict(
        parameters={"m_eff": 1.8, "band_gap": 600, "fermi_energy": 200},
        m1=1.2,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
    )
    conversion = client.post("/api/dpb/migrate", json=request)
    assert conversion.status_code == 200, conversion.text
    point = conversion.json()
    assert point["net_electron_density_per_m3"] == 0
    assert point["band_configuration"] == "vb_cb"
    body = point | dict(model="dpb", fit_mode="dpb_s", band_1_degeneracy=2, band_2_degeneracy=3)
    diagram = client.post("/api/band-diagram", json=body)
    assert diagram.status_code == 200, diagram.text
    content = diagram.json()
    assert len(content["wavevector_nm_inv"]) == len(content["curves"]["band_1_energy_k"])
    assert set(content["curves"]["fermi_energy_lower_k"]) == {0}
    assert set(content["curves"]["fermi_energy_upper_k"]) == {600}
    np.testing.assert_allclose(max(content["curves"]["band_1_energy_k"]), 0, atol=1e-12)
    assert (
        client.post(
            "/api/dpb/migrate", json=request | {"parameters": request["parameters"] | {"m_eff": 0}}
        ).status_code
        == 422
    )


def test_fermi_energy_is_fitted_and_density_follows_the_trial(client):
    response = client.get("/api/models?parameterization=explicit_fermi_v1")
    assert response.status_code == 200, response.text
    dpb = next(m for m in response.json()["models"] if m["id"] == "dpb")
    for mode in dpb["fit_modes"]:
        energy = next(p for p in mode["parameters"] if p["name"] == "fermi_energy")
        assert energy["role"] == "fitted"

    body = dict(
        model="dpb",
        fit_mode="dpb_s",
        scattering="acPh",
        parameterization="explicit_fermi_v1",
        band_configuration="cb_cb",
        band_1_degeneracy=2,
        band_2_degeneracy=3,
    )
    p = dict(m1=1.2, mass_ratio=1.7, band_offset_k=140, fermi_energy=85)
    grid = dict(min_temperature_k=180, max_temperature_k=510)
    request = body | grid | dict(parameters=p, points=5)
    calculated = client.post("/api/calc", json=request)
    assert calculated.status_code == 200, calculated.text
    observed = calculated.json()
    data = {
        "seebeck": dict(
            temperature_k=observed["temperature_k"], values=observed["curves"]["seebeck_v_per_k"]
        )
    }
    result = client.post(
        "/api/fit",
        json=body
        | grid
        | dict(
            start=p | {"fermi_energy": 95},
            measurements=data,
            held=["mass_ratio", "band_offset_k"],
            bounds={"fermi_energy": {"lower": 50, "upper": 120}},
        ),
    )
    assert result.status_code == 200, result.text
    fit = list(read_events(iter(result.text.splitlines())))[-1]
    assert fit["type"] == "done", fit
    assert fit["result"]["status"] == "converged"
    assert fit["result"]["parameters"]["fermi_energy"] == pytest.approx(85, rel=1e-5)

    for change in [
        {"net_electron_density_per_m3": 1e24},
        {"carrier_type": "p"},
    ]:
        assert client.post("/api/calc", json=request | change).status_code == 422


@pytest.mark.parametrize(
    "configuration,carrier,ef",
    [
        ("vb_vb", "p", 1000),
        ("vb_vb", "p", 1100),
        ("cb_cb", "n", 0),
        ("cb_cb", "n", -100),
        ("vb_cb", "n", -100),
        ("vb_cb", "p", 1100),
    ],
)
def test_ef_diagram_draws_unoccupied_and_opposite_carrier_states(
    client, configuration, carrier, ef
):
    body = dict(
        model="dpb",
        fit_mode="dpb_s",
        parameterization="explicit_fermi_v1",
        band_configuration=configuration,
        carrier_type=carrier,
        band_1_degeneracy=1,
        band_2_degeneracy=1,
        parameters=dict(m1=1, mass_ratio=1, band_offset_k=1000, fermi_energy=ef),
    )
    response = client.post("/api/band-diagram", json=body)
    assert response.status_code == 200, response.text
    curves = response.json()["curves"]
    assert set(curves["fermi_energy_k"]) == {ef}
    assert curves["band_1_energy_k"][50] == 0
    assert curves["band_2_energy_k"][50] == 1000
    assert all(np.isfinite(values).all() for values in curves.values())


@pytest.mark.parametrize("path,field", [("/api/calc", "parameters"), ("/api/fit", "start")])
@pytest.mark.parametrize(
    "configuration,carrier,ef,code",
    [
        ("vb_vb", "p", 1000, "fermi_energy_unoccupied_bands"),
        ("vb_vb", "p", 1100, "fermi_energy_unoccupied_bands"),
        ("cb_cb", "n", 0, "fermi_energy_unoccupied_bands"),
        ("cb_cb", "n", -100, "fermi_energy_unoccupied_bands"),
        ("vb_cb", "n", -100, "fermi_energy_carrier_mismatch"),
        ("vb_cb", "p", 1100, "fermi_energy_carrier_mismatch"),
    ],
)
def test_transport_ef_domain_errors_are_actionable(
    client, path, field, configuration, carrier, ef, code
):
    body = dict(
        model="dpb",
        fit_mode="dpb_s",
        parameterization="explicit_fermi_v1",
        band_configuration=configuration,
        carrier_type=carrier,
        band_1_degeneracy=1,
        band_2_degeneracy=1,
        min_temperature_k=100,
        max_temperature_k=500,
        measurements={"seebeck": {"temperature_k": [100, 300, 500], "values": [0, 0, 0]}},
    )
    body[field] = dict(m1=1, mass_ratio=1, band_offset_k=1000, fermi_energy=ef)
    response = client.post(path, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["details"][0]["code"] == code


@pytest.mark.parametrize(
    "change",
    [
        {"carrier_type": "n"},
        {"net_electron_density_per_m3": 1e24},
        {"band_1_degeneracy": 0},
        {"band_2_degeneracy": 1.5},
        {"parameters": dict(m1=0, mass_ratio=1, band_offset_k=1000, fermi_energy=1100)},
        {"parameters": dict(m1=1, mass_ratio=-1, band_offset_k=1000, fermi_energy=1100)},
        {"parameters": dict(m1=1, mass_ratio=1, band_offset_k=1000)},
        {"parameters": dict(m1=1, mass_ratio=1, band_offset_k=1000, fermi_energy="NaN")},
    ],
)
def test_ef_diagram_keeps_structural_input_validation(client, change):
    body = dict(
        model="dpb",
        fit_mode="dpb_s",
        parameterization="explicit_fermi_v1",
        band_configuration="vb_vb",
        carrier_type="p",
        band_1_degeneracy=1,
        band_2_degeneracy=1,
        parameters=dict(m1=1, mass_ratio=1, band_offset_k=1000, fermi_energy=1100),
    )
    assert client.post("/api/band-diagram", json=body | change).status_code == 422


def test_manual_parameter_domain_response_and_invalid_inputs(client):
    url = "/api/dpb/parameter-domain"
    query = dict(
        name="fermi_energy",
        band_configuration="vb_vb",
        carrier_type="p",
        fermi_energy=0,
        band_offset_k=400,
        mass_ratio=2,
        band_1_degeneracy=1,
        band_2_degeneracy=8,
    )

    def domain(**changes):
        response = client.get(url, params=query | changes)
        assert response.status_code == 200, response.text
        return response.json()

    assert domain() == dict(lower=None, upper=400, inclusive=False, empty=False)
    assert domain(band_configuration="cb_cb", carrier_type="n", band_offset_k=-400) == dict(
        lower=-400, upper=None, inclusive=False, empty=False
    )
    assert domain(band_configuration="vb_cb", band_offset_k=-180) == dict(
        lower=None, upper=-160, inclusive=True, empty=False
    )
    assert domain(name="mass_ratio", band_configuration="vb_cb", band_offset_k=-180)["empty"]
    assert domain(name="mass_ratio") == dict(lower=None, upper=None, inclusive=True, empty=False)
    for changes in (dict(mass_ratio=0), dict(band_1_degeneracy="inf"), dict(fermi_energy="nan")):
        assert client.get(url, params=query | changes).status_code == 422


@pytest.mark.parametrize("single_valley_mass,reference_count", [(0.5, 1), (2, 8)])
def test_migrated_hall_curves_follow_confirmed_mass_convention(
    client, single_valley_mass, reference_count
):
    # At equal valley counts the pre-#252 convention used their ratio alone, as for (1, 1).
    # A saved all-valley mass of 2 at N=8 therefore maps to 0.5; a single-valley 2 stays 2.
    shape = dict(m_eff=2, band_gap=600, fermi_energy=-200, m1=2, A=100000, B=0.7, F=100000, G=0.7)
    counts = dict(band_1_degeneracy=8, band_2_degeneracy=8)
    point = client.post(
        "/api/dpb/migrate", json=dict(parameters=shape, m1=single_valley_mass, **counts)
    )
    assert point.status_code == 200, point.text
    grid = dict(
        model="dpb",
        fit_mode="dpb_s_rho_rh",
        scattering="acPh",
        min_temperature_k=100,
        max_temperature_k=500,
        points=3,
    )
    historic = client.post(
        "/api/calc",
        json=grid
        | dict(
            parameters=shape, band_1_degeneracy=reference_count, band_2_degeneracy=reference_count
        ),
    )
    migrated = client.post("/api/calc", json=grid | point.json() | counts)
    assert historic.status_code == 200, historic.text
    assert migrated.status_code == 200, migrated.text
    for curve in ("seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c"):
        np.testing.assert_allclose(
            migrated.json()["curves"][curve], historic.json()["curves"][curve], rtol=1e-6, atol=0
        )
