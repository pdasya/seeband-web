import asyncio
import json
import logging
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pool_functions
import pytest
from fastapi.testclient import TestClient
from seeband_api.calc import CalcRequest, CalcResponse, _to_response
from seeband_api.calc_pool import CalcPool
from seeband_api.calc_worker import CalcOutcome
from seeband_api.errors import ApiError
from seeband_api.main import create_app
from seeband_api.settings import Settings
from seeband_core.fit_quality import curve_rmse
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest, CurveResult, Measurement
from seeband_core.model_scales import default_start

MODES = [
    (description.id, fit_mode.id, scattering)
    for description in registry.descriptions()
    for fit_mode in description.fit_modes
    if not fit_mode.disabled
    for scattering in fit_mode.scattering or (None,)
]
DPB_S_RHO_PARAMETERS = default_start(registry.get("dpb").describe().fit_mode("dpb_s_rho"))


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _body(**changes: Any) -> dict[str, Any]:
    return {
        "model": "dpb",
        "fit_mode": "dpb_s_rho",
        "scattering": "acPh",
        "parameters": DPB_S_RHO_PARAMETERS,
        "min_temperature_k": 100.0,
        "max_temperature_k": 500.0,
        "points": 11,
    } | changes


def _details(response: Any) -> list[tuple[list[str | int], str]]:
    return [(detail["location"], detail["code"]) for detail in response.json()["details"]]


@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), MODES)
def test_curves_are_exactly_those_of_the_core(
    client: TestClient, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    model = registry.get(model_id)
    parameters = default_start(model.describe().fit_mode(fit_mode_id))
    expected = model.calculate(CurveRequest(fit_mode_id, parameters, 50, 800, 50, scattering))

    response = client.post(
        "/api/calc",
        json={
            "model": model_id,
            "fit_mode": fit_mode_id,
            "scattering": scattering,
            "parameters": parameters,
            "min_temperature_k": 50,
            "max_temperature_k": 800,
            "points": 50,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["temperature_k"] == expected.temperature_k.tolist()
    assert list(body["curves"]) == list(expected.curves)
    assert (
        list(body["curves"])
        == [
            ["seebeck_v_per_k"],
            ["seebeck_v_per_k", "resistivity_ohm_m"],
            ["seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c"],
        ][len(model.describe().fit_mode(fit_mode_id).quantities) - 1]
    )
    for name, values in expected.curves.items():
        assert body["curves"][name] == values.tolist()
    assert body["known_issues"] == list(expected.known_issues)
    assert body["rmse"] == {}


def test_rmse_is_that_of_the_core_on_the_grid_asked_for(client: TestClient) -> None:
    temperature_k = [150.0, 300.0, 450.0]
    seebeck = [1.0e-4, 2.0e-4, 1.5e-4]
    resistivity = [1.0e-5, 2.0e-5, 3.0e-5]
    measurements = {
        "seebeck": Measurement(np.array(temperature_k), np.array(seebeck)),
        "resistivity": Measurement(np.array(temperature_k), np.array(resistivity)),
    }
    expected = curve_rmse(
        registry.get("dpb"),
        "dpb_s_rho",
        DPB_S_RHO_PARAMETERS,
        measurements,  # type: ignore[arg-type]
        "acPh",
        points=30,
    )

    response = client.post(
        "/api/calc",
        json=_body(
            rmse_points=30,
            measurements={
                "seebeck": {"temperature_k": temperature_k, "values": seebeck},
                "resistivity": {"temperature_k": temperature_k, "values": resistivity},
            },
        ),
    )

    assert response.status_code == 200
    assert response.json()["rmse"] == {
        "seebeck": {"value": expected["seebeck"].value, "unit": "uV/K"},
        "resistivity": {"value": expected["resistivity"].value, "unit": "%"},
    }


def test_measured_resistivity_gives_conductivity_points(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            measurements={
                "seebeck": {"temperature_k": [150.0, 300.0], "values": [1.0e-4, 2.0e-4]},
                "resistivity": {"temperature_k": [150.0, 300.0], "values": [1.0e-5, 4.0e-5]},
            },
        ),
    )

    assert response.status_code == 200
    points = response.json()["measured_points"]
    assert list(points) == ["electrical_conductivity_s_per_m"]
    assert points["electrical_conductivity_s_per_m"]["temperature_k"] == [150.0, 300.0]
    assert points["electrical_conductivity_s_per_m"]["values"] == pytest.approx([1.0e5, 2.5e4])


def test_a_resistivity_below_zero_gives_a_null_point(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            measurements={
                "resistivity": {"temperature_k": [150.0, 300.0], "values": [-1.0e-5, 4.0e-5]},
            },
        ),
    )

    assert response.status_code == 200
    values = response.json()["measured_points"]["electrical_conductivity_s_per_m"]["values"]
    assert values == [None, pytest.approx(2.5e4)]


def test_other_kinds_of_curve_give_no_points(client: TestClient) -> None:
    response = client.post("/api/calc", json=_body(kind="chemical_potential"))

    assert response.status_code == 200
    assert response.json()["measured_points"] == {}


def test_no_resistivity_gives_no_points(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            measurements={"seebeck": {"temperature_k": [150.0], "values": [1.0e-4]}},
        ),
    )

    assert response.status_code == 200
    assert response.json()["measured_points"] == {}


def test_rmse_grid_defaults_to_50_points(client: TestClient) -> None:
    measurements = {"seebeck": {"temperature_k": [150.0, 450.0], "values": [1.0e-4, 1.5e-4]}}
    expected = curve_rmse(
        registry.get("dpb"),
        "dpb_s_rho",
        DPB_S_RHO_PARAMETERS,
        {"seebeck": Measurement(np.array([150.0, 450.0]), np.array([1.0e-4, 1.5e-4]))},
        "acPh",
        points=50,
    )

    response = client.post("/api/calc", json=_body(measurements=measurements))

    assert response.json()["rmse"]["seebeck"]["value"] == expected["seebeck"].value


def test_both_degeneracies_reach_the_curve(client: TestClient) -> None:
    # Only their ratio matters in this mode, so band 1 changes the curve as well as band 2.
    expected = registry.get("dpb").calculate(
        CurveRequest("dpb_s_rho", DPB_S_RHO_PARAMETERS, 100, 500, 11, "acPh", "measured", 2.0, 1.0)
    )

    body = client.post("/api/calc", json=_body(band_1_degeneracy=2.0)).json()

    plain = client.post("/api/calc", json=_body()).json()
    assert body["curves"]["seebeck_v_per_k"] == expected.curves["seebeck_v_per_k"].tolist()
    assert body["curves"] != plain["curves"]


def test_infinite_curve_value_comes_back_as_null() -> None:
    curve = CurveResult(np.array([100.0, 200.0]), {"seebeck_v_per_k": np.array([np.inf, 1.0])})

    response = _to_response(CalcOutcome(curve, {}))

    assert response.curves["seebeck_v_per_k"] == [None, 1.0]
    assert response.model_dump_json().count("null") == 1


@pytest.mark.parametrize(
    "field",
    [
        '"min_temperature_k":1e400',
        '"max_temperature_k":1e400',
        '"band_1_degeneracy":1e400',
        '"measurements":{"seebeck":{"temperature_k":[1e400],"values":[1.0]}}',
    ],
)
def test_number_too_large_to_hold_is_refused(client: TestClient, field: str) -> None:
    fixed = _body()
    content = json.dumps(fixed)[:-1] + "," + field + "}"

    response = client.post(
        "/api/calc", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize(
    "changes",
    [
        {"parameters": DPB_S_RHO_PARAMETERS | {"m_eff": True}},
        {"parameters": DPB_S_RHO_PARAMETERS | {"m_eff": "1.5"}},
        {"min_temperature_k": "150"},
        {"points": "5"},
        {"points": 5.5},
        {"extrapolated": "yes"},
        {"band_2_degeneracy": True},
    ],
)
def test_values_of_the_wrong_type_are_refused(client: TestClient, changes: dict[str, Any]) -> None:
    response = client.post("/api/calc", json=_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_whole_numbers_are_accepted_for_floats(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(min_temperature_k=100, parameters=DPB_S_RHO_PARAMETERS | {"A": 40000}),
    )

    assert response.status_code == 200


def test_settings_reach_the_pool() -> None:
    with TestClient(create_app(Settings(calc_workers=3, calc_timeout_s=7.0))) as test_client:
        pool = test_client.app.state.calc_pool
        assert pool._workers == 3
        assert pool._timeout_s == 7.0
    with pytest.raises(RuntimeError):
        pool._executor.submit(int)


@pytest.mark.parametrize(
    ("scattering", "band_1", "band_2"),
    [
        ("dis", 1.0, 1.0),
        ("acPhDis", 1.0, 1.0),
        ("acPh", 2.0, 1.0),
        ("acPh", 1.0, 3.0),
        ("dis", 2.0, 5.0),
    ],
)
def test_rmse_uses_the_scattering_and_degeneracies_asked_for(
    client: TestClient, scattering: str, band_1: float, band_2: float
) -> None:
    temperature_k = [150.0, 450.0]
    values = [1.0e-5, 3.0e-5]
    expected = curve_rmse(
        registry.get("dpb"),
        "dpb_s_rho",
        DPB_S_RHO_PARAMETERS,
        {"resistivity": Measurement(np.array(temperature_k), np.array(values))},
        scattering,
        band_1,
        band_2,
        points=50,
    )

    response = client.post(
        "/api/calc",
        json=_body(
            scattering=scattering,
            band_1_degeneracy=band_1,
            band_2_degeneracy=band_2,
            measurements={"resistivity": {"temperature_k": temperature_k, "values": values}},
        ),
    )

    assert response.json()["rmse"]["resistivity"]["value"] == expected["resistivity"].value


def test_degeneracies_reach_the_core(client: TestClient) -> None:
    expected = registry.get("dpb").calculate(
        CurveRequest("dpb_s_rho", DPB_S_RHO_PARAMETERS, 100, 500, 11, "acPh", "measured", 1.0, 3.0)
    )

    body = client.post("/api/calc", json=_body(band_2_degeneracy=3.0)).json()

    assert body["curves"]["seebeck_v_per_k"] == expected.curves["seebeck_v_per_k"].tolist()


@pytest.mark.parametrize(("band_1", "band_2"), [(0.5, 1.0), (1.0, 2.5), (1.5, 0.25)])
def test_fractional_degeneracies_reach_the_core(
    client: TestClient, band_1: float, band_2: float
) -> None:
    expected = registry.get("dpb").calculate(
        CurveRequest(
            "dpb_s_rho", DPB_S_RHO_PARAMETERS, 100, 500, 11, "acPh", "measured", band_1, band_2
        )
    )

    body = client.post(
        "/api/calc", json=_body(band_1_degeneracy=band_1, band_2_degeneracy=band_2)
    ).json()

    assert body["curves"]["seebeck_v_per_k"] == expected.curves["seebeck_v_per_k"].tolist()


def test_points_default_to_the_model(client: TestClient) -> None:
    body = _body()
    del body["points"]

    assert len(client.post("/api/calc", json=body).json()["temperature_k"]) == 50


def test_known_issues_reach_the_client(client: TestClient) -> None:
    body = client.post("/api/calc", json=_body(scattering="acPhDis")).json()

    assert "acphdis_curve_scale" not in body["known_issues"]
    assert "acphdis_band_weight" not in body["known_issues"]


def test_extrapolated_data_is_flagged(client: TestClient) -> None:
    plain = client.post("/api/calc", json=_body()).json()
    flagged = client.post("/api/calc", json=_body(extrapolated=True)).json()

    assert "interpolation_extrapolates" not in plain["known_issues"]
    assert "interpolation_extrapolates" in flagged["known_issues"]


def test_values_that_are_not_finite_come_back_as_null(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json={
            "model": "spb",
            "fit_mode": "spb_s",
            "parameters": {"band_mass": 1.0, "fermi_energy": 1e6},
            "min_temperature_k": 100,
            "max_temperature_k": 500,
            "points": 5,
            "measurements": {"seebeck": {"temperature_k": [300.0], "values": [1.0e-4]}},
        },
    )

    assert response.status_code == 200
    assert response.json()["curves"]["seebeck_v_per_k"] == [None] * 5
    assert response.json()["rmse"]["seebeck"] == {"value": None, "unit": "uV/K"}


@pytest.mark.parametrize(
    "parameters",
    [
        {"band_mass": 0.0, "fermi_energy": 100.0},
        {"band_mass": 1.0, "fermi_energy": 0.0},
        {"band_mass": -1.0, "fermi_energy": 100.0},
    ],
)
def test_spb_without_a_finite_chemical_potential_is_an_explicit_error(
    client: TestClient, parameters: dict[str, float]
) -> None:
    response = client.post(
        "/api/calc",
        json=_body(model="spb", fit_mode="spb_s", scattering=None, parameters=parameters),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"
    assert response.json()["details"] == []


def test_parameters_with_no_result_answer_a_clear_error(client: TestClient) -> None:
    parameters = DPB_S_RHO_PARAMETERS | {"m_eff": 0.0}

    response = client.post("/api/calc", json=_body(parameters=parameters))

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"
    assert response.json()["details"] == []


def test_hall_curve_with_a_value_that_is_not_finite_fails_and_is_logged(client: TestClient) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho_rh")
    logger = logging.getLogger("seeband_api")
    records: list[logging.LogRecord] = []

    class Recorder(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    recorder = Recorder()
    logger.addHandler(recorder)
    try:
        response = client.post(
            "/api/calc",
            json=_body(
                fit_mode="dpb_s_rho_rh",
                parameters=default_start(fit_mode) | {"fermi_energy": 3000.0},
                min_temperature_k=2.0,
                max_temperature_k=300.0,
                points=50,
            ),
        )
    finally:
        logger.removeHandler(recorder)

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"
    failures = [r for r in records if r.getMessage() == "calculation_failed"]
    assert [r.__dict__["fields"] for r in failures] == [{"exception_type": "ValueError"}]


def test_complex_curve_is_refused_rather_than_cut_to_its_real_part(client: TestClient) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho_rh")

    response = client.post(
        "/api/calc",
        json=_body(fit_mode="dpb_s_rho_rh", parameters=default_start(fit_mode) | {"m1": -1.0}),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"


def test_same_condition_leaves_a_null_in_the_mode_without_hall_data(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            parameters=DPB_S_RHO_PARAMETERS | {"fermi_energy": 3000.0},
            min_temperature_k=2.0,
            max_temperature_k=300.0,
            points=50,
        ),
    )

    assert response.status_code == 200
    assert None in response.json()["curves"]["seebeck_v_per_k"]


def test_lone_surrogate_in_a_name_answers_in_the_error_format(client: TestClient) -> None:
    content = json.dumps(_body()).replace('"m_eff"', '"\\ud800"')

    response = client.post(
        "/api/calc", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_calculation"
    assert ["body", "parameters", "\ud800"] in [d["location"] for d in response.json()["details"]]


def test_values_outside_a_control_are_allowed(client: TestClient) -> None:
    parameters = DPB_S_RHO_PARAMETERS | {"A": 1e12}

    assert client.post("/api/calc", json=_body(parameters=parameters)).status_code == 200


def test_spb_hall_mode_returns_finite_hall_curves(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            model="spb",
            fit_mode="spb_s_rho_rh",
            parameters=default_start(registry.get("spb").describe().fit_mode("spb_s_rho_rh")),
        ),
    )

    assert response.status_code == 200
    hall = response.json()["curves"]["hall_m3_per_c"]
    assert len(hall) == 11
    assert all(value is not None and math.isfinite(value) for value in hall)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"model": "nope"}, [(["body", "model"], "unknown_model")]),
        ({"fit_mode": "nope"}, [(["body", "fit_mode"], "unknown_fit_mode")]),
        ({"scattering": None}, [(["body", "scattering"], "missing_scattering")]),
        ({"scattering": "nope"}, [(["body", "scattering"], "unknown_scattering")]),
        (
            {
                "fit_mode": "dpb_s",
                "parameters": {"m_eff": 1.0, "band_gap": 1.0, "fermi_energy": 1.0},
            },
            [(["body", "scattering"], "unknown_scattering")],
        ),
        (
            {"parameters": {"m_eff": 1.0, "nope": 2.0}},
            [
                *[
                    (["body", "parameters", name], "missing_parameter")
                    for name in DPB_S_RHO_PARAMETERS
                    if name != "m_eff"
                ],
                (["body", "parameters", "nope"], "unknown_parameter"),
            ],
        ),
        (
            {"measurements": {"hall": {"temperature_k": [300.0], "values": [1.0]}}},
            [(["body", "measurements", "hall"], "quantity_not_in_mode")],
        ),
        (
            {"measurements": {"resistivity": {"temperature_k": [1.0, 2.0], "values": [1.0, 0.0]}}},
            [(["body", "measurements", "resistivity", "values", 1], "zero_measured_value")],
        ),
    ],
)
def test_invalid_calculations_name_the_problem(
    client: TestClient, changes: dict[str, Any], expected: list[tuple[list[str | int], str]]
) -> None:
    response = client.post("/api/calc", json=_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_calculation"
    assert _details(response) == expected


def test_zero_hall_value_is_refused(client: TestClient) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho_rh")
    measurements = {"hall": {"temperature_k": [150.0], "values": [0.0]}}

    response = client.post(
        "/api/calc",
        json=_body(
            fit_mode="dpb_s_rho_rh", parameters=default_start(fit_mode), measurements=measurements
        ),
    )

    location = ["body", "measurements", "hall", "values", 0]
    assert _details(response) == [(location, "zero_measured_value")]


def test_degeneracy_is_refused_on_a_mode_without_one(client: TestClient) -> None:
    fit_mode = registry.get("spb").describe().fit_mode("spb_s")

    response = client.post(
        "/api/calc",
        json=_body(
            model="spb",
            fit_mode="spb_s",
            scattering=None,
            parameters=default_start(fit_mode),
            band_1_degeneracy=5.0,
        ),
    )

    assert response.status_code == 422
    assert _details(response) == [(["body", "band_1_degeneracy"], "degeneracy_not_in_mode")]


def test_refused_model_uses_the_format_of_this_route(client: TestClient) -> None:
    for changes in ({"model": "nope"}, {"fit_mode": "nope"}):
        response = client.post("/api/calc", json=_body(**changes))

        assert response.json()["message"] == "Invalid calculation"


def test_zero_seebeck_value_is_allowed(client: TestClient) -> None:
    measurements = {"seebeck": {"temperature_k": [150.0, 450.0], "values": [0.0, 1.5e-4]}}

    assert client.post("/api/calc", json=_body(measurements=measurements)).status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"min_temperature_k": 500.0, "max_temperature_k": 100.0},
        {"min_temperature_k": 100.0, "max_temperature_k": 100.0},
        {"min_temperature_k": 0.0},
        {"min_temperature_k": -5.0},
        {"points": 1},
        {"points": 1001},
        {"rmse_points": 1},
        {"rmse_points": 1001},
        {"band_1_degeneracy": 0.0},
        {"band_2_degeneracy": -1.0},
        {"measurements": {"seebeck": {"temperature_k": [], "values": []}}},
        {"measurements": {"seebeck": {"temperature_k": [300.0], "values": [1.0, 2.0]}}},
        {"measurements": {"seebeck": {"temperature_k": [0.0], "values": [1.0]}}},
        {"measurements": {"nope": {"temperature_k": [300.0], "values": [1.0]}}},
    ],
)
def test_invalid_requests_are_refused_before_any_calculation(
    client: TestClient, changes: dict[str, Any]
) -> None:
    response = client.post("/api/calc", json=_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize(
    "template",
    [
        '{{"model":"dpb","fit_mode":"dpb_s","parameters":{{"m_eff":{token}}},'
        '"min_temperature_k":100,"max_temperature_k":500}}',
        '{{"model":"dpb","fit_mode":"dpb_s","parameters":{{}},'
        '"min_temperature_k":{token},"max_temperature_k":500}}',
        '{{"model":"dpb","fit_mode":"dpb_s","parameters":{{}},"min_temperature_k":100,'
        '"max_temperature_k":500,"measurements":{{"seebeck":{{"temperature_k":[300],'
        '"values":[{token}]}}}}}}',
    ],
)
def test_numbers_that_are_not_finite_are_refused(
    client: TestClient, template: str, token: str
) -> None:
    response = client.post(
        "/api/calc",
        content=template.format(token=token),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_calls_keep_no_state(client: TestClient) -> None:
    measurements = {"seebeck": {"temperature_k": [150.0], "values": [1.0e-4]}}
    first = client.post("/api/calc", json=_body()).json()

    client.post(
        "/api/calc",
        json=_body(
            parameters=DPB_S_RHO_PARAMETERS | {"m_eff": 2.0}, measurements=measurements, points=7
        ),
    )

    assert client.post("/api/calc", json=_body()).json() == first


def test_examples_in_the_contract_fit_the_core(client: TestClient) -> None:
    """The mock serves these, so they should be what the API would answer, to the digits shown."""
    request = CalcRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]
    example = CalcResponse.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    answer = client.post("/api/calc", json=request)

    assert answer.status_code == 200
    body = answer.json()
    assert body["temperature_k"] == example["temperature_k"]
    assert body["known_issues"] == example["known_issues"]
    assert list(body["curves"]) == list(example["curves"])
    for name, values in example["curves"].items():
        assert np.allclose(body["curves"][name], values, rtol=1e-3, atol=0.0)
    assert body["rmse"]["seebeck"]["unit"] == example["rmse"]["seebeck"]["unit"]
    assert math.isclose(
        body["rmse"]["seebeck"]["value"], example["rmse"]["seebeck"]["value"], rel_tol=1e-3
    )


def _run_in_pool(pool: CalcPool, function: Any, *args: Any) -> Any:
    async def run() -> Any:
        return await pool.run(function, *args)

    return asyncio.run(run())


def test_slow_calculation_answers_504() -> None:
    pool = CalcPool(1, 2.0)
    try:
        # The worker has started by now, so the time limit is spent on the calculation.
        assert _run_in_pool(pool, pool_functions.double, 21) == 42
        pool._timeout_s = 0.2
        with pytest.raises(ApiError) as raised:
            _run_in_pool(pool, pool_functions.sleep_for_a_while)
        # A stuck worker cannot be interrupted, so this reaches inside the pool to end the test.
        for process in list(pool._executor._processes.values()):
            process.terminate()
    finally:
        pool.close()

    assert raised.value.status_code == 504
    assert raised.value.code == "calculation_timeout"


def test_dead_worker_answers_503_and_the_pool_recovers() -> None:
    pool = CalcPool(1, 30.0)
    try:
        with pytest.raises(ApiError) as raised:
            _run_in_pool(pool, pool_functions.die)
        assert raised.value.status_code == 503
        assert raised.value.code == "calculation_unavailable"

        assert _run_in_pool(pool, pool_functions.double, 21) == 42
    finally:
        pool.close()


def test_contract_file_lists_the_route() -> None:
    contract = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"

    operation = json.loads(contract.read_text(encoding="utf-8"))["paths"]["/api/calc"]["post"]

    assert operation["operationId"] == "post_calc"
