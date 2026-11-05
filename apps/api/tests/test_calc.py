import asyncio
import json
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
    "template",
    [
        '{{"min_temperature_k":{token}}}',
        '{{"max_temperature_k":{token}}}',
        '{{"band_1_degeneracy":{token}}}',
        '{{"measurements":{{"seebeck":{{"temperature_k":[{token}],"values":[1.0]}}}}}}',
    ],
)
def test_infinite_positive_numbers_are_refused(client: TestClient, template: str) -> None:
    fields = json.loads(template.format(token="1e400"))

    response = client.post(
        "/api/calc",
        content=json.dumps(_body() | fields),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_rmse_passes_the_degeneracies(client: TestClient) -> None:
    measurements = {"seebeck": {"temperature_k": [150.0, 450.0], "values": [1.0e-4, 1.5e-4]}}
    plain = client.post("/api/calc", json=_body(measurements=measurements)).json()

    other = client.post(
        "/api/calc", json=_body(measurements=measurements, band_2_degeneracy=3.0)
    ).json()

    assert other["rmse"]["seebeck"]["value"] != plain["rmse"]["seebeck"]["value"]
    assert other["curves"]["seebeck_v_per_k"] != plain["curves"]["seebeck_v_per_k"]


def test_degeneracies_reach_the_core(client: TestClient) -> None:
    expected = registry.get("dpb").calculate(
        CurveRequest("dpb_s_rho", DPB_S_RHO_PARAMETERS, 100, 500, 11, "acPh", "measured", 1.0, 3.0)
    )

    body = client.post("/api/calc", json=_body(band_2_degeneracy=3.0)).json()

    assert body["curves"]["seebeck_v_per_k"] == expected.curves["seebeck_v_per_k"].tolist()


def test_points_default_to_the_model(client: TestClient) -> None:
    body = _body()
    del body["points"]

    assert len(client.post("/api/calc", json=body).json()["temperature_k"]) == 50


def test_known_issues_reach_the_client(client: TestClient) -> None:
    body = client.post("/api/calc", json=_body(scattering="acPhDis")).json()

    assert "acphdis_curve_scale" not in body["known_issues"]
    assert "acphdis_band_weight" in body["known_issues"]


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
            "parameters": {"band_mass": 0.0, "fermi_energy": 100.0},
            "min_temperature_k": 100,
            "max_temperature_k": 500,
            "points": 5,
            "measurements": {"seebeck": {"temperature_k": [300.0], "values": [1.0e-4]}},
        },
    )

    assert response.status_code == 200
    json.dumps(response.json(), allow_nan=False)
    assert response.json()["curves"]["seebeck_v_per_k"] == [None] * 5
    assert response.json()["rmse"]["seebeck"] == {"value": None, "unit": "uV/K"}


def test_parameters_with_no_result_answer_a_clear_error(client: TestClient) -> None:
    parameters = DPB_S_RHO_PARAMETERS | {"m_eff": 0.0}

    response = client.post("/api/calc", json=_body(parameters=parameters))

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"
    assert response.json()["details"] == []


def test_values_outside_a_control_are_allowed(client: TestClient) -> None:
    parameters = DPB_S_RHO_PARAMETERS | {"A": 1e12}

    assert client.post("/api/calc", json=_body(parameters=parameters)).status_code == 200


def test_disabled_mode_is_refused_with_its_reason(client: TestClient) -> None:
    response = client.post(
        "/api/calc",
        json=_body(
            model="spb",
            fit_mode="spb_s_rho_rh",
            parameters=default_start(registry.get("spb").describe().fit_mode("spb_s_rho_rh")),
        ),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "fit_mode_disabled"
    assert response.json()["details"] == [
        {
            "location": ["body", "fit_mode"],
            "code": "spb_hall_mode_disabled",
            "message": "known_issue.spb_hall_mode_disabled",
        }
    ]


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
    pool = CalcPool(1, 0.2)
    try:
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
