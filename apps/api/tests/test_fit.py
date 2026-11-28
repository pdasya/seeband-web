import asyncio
import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import seeband_core
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from running_server import read_events
from seeband_api.errors import ErrorResponse
from seeband_api.fit import (
    _STREAM_EXAMPLES,
    FitApiRequest,
    FitResponse,
    _last_event,
    _to_response,
)
from seeband_api.main import create_app
from seeband_api.settings import Settings
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    Bounds,
    FitRequest,
    FitResult,
    IterationUpdate,
    Measurement,
)
from seeband_core.model_scales import default_start

MODES = [
    (description.id, fit_mode.id, scattering)
    for description in registry.descriptions()
    for fit_mode in description.fit_modes
    if not fit_mode.disabled
    for scattering in fit_mode.scattering or (None,)
]
# The API passes a fit through to the core; the core's own tests fit every combination. So the
# identity is checked for every SPB combination, and for each DPB mode once: two with the
# cheaper "dis", and the demo's own dpb_s_rho_rh with acPh. A DPB fit takes up to a minute.
RESULT_CASES = [
    mode
    for mode in MODES
    if mode[0] != "dpb"
    or mode
    in {("dpb", "dpb_s", "dis"), ("dpb", "dpb_s_rho", "dis"), ("dpb", "dpb_s_rho_rh", "acPh")}
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


def _events(client: TestClient, body: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.post("/api/fit", json=body)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return list(read_events(iter(response.text.splitlines())))


def _result(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    last = _events(client, body)[-1]
    assert last["type"] == "done", last
    result: dict[str, Any] = last["result"]
    return result


def _details(response: Any) -> list[tuple[list[str | int], str]]:
    return [(detail["location"], detail["code"]) for detail in response.json()["details"]]


def test_fit_result_identifies_the_core_version(client: TestClient) -> None:
    result = _result(client, _body("spb", "spb_s"))

    assert result["core_version"] == seeband_core.__version__


@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), RESULT_CASES)
def test_result_equals_the_core(
    client: TestClient, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    updates: list[IterationUpdate] = []
    mode = _mode(model_id, fit_mode_id)
    expected = registry.get(model_id).fit(
        FitRequest(
            fit_mode_id,
            {quantity: DEMO[quantity] for quantity in mode.quantities},
            default_start(mode),
            scattering=scattering,
        ),
        updates.append,
    )
    events = _events(client, _body(model_id, fit_mode_id, scattering=scattering))
    assert events[-1]["type"] == "done", events[-1]
    body = events[-1]["result"]

    assert body["parameters"] == expected.parameters
    assert body["status"] == expected.status
    assert body.get("iterations") == expected.iterations
    assert body["parameter_errors"] == expected.parameter_errors
    assert body["at_bounds"] == list(expected.at_bounds)
    assert body["known_issues"] == list(expected.known_issues)
    assert body["parameter_status"] == dict(expected.parameter_status)
    assert set(body["parameter_status"]) == set(body["parameters"])
    assert body["uncertainty"] == "not_assessed"
    assert body["last_changes"] == dict(expected.last_changes)

    if mode.iterative:
        assert updates
        assert events[0] == {"type": "started"}
        assert events[1:-1] == [
            {
                "type": "iteration",
                "iteration": update.iteration,
                "parameters": dict(update.parameters),
            }
            for update in updates
        ]


def test_a_fermi_energy_inside_the_gap_is_not_determined(client: TestClient) -> None:
    """R7, the review's s13 cases: E_F in the DPB gap with m_eff > 0 has no effect on S."""
    start = default_start(_mode("dpb", "dpb_s")) | {
        "m_eff": 1.2,
        "band_gap": 800.0,
        "fermi_energy": 400.0,
    }
    result = _result(
        client,
        _body(
            start=start,
            held=["m_eff", "band_gap"],
            algorithm="legacy-sequential-v1",
        ),
    )

    assert result["parameter_status"]["fermi_energy"] == "not_determined"
    assert result["parameter_status"]["m_eff"] == "held"
    assert "fermi_energy_in_gap" in result["known_issues"]


@pytest.mark.parametrize(
    ("model_id", "fit_mode_id", "scattering"),
    [mode for mode in MODES if not _mode(mode[0], mode[1]).iterative],
)
def test_single_pass_fit_sends_no_iteration_counter(
    client: TestClient, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    body = _body(model_id, fit_mode_id, scattering=scattering)
    if fit_mode_id == "spb_s_rho_rh":
        # The demo's R_H is above 0, holes, and an electron start is refused.
        body["start"] |= {"band_mass": -1.0, "fermi_energy": -100.0}
    events = _events(client, body)

    assert [event["type"] for event in events] == ["started", "done"]
    assert "iterations" not in events[-1]["result"]
    assert "message" not in events[-1]["result"]


def test_refused_model_uses_the_format_of_this_route(client: TestClient) -> None:
    response = client.post("/api/fit", json=_body(model="nope"))

    assert response.json()["code"] == "invalid_fit"
    assert response.json()["message"] == "Invalid fit"


def test_custom_bounds_reach_the_fit(client: TestClient) -> None:
    # The default start of the band gap is 1000 K, and the fit leaves it without these bounds.
    bounds = Bounds(990.0, 1010.0)
    free = _core_fit("dpb", "dpb_s")
    expected = _core_fit("dpb", "dpb_s", bounds={"band_gap": bounds})
    assert free.parameters["band_gap"] != expected.parameters["band_gap"]

    body = _result(client, _body(bounds={"band_gap": {"lower": 990.0, "upper": 1010.0}}))

    assert body["status"] == "converged"
    assert body["parameters"] == expected.parameters
    assert 990.0 <= body["parameters"]["band_gap"] <= 1010.0


def test_start_outside_the_bounds_is_a_failed_fit(client: TestClient) -> None:
    body = _result(client, _body(bounds={"band_gap": {"lower": 1.0, "upper": 2.0}}))

    assert body["status"] == "failed"
    assert "bound" in body["message"].lower()
    assert body["parameters"] == default_start(_mode("dpb", "dpb_s"))


_SPB_NO_ROOT = (
    "The fit started from a Fermi energy outside the band selected by the mass sign, "
    "which has no finite chemical potential."
)
_DPB_NO_ROOT = (
    "The fit started from a Fermi energy at or above the higher edge of two valence bands, "
    "which has no finite chemical potential."
)


@pytest.mark.parametrize(
    ("model", "mode", "start", "message"),
    [
        ("spb", "spb_s", {"band_mass": 1.0, "fermi_energy": 0.0}, _SPB_NO_ROOT),
        ("spb", "spb_s", {"band_mass": -1.0, "fermi_energy": 1.0}, _SPB_NO_ROOT),
        (
            "dpb",
            "dpb_s",
            {"m_eff": -1.0, "band_gap": 1000.0, "fermi_energy": 1000.0},
            _DPB_NO_ROOT,
        ),
        ("dpb", "dpb_s", {"m_eff": -1.0, "band_gap": -500.0, "fermi_energy": 0.0}, _DPB_NO_ROOT),
    ],
)
def test_no_root_at_the_start_ends_with_a_failed_fit(
    client: TestClient, model: str, mode: str, start: dict[str, float], message: str
) -> None:
    events = _events(client, _body(model, mode, start=start))

    assert [event["type"] for event in events] == ["started", "done"]
    result = events[-1]["result"]
    assert result["status"] == "failed"
    assert result["message"] == message
    assert result["parameters"] == start


@pytest.mark.parametrize("algorithm", ["verified-sequential-v2", "legacy-sequential-v1"])
@pytest.mark.parametrize(
    ("model", "mode", "start"),
    [
        ("spb", "spb_s", {"band_mass": 0.0, "fermi_energy": 100.0}),
        ("dpb", "dpb_s", {"m_eff": 0.0, "band_gap": 1000.0, "fermi_energy": 100.0}),
    ],
)
def test_zero_start_mass_selects_no_carrier_branch(
    client: TestClient, algorithm: str, model: str, mode: str, start: dict[str, float]
) -> None:
    result = _result(client, _body(model, mode, start=start) | {"algorithm": algorithm})

    assert result["status"] == "failed"
    # The legacy Seebeck-only SPB fit has no branch check, so the solver reports the zero mass.
    assert result["message"] == (
        "The fit started from a zero band mass, which has no finite chemical potential."
        if (model, algorithm) == ("spb", "legacy-sequential-v1")
        else "The start values do not fit the bounds."
    )
    assert result["parameters"] == start


def test_uncertified_chemical_potential_has_a_distinct_fit_message(client: TestClient) -> None:
    start = {"m_eff": 1.01, "band_gap": 1000.0, "fermi_energy": 0.0}
    result = _result(
        client,
        _body(
            start=start,
            min_temperature_k=0.01,
            max_temperature_k=0.03,
            measurements={"seebeck": {"temperature_k": [0.01, 0.02, 0.03], "values": [2.0e-4] * 3}},
        ),
    )

    assert result["status"] == "failed"
    assert (
        result["message"] == "The chemical-potential balance could not be verified during the fit."
    )
    assert result["parameters"] == start


def test_valid_start_recovers_from_no_root_optimizer_trials(client: TestClient) -> None:
    # The historical SiP fit has a valid start and optimum, but TRF probes E_F <= 0.
    fixture = (
        Path(__file__).resolve().parents[3]
        / "packages/seeband_core/tests/fixtures/golden/02_SiP.json"
    )
    document = json.loads(fixture.read_text())
    run = next(run for run in document["runs"] if run["mode"] == "spb_s")
    call = run["calls"][0]
    temperature, seebeck, mass, start, bounds = call["args"]
    result = _result(
        client,
        _body(
            "spb",
            "spb_s",
            start={"band_mass": mass, "fermi_energy": start[0]},
            bounds={"fermi_energy": {"lower": bounds[0][0], "upper": bounds[1][0]}},
            min_temperature_k=min(temperature),
            max_temperature_k=max(temperature),
            measurements={"seebeck": {"temperature_k": temperature, "values": seebeck}},
        ),
    )

    assert result["status"] == "converged"
    assert "message" not in result
    assert result["parameters"]["fermi_energy"] == pytest.approx(call["result"][0], rel=1e-4)


def test_degeneracies_reach_the_fit(client: TestClient) -> None:
    expected = _core_fit(
        "dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=2.0, band_2_degeneracy=3.0
    )

    body = _result(
        client,
        _body("dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=2.0, band_2_degeneracy=3.0),
    )

    assert body["parameters"] == expected.parameters
    assert body["algorithm"] == "verified-sequential-v2"
    assert "dpb_loop_degeneracy" not in body["known_issues"]


def test_fractional_degeneracies_reach_the_fit(client: TestClient) -> None:
    expected = _core_fit(
        "dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=1.5, band_2_degeneracy=2.5
    )

    body = _result(
        client,
        _body("dpb", "dpb_s_rho", scattering="acPh", band_1_degeneracy=1.5, band_2_degeneracy=2.5),
    )

    assert body["parameters"] == expected.parameters


def test_extrapolated_data_is_flagged(client: TestClient) -> None:
    plain = _result(client, _body())
    flagged = _result(client, _body(extrapolated=True))

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

    body = _result(client, _body(min_temperature_k=low, max_temperature_k=high))

    assert body["parameters"] == expected.parameters


def test_spb_hall_mode_validates_measurements_instead_of_refusing_mode(client: TestClient) -> None:
    response = client.post(
        "/api/fit", json=_body("spb", "spb_s_rho_rh", scattering="acPh") | {"measurements": {}}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fit"
    assert {tuple(location) for location, _ in _details(response)} == {
        ("body", "measurements", quantity) for quantity in ("seebeck", "resistivity", "hall")
    }


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"model": "nope"}, [(["body", "model"], "unknown_model")]),
        ({"fit_mode": "nope"}, [(["body", "fit_mode"], "unknown_fit_mode")]),
        ({"scattering": "nope"}, [(["body", "scattering"], "unknown_scattering")]),
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


def test_held_parameters_reach_the_fit_and_come_back_as_sent(client: TestClient) -> None:
    start = default_start(_mode("dpb", "dpb_s_rho"))
    expected = _core_fit("dpb", "dpb_s_rho", scattering="acPh", held=frozenset({"band_gap", "A"}))

    body = _result(client, _body("dpb", "dpb_s_rho", scattering="acPh", held=["band_gap", "A"]))

    assert body["parameters"] == expected.parameters
    assert body["parameters"]["band_gap"] == start["band_gap"]
    assert body["parameters"]["A"] == start["A"]
    assert body["held"] == ["A", "band_gap"]
    assert "band_gap" not in body["parameter_errors"]


def test_a_fit_with_nothing_held_says_so(client: TestClient) -> None:
    assert _result(client, _body())["held"] == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        # SPB S does not fit the mass, and F belongs to dis.
        (
            {"model": "spb", "fit_mode": "spb_s", "start": default_start(_mode("spb", "spb_s"))}
            | {"held": ["band_mass"]},
            [(["body", "held", "band_mass"], "parameter_not_fitted")],
        ),
        (
            {"fit_mode": "dpb_s_rho", "scattering": "acPh", "held": ["F"]}
            | {"start": default_start(_mode("dpb", "dpb_s_rho"))},
            [(["body", "held", "F"], "parameter_not_fitted")],
        ),
        (
            {"held": ["m_eff", "band_gap", "fermi_energy"]},
            [(["body", "held"], "nothing_to_fit")],
        ),
    ],
)
def test_holding_what_the_fit_does_not_find_or_everything_is_refused(
    client: TestClient, changes: dict[str, Any], expected: list[tuple[list[str | int], str]]
) -> None:
    body = _body(**changes)
    mode = _mode(body["model"], body["fit_mode"])
    body["measurements"] = {quantity: DEMO_INPUT[quantity] for quantity in mode.quantities}

    response = client.post("/api/fit", json=body)

    assert response.status_code == 422
    assert _details(response) == expected


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
        {"min_temperature_k": 100.0, "max_temperature_k": 100.0},
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
        # This fills the only place, without timing a fit against the request below.
        client.app.state.fit_runner._admitted = 1

        response = client.post("/api/fit", json=_body())

        client.app.state.fit_runner._admitted = 0

    assert response.status_code == 429
    assert response.json()["code"] == "fit_queue_full"
    assert response.headers["retry-after"] == "5"
    assert response.headers["content-type"] == "application/json"


def test_contract_declares_the_retry_hint() -> None:
    contract = create_app().openapi()
    answer = contract["paths"]["/api/fit"]["post"]["responses"]["429"]

    assert "Retry-After" in answer["headers"]


def test_contract_has_a_stream_for_the_200_and_json_for_errors() -> None:
    responses = create_app().openapi()["paths"]["/api/fit"]["post"]["responses"]

    assert list(responses["200"]["content"]) == ["text/event-stream"]
    assert list(responses["429"]["content"]) == ["application/json"]
    assert list(responses["default"]["content"]) == ["application/json"]


@pytest.mark.parametrize("name", sorted(_STREAM_EXAMPLES))
def test_stream_examples_fit_the_schema_of_the_events(name: str) -> None:
    contract = create_app().openapi()
    media = contract["paths"]["/api/fit"]["post"]["responses"]["200"]["content"][
        "text/event-stream"
    ]
    schema = media["itemSchema"]["properties"]["data"]["contentSchema"]
    validator = Draft202012Validator({**schema, "components": contract["components"]})

    events = list(read_events(iter(media["examples"][name]["value"].splitlines())))

    assert events[0] == {"type": "started"}
    assert events[-1]["type"] in ("done", "error")
    for event in events:
        validator.validate(event)
    if events[-1]["type"] == "error":
        assert events[-1]["error"]["code"] == name
        ErrorResponse.model_validate(events[-1]["error"])


def test_stopping_the_app_closes_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = []
    with TestClient(create_app()) as client:
        monkeypatch.setattr(client.app.state.fit_runner, "close", lambda: closed.append(True))

    assert closed == [True]


def test_value_that_is_not_finite_comes_back_as_null() -> None:
    result = FitResult({"m_eff": math.nan, "band_gap": 5.0}, "converged")

    assert _to_response(result).parameters == {"m_eff": None, "band_gap": 5.0}


def test_unexpected_failure_of_a_task_is_an_event_without_its_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_app()

    async def fails() -> FitResult:
        raise RuntimeError("SECRET-VALUE")

    async def main() -> Any:
        task = asyncio.create_task(fails())
        await asyncio.wait([task])
        return _last_event(task)

    event = asyncio.run(main())

    assert event.type == "error"
    assert event.error.code == "internal_error"
    assert "SECRET-VALUE" not in event.model_dump_json()
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "SECRET-VALUE" not in captured.err


def test_settings_reach_the_runner() -> None:
    settings = Settings(fit_max_running=3, fit_max_waiting=7, fit_timeout_s=9.0)
    with TestClient(create_app(settings)) as client:
        runner = client.app.state.fit_runner

    assert (runner._semaphore._value, runner._max_admitted, runner._timeout_s) == (3, 10, 9.0)


def test_process_past_the_time_limit_ends_the_stream_with_an_error() -> None:
    settings = Settings(fit_timeout_s=0.001)
    with TestClient(create_app(settings)) as client:
        events = _events(client, _body())

    assert events == [
        {"type": "started"},
        {
            "type": "error",
            "error": {"code": "fit_timeout", "message": "The fit took too long", "details": []},
        },
    ]


def test_examples_in_the_contract_fit_their_schemas() -> None:
    request = FitApiRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]
    response = FitResponse.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    FitApiRequest.model_validate(request)
    FitResponse.model_validate(response)
    assert set(request["start"]) == set(default_start(_mode("dpb", "dpb_s")))


def test_example_request_is_a_fit_the_api_accepts(client: TestClient) -> None:
    request = FitApiRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    assert set(_result(client, request)["parameters"]) == set(request["start"])


def test_algorithm_defaults_to_verified_and_rejects_unknown() -> None:
    body = _body("spb", "spb_s")
    assert FitApiRequest.model_validate(body).algorithm == "verified-sequential-v2"
    assert (
        FitApiRequest.model_validate(body | {"algorithm": "legacy-sequential-v1"}).algorithm
        == "legacy-sequential-v1"
    )
    with pytest.raises(ValueError):
        FitApiRequest.model_validate(body | {"algorithm": "unknown"})


def test_algorithm_reaches_core_request() -> None:
    from seeband_api.fit import _to_core_request

    for algorithm in ("verified-sequential-v2", "legacy-sequential-v1"):
        _, request = _to_core_request(
            FitApiRequest.model_validate(_body("spb", "spb_s", algorithm=algorithm)), 10000
        )
        assert request.algorithm == algorithm


def test_verified_metadata_survives_the_done_event() -> None:
    from seeband_core.model_interface import FitDiagnostics, ResidualDiagnostics

    diagnostics = FitDiagnostics(
        termination="cycle",
        stage_consistent=False,
        objectives={"seebeck": 0.25},
        optimality={"seebeck": 0.1},
        evaluations=12,
        recoveries=1,
        residuals={"seebeck": ResidualDiagnostics(0.5, None, "V/K")},
        unidentified=("m_eff",),
    )
    result = FitResult({}, "stalled", algorithm="verified-sequential-v2", diagnostics=diagnostics)

    async def main() -> Any:
        async def completed() -> FitResult:
            return result

        task = asyncio.create_task(completed())
        await task
        return _last_event(task)

    event = asyncio.run(main())
    payload = json.loads(event.model_dump_json())
    assert payload["type"] == "done"
    assert payload["result"]["algorithm"] == "verified-sequential-v2"
    assert payload["result"]["status"] == "stalled"
    assert payload["result"]["diagnostics"]["residuals"]["seebeck"] == {
        "rmse": 0.5,
        "relative_l2": None,
        "unit": "V/K",
    }
    assert payload["result"]["diagnostics"]["uncertainty"] == "not_assessed"
    assert payload["result"]["diagnostics"]["residual_adequacy"] == "not_assessed"


def test_unknown_algorithm_is_refused_before_the_stream(client: TestClient) -> None:
    response = client.post("/api/fit", json=_body("spb", "spb_s", algorithm="unknown"))
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("algorithm", ["verified-sequential-v2", "legacy-sequential-v1"])
def test_stream_reports_selected_algorithm(client: TestClient, algorithm: str) -> None:
    result = _result(client, _body("spb", "spb_s", algorithm=algorithm))
    assert result["algorithm"] == algorithm
    if algorithm == "verified-sequential-v2":
        assert result["diagnostics"]["uncertainty"] == "not_assessed"
    else:
        assert "diagnostics" not in result


def test_legacy_response_retains_the_historical_degeneracy_flag() -> None:
    result = FitResult(
        {"m_eff": 3.0},
        "converged",
        known_issues=("dpb_loop_degeneracy",),
        algorithm="legacy-sequential-v1",
    )
    response = _to_response(result)
    assert response.algorithm == "legacy-sequential-v1"
    assert "dpb_loop_degeneracy" in response.known_issues


def test_a_fit_error_event_gives_at_most_50_details() -> None:
    from seeband_api.errors import ApiError, ErrorDetail

    details = [ErrorDetail(location=["body", index], code="x", message="x") for index in range(60)]

    async def failing() -> Any:
        raise ApiError(422, "invalid_fit", "Invalid", details)

    async def last() -> Any:
        task = asyncio.ensure_future(failing())
        await asyncio.wait([task])
        return _last_event(task)

    event = asyncio.run(last())

    assert len(event.error.details) == 50
    assert event.error.details_omitted == 10
    assert '"details_omitted":10' in event.model_dump_json(exclude_none=True)
