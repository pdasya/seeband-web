"""Each cell of the curve availability matrix, through the API."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_core.model_catalog import registry
from seeband_core.model_interface import ALL_CURVE_KINDS, CurveRequest
from seeband_core.model_scales import default_start

BY_BAND_COLUMNS = {
    "seebeck_by_band": ["seebeck_band_1_v_per_k", "seebeck_band_2_v_per_k"],
    "electrical_conductivity_by_band": [
        "electrical_conductivity_band_1_s_per_m",
        "electrical_conductivity_band_2_s_per_m",
    ],
    "carrier_concentration_by_band": [
        "carrier_concentration_band_1_per_cm3",
        "carrier_concentration_band_2_per_cm3",
    ],
}
MU = {"chemical_potential": ["chemical_potential_k"]}
SIGMA = {"electrical_conductivity": ["electrical_conductivity_s_per_m"]}
KAPPA = {"thermal_conductivity": ["thermal_conductivity_w_per_m_k"]}
TOTAL_S = {"seebeck": ["seebeck_v_per_k"]}
S = ["seebeck_v_per_k"]
RHO = [*S, "resistivity_ohm_m"]
HALL = [*RHO, "hall_m3_per_c"]

# Written by hand from the desktop's AddGraphsWin* windows, in docs/curve-availability.md.
OFFERED: dict[str, dict[str, list[str]]] = {
    "spb_s": {"measured": S, **MU},
    "spb_s_rho": {"measured": RHO, **MU, **SIGMA, **KAPPA},
    "dpb_s": {
        "measured": S,
        "seebeck_by_band": BY_BAND_COLUMNS["seebeck_by_band"],
        **MU,
        "carrier_concentration_by_band": BY_BAND_COLUMNS["carrier_concentration_by_band"],
    },
    "dpb_s_rho": {"measured": RHO, **TOTAL_S, **BY_BAND_COLUMNS, **MU, **SIGMA, **KAPPA},
    "dpb_s_rho_rh": {"measured": HALL, **TOTAL_S, **BY_BAND_COLUMNS, **MU, **SIGMA, **KAPPA},
}
REFUSED: dict[str, dict[str, str]] = {
    "spb_s": {
        "seebeck": "same_as_measured",
        "seebeck_by_band": "single_band",
        "electrical_conductivity": "needs_resistivity",
        "electrical_conductivity_by_band": "single_band",
        "thermal_conductivity": "needs_resistivity",
        "carrier_concentration_by_band": "not_on_desktop",
    },
    "spb_s_rho": {
        "seebeck": "same_as_measured",
        "seebeck_by_band": "single_band",
        "electrical_conductivity_by_band": "single_band",
        "carrier_concentration_by_band": "not_on_desktop",
    },
    "dpb_s": {
        "seebeck": "same_as_measured",
        "electrical_conductivity": "needs_resistivity",
        "electrical_conductivity_by_band": "needs_resistivity",
        "thermal_conductivity": "needs_resistivity",
    },
    "dpb_s_rho": {},
    "dpb_s_rho_rh": {},
}
SCATTERING: dict[str, tuple[str | None, ...]] = {
    "spb_s": (None,),
    "spb_s_rho": ("acPh", "dis", "acPhDis"),
    "dpb_s": (None,),
    "dpb_s_rho": ("acPh", "dis", "acPhDis"),
    "dpb_s_rho_rh": ("acPh", "dis", "acPhDis"),
}

KANE_ONLY = (
    "lorenz_number",
    "reduced_fermi_level",
    "carrier_mobility",
    "hall_factor",
    "band_masses",
    "band_structure",
)
for reasons in REFUSED.values():
    reasons.update(dict.fromkeys(KANE_ONLY, "not_provided"))
OFFERED["skb_s_rho_rh"] = {
    "measured": HALL,
    "chemical_potential": ["chemical_potential_k"],
    **SIGMA,
    "lorenz_number": ["lorenz_w_ohm_per_k2"],
    "reduced_fermi_level": ["reduced_fermi_level"],
    "carrier_concentration_by_band": ["carrier_concentration_band_1_per_cm3"],
    "carrier_mobility": ["mobility_m2_per_v_s", "hall_mobility_m2_per_v_s"],
    "hall_factor": ["hall_factor"],
    "band_masses": ["band_edge_dos_mass_me", "band_edge_valley_mass_me"],
    "band_structure": ["wavevector_per_m", "band_energy_ev"],
}
REFUSED["skb_s_rho_rh"] = dict.fromkeys(
    (
        "seebeck",
        "seebeck_by_band",
        "electrical_conductivity_by_band",
        "thermal_conductivity",
    ),
    "not_provided",
)
SCATTERING["skb_s_rho_rh"] = ("acPh",)


def _model_id(fit_mode_id: str) -> str:
    return fit_mode_id.split("_")[0]


def _defaults(fit_mode_id: str) -> dict[str, float]:
    return default_start(registry.get(_model_id(fit_mode_id)).describe().fit_mode(fit_mode_id))


def _body(fit_mode_id: str, scattering: str | None, kind: str) -> dict[str, Any]:
    return {
        "model": _model_id(fit_mode_id),
        "fit_mode": fit_mode_id,
        "scattering": scattering,
        "kind": kind,
        "parameters": _defaults(fit_mode_id),
        "min_temperature_k": 100.0,
        "max_temperature_k": 800.0,
        "points": 8,
    }


OFFERED_CELLS = [
    (fit_mode_id, scattering, kind)
    for fit_mode_id, kinds in OFFERED.items()
    for scattering in SCATTERING[fit_mode_id]
    for kind in kinds
]
REFUSED_CELLS = [
    (fit_mode_id, scattering, kind)
    for fit_mode_id, kinds in REFUSED.items()
    for scattering in SCATTERING[fit_mode_id]
    for kind in kinds
]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def modes(client: TestClient) -> dict[str, dict[str, Any]]:
    models = client.get("/api/models").json()["models"]
    return {mode["id"]: mode for model in models for mode in model["fit_modes"]}


def test_the_matrix_covers_every_cell() -> None:
    for fit_mode_id in OFFERED:
        assert set(OFFERED[fit_mode_id]) | set(REFUSED[fit_mode_id]) == set(ALL_CURVE_KINDS)
        assert not set(OFFERED[fit_mode_id]) & set(REFUSED[fit_mode_id])


@pytest.mark.parametrize(("fit_mode_id", "scattering", "kind"), OFFERED_CELLS)
def test_offered_curve_equals_the_core(
    client: TestClient, fit_mode_id: str, scattering: str | None, kind: str
) -> None:
    expected = registry.get(_model_id(fit_mode_id)).calculate(
        CurveRequest(fit_mode_id, _defaults(fit_mode_id), 100, 800, 8, scattering, kind)  # type: ignore[arg-type]
    )

    response = client.post("/api/calc", json=_body(fit_mode_id, scattering, kind))

    assert response.status_code == 200
    body = response.json()
    assert list(body["curves"]) == OFFERED[fit_mode_id][kind]
    for name, values in expected.curves.items():
        assert body["curves"][name] == values.tolist()
    assert body["known_issues"] == list(expected.known_issues)


@pytest.mark.parametrize(("fit_mode_id", "scattering", "kind"), REFUSED_CELLS)
def test_refused_curve_gives_its_reason(
    client: TestClient, fit_mode_id: str, scattering: str | None, kind: str
) -> None:
    response = client.post("/api/calc", json=_body(fit_mode_id, scattering, kind))

    assert response.status_code == 422
    assert response.json()["code"] == "curve_unavailable"
    reason = REFUSED[fit_mode_id][kind]
    assert response.json()["details"] == [
        {
            "location": ["body", "kind"],
            "code": reason,
            "message": "See curve_unavailable in the API's README",
        }
    ]


@pytest.mark.parametrize("fit_mode_id", OFFERED)
def test_models_list_the_same_matrix(modes: dict[str, dict[str, Any]], fit_mode_id: str) -> None:
    curves = {curve["kind"]: curve for curve in modes[fit_mode_id]["curves"]}

    assert {kind for kind, curve in curves.items() if curve["available"]} == set(
        OFFERED[fit_mode_id]
    )
    assert {
        kind: curve["reason"] for kind, curve in curves.items() if not curve["available"]
    } == REFUSED[fit_mode_id]
    assert all("reason" not in curve for curve in curves.values() if curve["available"])


def test_disabled_mode_lists_its_curves_and_refuses_them(
    client: TestClient, modes: dict[str, dict[str, Any]]
) -> None:
    curves = {curve["kind"]: curve for curve in modes["spb_s_rho_rh"]["curves"]}
    assert curves["chemical_potential"]["available"] is True

    response = client.post("/api/calc", json=_body("spb_s_rho_rh", "acPh", "chemical_potential"))

    assert response.status_code == 409
    assert response.json()["code"] == "fit_mode_disabled"


@pytest.mark.parametrize(
    ("fit_mode_id", "relative"),
    [("dpb_s", True), ("dpb_s_rho", True), ("dpb_s_rho_rh", False)],
)
def test_carrier_concentration_is_relative_without_hall_data(
    modes: dict[str, dict[str, Any]], fit_mode_id: str, relative: bool
) -> None:
    flags = {curve["kind"]: curve["relative"] for curve in modes[fit_mode_id]["curves"]}

    assert flags.pop("carrier_concentration_by_band") is relative
    assert not any(flags.values())


def test_absolute_n_scales_with_m1_and_relative_n_uses_one(client: TestClient) -> None:
    kind = "carrier_concentration_by_band"
    body = _body("dpb_s_rho_rh", "acPh", kind)
    at_one = client.post("/api/calc", json=body).json()["curves"]
    body["parameters"] = body["parameters"] | {"m1": 2.0}
    at_two = client.post("/api/calc", json=body).json()["curves"]
    relative = client.post("/api/calc", json=_body("dpb_s_rho", "acPh", kind)).json()["curves"]

    assert relative == at_one
    # The density of states goes as m^1.5, for both bands, as they share m1.
    for name, values in at_one.items():
        assert at_two[name] == pytest.approx([value * 2**1.5 for value in values], rel=1e-12)


def test_r_h_scales_inversely_with_n_through_m1(client: TestClient) -> None:
    body = _body("dpb_s_rho_rh", "acPh", "measured")
    at_one = client.post("/api/calc", json=body).json()["curves"]
    body["parameters"] = body["parameters"] | {"m1": 2.0}
    at_two = client.post("/api/calc", json=body).json()["curves"]

    expected = [value / 2**1.5 for value in at_one["hall_m3_per_c"]]
    assert at_two["hall_m3_per_c"] == pytest.approx(expected, rel=1e-12)
    assert at_two["seebeck_v_per_k"] == at_one["seebeck_v_per_k"]
    assert at_two["resistivity_ohm_m"] == at_one["resistivity_ohm_m"]


def test_negative_m1_in_n_is_refused(client: TestClient) -> None:
    body = _body("dpb_s_rho_rh", "acPh", "carrier_concentration_by_band")
    body["parameters"] = body["parameters"] | {"m1": -1.0}

    response = client.post("/api/calc", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"


def test_disabled_mode_answers_first_even_for_a_curve_it_lacks(client: TestClient) -> None:
    response = client.post("/api/calc", json=_body("spb_s_rho_rh", "acPh", "seebeck_by_band"))

    assert response.status_code == 409


def test_bad_parameters_are_reported_before_an_unavailable_curve(client: TestClient) -> None:
    body = _body("spb_s", None, "seebeck_by_band") | {"parameters": {"band_mass": 1.0}}

    response = client.post("/api/calc", json=body)

    assert response.json()["code"] == "invalid_calculation"


@pytest.mark.parametrize(
    ("fit_mode_id", "scattering", "kind", "issue"),
    [
        ("dpb_s_rho_rh", "acPh", "carrier_concentration_by_band", "dpb_hall_prefactor"),
        ("spb_s_rho", "acPhDis", "electrical_conductivity", "acphdis_curve_scale"),
        ("spb_s_rho", "acPhDis", "thermal_conductivity", "acphdis_curve_scale"),
        ("dpb_s_rho", "acPhDis", "seebeck_by_band", "acphdis_curve_scale"),
        ("dpb_s_rho", "acPhDis", "electrical_conductivity_by_band", "acphdis_curve_scale"),
    ],
)
def test_known_issues_are_flagged_on_affected_curves(
    client: TestClient, fit_mode_id: str, scattering: str, kind: str, issue: str
) -> None:
    body = client.post("/api/calc", json=_body(fit_mode_id, scattering, kind)).json()

    assert issue in body["known_issues"]


def test_acphdis_flag_is_not_on_curves_it_does_not_change(client: TestClient) -> None:
    body = client.post("/api/calc", json=_body("dpb_s_rho", "acPhDis", "chemical_potential")).json()

    assert "acphdis_curve_scale" not in body["known_issues"]


def test_measurements_need_the_measured_kind(client: TestClient) -> None:
    measurements = {"seebeck": {"temperature_k": [300.0, 500.0], "values": [1.0e-4, 2.0e-4]}}
    body = _body("dpb_s_rho", "acPh", "chemical_potential") | {"measurements": measurements}

    response = client.post("/api/calc", json=body)

    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "measurements_need_measured_kind"


def test_unknown_kind_is_refused(client: TestClient) -> None:
    response = client.post("/api/calc", json=_body("dpb_s", None, "nope"))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
