"""`POST /api/band-diagram`, against the desktop's own calls."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_core.model_catalog import registry
from seeband_core.model_scales import default_start


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _mode(model: str, fit_mode: str) -> Any:
    return registry.get(model).describe().fit_mode(fit_mode)


def _body(model: str, fit_mode: str, **parameters: float) -> dict[str, Any]:
    return {
        "model": model,
        "fit_mode": fit_mode,
        "parameters": {**default_start(_mode(model, fit_mode)), **parameters},
    }


def test_spb_has_its_band_and_the_fermi_energy(client: TestClient) -> None:
    response = client.post(
        "/api/band-diagram", json=_body("spb", "spb_s", band_mass=1.01, fermi_energy=100.0)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["wavevector"]) == 100
    assert body["wavevector"][0] == -40.0
    assert body["wavevector"][-1] == 40.0
    assert list(body["curves"]) == ["band_1_energy_k", "fermi_energy_k"]
    assert body["known_issues"] == ["band_diagram_formula"]
    assert body["curves"]["fermi_energy_k"][50] == pytest.approx(100.0, abs=1e-3)


def test_dpb_has_both_bands_and_the_fermi_energy(client: TestClient) -> None:
    response = client.post(
        "/api/band-diagram",
        json=_body("dpb", "dpb_s_rho", m_eff=1.25, band_gap=500.0, fermi_energy=-50.0),
    )

    assert response.status_code == 200
    curves = response.json()["curves"]
    assert list(curves) == ["band_1_energy_k", "band_2_energy_k", "fermi_energy_k"]
    # Band 2 opens up from E_g and band 1 down from 0, as the masses have those signs.
    assert min(curves["band_2_energy_k"]) > 500.0
    assert max(curves["band_1_energy_k"]) < 0.0


def test_the_ratio_of_degeneracies_sets_the_mass_of_band_2(client: TestClient) -> None:
    body = _body("dpb", "dpb_s", m_eff=1.0, band_gap=0.0)
    one = client.post("/api/band-diagram", json=body).json()["curves"]["band_2_energy_k"]
    body |= {"band_1_degeneracy": 1.0, "band_2_degeneracy": 2.0}
    two = client.post("/api/band-diagram", json=body).json()["curves"]["band_2_energy_k"]

    assert two[0] == pytest.approx(one[0] / 2)


def test_a_mass_of_0_gives_null_and_leaves_the_rest(client: TestClient) -> None:
    response = client.post("/api/band-diagram", json=_body("dpb", "dpb_s", m_eff=0.0))

    assert response.status_code == 200
    curves = response.json()["curves"]
    assert set(curves["band_2_energy_k"]) == {None}
    assert None not in curves["band_1_energy_k"]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"model": "nope"}, "unknown_model"),
        ({"fit_mode": "nope"}, "unknown_fit_mode"),
        ({"parameters": {}}, "missing_parameter"),
    ],
)
def test_what_is_wrong_is_named(client: TestClient, change: dict[str, Any], code: str) -> None:
    response = client.post("/api/band-diagram", json=_body("dpb", "dpb_s") | change)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_band_diagram"
    assert code in {detail["code"] for detail in body["details"]}


@pytest.mark.parametrize(("band_1", "band_2"), [(1e-308, 1e308), (1e308, 1e-308)])
def test_a_ratio_of_degeneracies_past_a_float_is_refused(
    client: TestClient, band_1: float, band_2: float
) -> None:
    body = _body("dpb", "dpb_s") | {"band_1_degeneracy": band_1, "band_2_degeneracy": band_2}

    response = client.post("/api/band-diagram", json=body)

    assert response.status_code == 422
    assert [detail["code"] for detail in response.json()["details"]] == [
        "degeneracy_ratio_out_of_range"
    ]


def test_a_mode_with_no_degeneracy_refuses_one(client: TestClient) -> None:
    body = _body("spb", "spb_s") | {"band_2_degeneracy": 2.0}

    assert client.post("/api/band-diagram", json=body).status_code == 422


def test_a_disabled_mode_is_refused(client: TestClient) -> None:
    response = client.post("/api/band-diagram", json=_body("spb", "spb_s_rho_rh"))

    assert response.status_code == 409
