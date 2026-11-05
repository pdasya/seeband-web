import math
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from seeband_api.fit import FitApiRequest, FitResponse, _to_response
from seeband_api.main import create_app
from seeband_api.settings import Settings
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Bounds, FitRequest, FitResult, Measurement
from seeband_core.model_scales import default_start

MODES = [
    (description.id, fit_mode.id, scattering)
    for description in registry.descriptions()
    for fit_mode in description.fit_modes
    if not fit_mode.disabled
    for scattering in fit_mode.scattering or (None,)
]
DEMO = load_demo_dataset().measurements
DEMO_INPUT = {
    quantity: {
        "temperature_k": measurement.temperature_k.tolist(),
        "values": measurement.values.tolist(),
    }
    for quantity, measurement in DEMO.items()
}
LOW_K = float(DEMO["seebeck"].temperature_k.min())
HIGH_K = float(DEMO["seebeck"].temperature_k.max())


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _mode(model_id: str, fit_mode_id: str) -> Any:
    return registry.get(model_id).describe().fit_mode(fit_mode_id)


def _body(model_id: str = "dpb", fit_mode_id: str = "dpb_s", **changes: Any) -> dict[str, Any]:
    mode = _mode(model_id, fit_mode_id)
    return {
        "model": model_id,
        "fit_mode": fit_mode_id,
        "start": default_start(mode),
        "min_temperature_k": LOW_K,
        "max_temperature_k": HIGH_K,
        "measurements": {quantity: DEMO_INPUT[quantity] for quantity in mode.quantities},
    } | changes


def _core_fit(model_id: str, fit_mode_id: str, **fields: Any) -> Any:
    mode = _mode(model_id, fit_mode_id)
    return registry.get(model_id).fit(
        FitRequest(
            fit_mode_id,
            {quantity: DEMO[quantity] for quantity in mode.quantities},
            default_start(mode),
            **fields,
        )
    )


def _details(response: Any) -> list[tuple[list[str | int], str]]:
    return [(detail["location"], detail["code"]) for detail in response.json()["details"]]


@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), MODES)
def test_result_equals_the_core(
    client: TestClient, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    expected = _core_fit(model_id, fit_mode_id, scattering=scattering)

    response = client.post("/api/fit", json=_body(model_id, fit_mode_id, scattering=scattering))

    assert response.status_code == 200
    body = response.json()
    assert body["parameters"] == expected.parameters
    assert body["status"] == expected.status
    assert body.get("iterations") == expected.iterations
    assert body["parameter_errors"] == expected.parameter_errors
    assert body["at_bounds"] == list(expected.at_bounds)
    assert body["known_issues"] == list(expected.known_issues)


def test_custom_bounds_reach_the_fit(client: TestClient) -> None:
    # The default start of the band gap is 1000 K, and the fit leaves it without these bounds.
    bounds = Bounds(990.0, 1010.0)
    free = _core_fit("dpb", "dpb_s")
    expected = _core_fit("dpb", "dpb_s", bounds={"band_gap": bounds})
    assert free.parameters["band_gap"] != expected.parameters["band_gap"]

    body = client.post(
        "/api/fit", json=_body(bounds={"band_gap": {"lower": 990.0, "upper": 1010.0}})
    ).json()

    assert body["status"] == "converged"
    assert body["parameters"] == expected.parameters
    assert 990.0 <= body["parameters"]["band_gap"] <= 1010.0


def test_start_outside_the_bounds_is_a_failed_fit(client: TestClient) -> None:
    body = client.post(
        "/api/fit", json=_body(bounds={"band_gap": {"lower": 1.0, "upper": 2.0}})
    ).json()

    assert body["status"] == "failed"
    assert "bound" in body["message"].lower()
    assert body["parameters"] == default_start(_mode("dpb", "dpb_s"))


def test_degeneracies_reach_the_fit(client: TestClient) -> None:
    expected = _core_fit(
        "dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=2.0, band_2_degeneracy=3.0
    )

    body = client.post(
        "/api/fit",
        json=_body(
            "dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=2.0, band_2_degeneracy=3.0
        ),
    ).json()

    assert body["parameters"] == expected.parameters
    assert "dpb_loop_degeneracy" in body["known_issues"]


def test_extrapolated_data_is_flagged(client: TestClient) -> None:
    plain = client.post("/api/fit", json=_body()).json()
    flagged = client.post("/api/fit", json=_body(extrapolated=True)).json()

    assert "interpolation_extrapolates" not in plain["known_issues"]
    assert "interpolation_extrapolates" in flagged["known_issues"]


def test_only_points_in_the_fit_range_enter_the_fit(client: TestClient) -> None:
    temperature_k = DEMO["seebeck"].temperature_k
    low, high = float(temperature_k[5]), float(temperature_k[25])
    inside = (temperature_k >= low) & (temperature_k <= high)
    expected = registry.get("dpb").fit(
        FitRequest(
            "dpb_s",
            {"seebeck": Measurement(temperature_k[inside], DEMO["seebeck"].values[inside])},
            default_start(_mode("dpb", "dpb_s")),
        )
    )

    body = client.post("/api/fit", json=_body(min_temperature_k=low, max_temperature_k=high)).json()

    assert body["parameters"] == expected.parameters


def test_disabled_mode_is_refused_before_any_process(client: TestClient) -> None:
    response = client.post(
        "/api/fit", json=_body("spb", "spb_s_rho_rh", scattering="acPh") | {"measurements": {}}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "fit_mode_disabled"
    assert _details(response) == [(["body", "fit_mode"], "spb_hall_mode_disabled")]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"model": "nope"}, [(["body", "model"], "unknown_model")]),
        ({"fit_mode": "nope"}, [(["body", "fit_mode"], "unknown_fit_mode")]),
        ({"scattering": "acPh"}, [(["body", "scattering"], "unknown_scattering")]),
        (
            {"start": {"m_eff": 1.0, "band_gap": 1.0}},
            [(["body", "start", "fermi_energy"], "missing_parameter")],
        ),
        (
            {"start": default_start(_mode("dpb", "dpb_s")) | {"nope": 1.0}},
            [(["body", "start", "nope"], "unknown_parameter")],
        ),
        (
            {"bounds": {"nope": {"lower": 0.0, "upper": 1.0}}},
            [(["body", "bounds", "nope"], "parameter_not_fitted")],
        ),
        ({"measurements": {}}, [(["body", "measurements", "seebeck"], "missing_measurement")]),
        (
            {"measurements": DEMO_INPUT},
            [
                (["body", "measurements", "resistivity"], "quantity_not_in_mode"),
                (["body", "measurements", "hall"], "quantity_not_in_mode"),
            ],
        ),
        (
            {"min_temperature_k": 1.0, "max_temperature_k": 2.0},
            [(["body", "measurements", "seebeck"], "no_points_in_range")],
        ),
    ],
)
def test_invalid_fits_name_the_problem(
    client: TestClient, changes: dict[str, Any], expected: list[tuple[list[str | int], str]]
) -> None:
    response = client.post("/api/fit", json=_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fit"
    assert _details(response) == expected


def test_bounds_the_desktop_fixes_are_refused(client: TestClient) -> None:
    response = client.post(
        "/api/fit",
        json=_body(
            "spb", "spb_s_rho", scattering="acPh", bounds={"A": {"lower": 1.0, "upper": 2.0}}
        ),
    )

    assert _details(response) == [(["body", "bounds", "A"], "bounds_not_editable")]


def test_bounds_of_a_parameter_of_another_scattering_type_are_refused(client: TestClient) -> None:
    response = client.post(
        "/api/fit",
        json=_body(
            "dpb", "dpb_s_rho", scattering="acPh", bounds={"F": {"lower": 1.0, "upper": 2.0}}
        ),
    )

    assert _details(response) == [(["body", "bounds", "F"], "parameter_not_fitted")]


def test_degeneracy_is_refused_on_a_mode_without_one(client: TestClient) -> None:
    response = client.post("/api/fit", json=_body("spb", "spb_s", band_2_degeneracy=2.0))

    assert _details(response) == [(["body", "band_2_degeneracy"], "degeneracy_not_in_mode")]


@pytest.mark.parametrize(
    "changes",
    [
        {"bounds": {"m_eff": {"lower": 2.0, "upper": 1.0}}},
        {"bounds": {"m_eff": {"lower": 1.0, "upper": 1.0}}},
        {"bounds": {"m_eff": {"lower": True, "upper": 2.0}}},
        {"start": {"m_eff": "1.5"}},
        {"min_temperature_k": 500.0, "max_temperature_k": 100.0},
        {"min_temperature_k": 0.0},
        {"extrapolated": "yes"},
        {"band_1_degeneracy": 0.0},
        {"measurements": {"seebeck": {"temperature_k": [1.0], "values": []}}},
        {"measurements": {"nope": {"temperature_k": [1.0], "values": [1.0]}}},
    ],
)
def test_invalid_requests_are_refused(client: TestClient, changes: dict[str, Any]) -> None:
    response = client.post("/api/fit", json=_body(**changes))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_full_queue_answers_429_with_a_retry_hint() -> None:
    settings = Settings(fit_max_running=1, fit_max_waiting=0)
    with TestClient(create_app(settings)) as client:
        # This fills the only slot, without timing a fit against the request below.
        semaphore = client.app.state.fit_runner._semaphore
        client.portal.call(semaphore.acquire)  # type: ignore[union-attr]

        response = client.post("/api/fit", json=_body())

        client.portal.call(semaphore.release)  # type: ignore[union-attr]

    assert response.status_code == 429
    assert response.json()["code"] == "fit_queue_full"
    assert response.headers["retry-after"] == "5"


def test_stopping_the_app_closes_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = []
    with TestClient(create_app()) as client:
        monkeypatch.setattr(client.app.state.fit_runner, "close", lambda: closed.append(True))

    assert closed == [True]


def test_value_that_is_not_finite_comes_back_as_null() -> None:
    result = FitResult({"m_eff": math.nan, "band_gap": 5.0}, "converged")

    assert _to_response(result).parameters == {"m_eff": None, "band_gap": 5.0}


def test_settings_reach_the_runner() -> None:
    settings = Settings(fit_max_running=3, fit_max_waiting=7, fit_timeout_s=9.0)
    with TestClient(create_app(settings)) as client:
        runner = client.app.state.fit_runner

    assert (runner._semaphore._value, runner._max_waiting, runner._timeout_s) == (3, 7, 9.0)


def test_process_past_the_time_limit_answers_504() -> None:
    settings = Settings(fit_timeout_s=0.001)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/fit", json=_body())

    assert response.status_code == 504
    assert response.json()["code"] == "fit_timeout"


def test_examples_in_the_contract_fit_their_schemas() -> None:
    request = FitApiRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]
    response = FitResponse.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    FitApiRequest.model_validate(request)
    FitResponse.model_validate(response)
    assert set(request["start"]) == set(default_start(_mode("dpb", "dpb_s")))


def test_example_request_is_a_fit_the_api_accepts(client: TestClient) -> None:
    request = FitApiRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    response = client.post("/api/fit", json=request)

    assert response.status_code == 200
    assert set(response.json()["parameters"]) == set(request["start"])
