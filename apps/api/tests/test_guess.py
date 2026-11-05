import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pool_functions
import pytest
from fastapi.testclient import TestClient
from seeband_api import guess_worker
from seeband_api.calc_worker import CalculationFailed
from seeband_api.errors import ERROR_EXAMPLES
from seeband_api.guess import REQUEST_EXAMPLE, RESPONSE_EXAMPLES
from seeband_api.main import create_app
from seeband_api.settings import Settings
from seeband_core import data_processing, neural_nets
from seeband_core.model_catalog import registry
from seeband_core.model_scales import core_range, default_start

FIXTURE = (
    Path(__file__).parents[3]
    / "packages"
    / "seeband_core"
    / "tests"
    / "fixtures"
    / "neural_net_references.json"
)
CASES: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
SELECTED = [case for case in CASES if case["selected_range_k"] is not None]
NO_NET = [case for case in CASES if case["selected_range_k"] is None]
DPB = registry.get("dpb").describe()
# Written by hand from the desktop's recorded values, so that a change to the fixture fails here.
# case: (range, m_eff, band gap in K, Fermi energy in K)
EXPECTED_START_VALUES = {
    "01_Fe2VAl09Si01": ((400.0, 700.0), 1.57, 554.0, 1170.0),
    "03_AWI32_SI": ((200.0, 500.0), 1.22, 1947.0, -350.0),
    "03_negated_seebeck": ((200.0, 500.0), 0.82, 1947.0, 2298.0),
    "synthetic_300_800": ((300.0, 800.0), 3.0, 3000.0, -763.0),
    "synthetic_400_700": ((400.0, 700.0), 3.0, 3000.0, -1041.0),
    "synthetic_300_600": ((300.0, 600.0), 3.0, 2593.0, -1086.0),
    "synthetic_200_500": ((200.0, 500.0), 3.0, 699.0, -953.0),
    "synthetic_100_400": ((100.0, 400.0), 2.08, -3.0, -651.0),
}
EVERY_NET = [
    {"min_temperature_k": 300.0, "max_temperature_k": 800.0},
    {"min_temperature_k": 400.0, "max_temperature_k": 700.0},
    {"min_temperature_k": 300.0, "max_temperature_k": 600.0},
    {"min_temperature_k": 200.0, "max_temperature_k": 500.0},
    {"min_temperature_k": 100.0, "max_temperature_k": 400.0},
]
SPANNING_30_ROWS = np.linspace(100.0, 800.0, 30).tolist()
# A constant Seebeck of this size gives a finite prediction from any of these temperatures.
MILD_V_PER_K = 1e-4


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _post(client: TestClient, temperature_k: list[float], seebeck_v_per_k: list[float]) -> Any:
    return client.post(
        "/api/guess",
        json={"model": "dpb", "temperature_k": temperature_k, "seebeck_v_per_k": seebeck_v_per_k},
    )


def _mild(temperature_k: list[float]) -> list[float]:
    return [MILD_V_PER_K for _ in temperature_k]


def _start_values(case: dict[str, Any]) -> dict[str, float]:
    start = case["desktop_start_values"]
    return {
        "m_eff": start["m_eff"],
        "band_gap": start["band_gap_k"],
        "fermi_energy": start["fermi_energy_k"],
    }


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_guess_is_exactly_that_of_the_core_and_starts_as_on_the_desktop(
    client: TestClient, case: dict[str, Any]
) -> None:
    expected = neural_nets.predict_band_parameters(
        np.array(case["temperature_k"]), np.array(case["seebeck_v_per_k"])
    )
    assert isinstance(expected, neural_nets.NeuralNetGuess)

    response = _post(client, case["temperature_k"], case["seebeck_v_per_k"])

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "net_range", "prediction", "start_values", "warnings"}
    assert body["status"] == "guess"
    assert body["prediction"] == {
        "m_eff": expected.m_eff,
        "band_gap_k": expected.band_gap_k,
        "fermi_energy_k": expected.fermi_energy_k,
    }
    # The desktop's own prediction, and its sliders' values, exactly.
    low_k, high_k = case["selected_range_k"]
    assert body["net_range"] == {"min_temperature_k": low_k, "max_temperature_k": high_k}
    assert body["start_values"] == _start_values(case)
    for key, value in case["prediction"].items():
        assert body["prediction"][key] == pytest.approx(value, rel=1e-12)
    assert body["warnings"] == []


@pytest.mark.parametrize("case", NO_NET, ids=lambda case: case["name"])
def test_no_net_is_an_answer_with_its_reason(client: TestClient, case: dict[str, Any]) -> None:
    response = _post(client, case["temperature_k"], case["seebeck_v_per_k"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_net"
    assert body["reason"] == "temperature_span"
    assert body["first_temperature_k"] == case["temperature_k"][0]
    assert body["last_temperature_k"] == case["temperature_k"][-1]
    assert body["available_ranges"] == EVERY_NET
    assert not {"net_range", "prediction", "start_values"} & set(body)


def test_every_selected_case_has_values_written_by_hand() -> None:
    assert {case["name"] for case in SELECTED} == set(EXPECTED_START_VALUES)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_values_match_those_written_by_hand(client: TestClient, case: dict[str, Any]) -> None:
    body = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()

    (low_k, high_k), m_eff, band_gap, fermi_energy = EXPECTED_START_VALUES[case["name"]]
    assert body["net_range"] == {"min_temperature_k": low_k, "max_temperature_k": high_k}
    assert body["start_values"] == {
        "m_eff": m_eff,
        "band_gap": band_gap,
        "fermi_energy": fermi_energy,
    }


def test_prediction_keeps_what_the_controls_limit(client: TestClient) -> None:
    case = next(case for case in CASES if case["name"] == "synthetic_300_800")

    body = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()

    assert body["prediction"]["band_gap_k"] == pytest.approx(52464, rel=1e-3)
    assert body["start_values"]["band_gap"] == 3000.0
    assert body["prediction"]["m_eff"] > 3.0
    assert body["start_values"]["m_eff"] == 3.0


@pytest.mark.parametrize(
    ("first_k", "last_k", "expected_k"),
    [
        (300.0, 800.0, (300.0, 800.0)),
        (300.0, 799.0, (400.0, 700.0)),
        (301.0, 800.0, (400.0, 700.0)),
        (200.0, 650.0, (300.0, 600.0)),
        (200.0, 599.0, (200.0, 500.0)),
        (100.0, 499.0, (100.0, 400.0)),
    ],
)
def test_choice_of_net_through_the_route(
    client: TestClient, first_k: float, last_k: float, expected_k: tuple[float, float]
) -> None:
    temperature_k = np.linspace(first_k, last_k, 12).tolist()

    body = _post(client, temperature_k, _mild(temperature_k)).json()

    assert (body["net_range"]["min_temperature_k"], body["net_range"]["max_temperature_k"]) == (
        expected_k
    )


@pytest.mark.parametrize(
    ("first_k", "last_k"), [(101.0, 400.0), (100.0, 399.0), (450.0, 800.0), (401.0, 699.0)]
)
def test_span_just_short_of_every_net_has_no_net(
    client: TestClient, first_k: float, last_k: float
) -> None:
    temperature_k = np.linspace(first_k, last_k, 12).tolist()

    body = _post(client, temperature_k, _mild(temperature_k)).json()

    assert body["status"] == "no_net"


# A prediction that is not finite is reachable with real sizes of Seebeck: 1 mV/K is enough.
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize("seebeck_v_per_k", [1e-3, -1e-3, 1.0, -1.0, 1e300])
def test_prediction_that_is_not_finite_has_its_own_state(
    client: TestClient, seebeck_v_per_k: float
) -> None:
    core = neural_nets.predict_band_parameters(
        np.array(SPANNING_30_ROWS), np.full(30, seebeck_v_per_k)
    )
    assert isinstance(core, neural_nets.NeuralNetGuess)
    assert not np.isfinite([core.m_eff, core.band_gap_k, core.fermi_energy_k]).all()

    response = _post(client, SPANNING_30_ROWS, [seebeck_v_per_k] * 30)

    assert response.status_code == 200
    body = json.loads(response.text, parse_constant=pytest.fail)
    assert body == {
        "status": "not_finite",
        "net_range": {"min_temperature_k": 300.0, "max_temperature_k": 800.0},
        "warnings": [],
    }


def test_one_row_has_no_net(client: TestClient) -> None:
    body = _post(client, [300.0], [1e-4]).json()

    assert body["status"] == "no_net"
    assert (body["first_temperature_k"], body["last_temperature_k"]) == (300.0, 300.0)
    assert body["warnings"] == []


@pytest.mark.parametrize(
    ("temperature_k", "underdetermined"),
    [
        ([100.0, 400.0], True),
        ([100.0, 200.0, 250.0, 300.0, 400.0], True),
        ([100.0, 200.0, 250.0, 300.0, 300.0, 400.0], True),
        ([100.0, 200.0, 250.0, 300.0, 350.0, 400.0], False),
    ],
)
def test_too_few_distinct_temperatures_are_flagged_and_still_answered(
    client: TestClient, temperature_k: list[float], underdetermined: bool
) -> None:
    seebeck_v_per_k = [1e-5 * value / 400.0 for value in temperature_k]

    body = _post(client, temperature_k, seebeck_v_per_k).json()

    assert body["net_range"] == {"min_temperature_k": 100.0, "max_temperature_k": 400.0}
    assert body["warnings"] == (["underdetermined_fit"] if underdetermined else [])


def test_too_few_rows_for_a_net_are_not_flagged_as_a_bad_fit(client: TestClient) -> None:
    assert _post(client, [450.0, 500.0], [1e-4, 1e-4]).json()["warnings"] == []


def test_order_of_rows_decides_the_net_as_on_the_desktop_and_is_flagged(
    client: TestClient,
) -> None:
    """P9 fixes this, and the parser sorts rows, so a client normally sends them sorted."""
    temperature_k = [100.0, 1000.0, 200.0, 300.0, 350.0, 500.0, 600.0, 400.0]

    body = _post(client, temperature_k, _mild(temperature_k)).json()

    assert body["net_range"] == {"min_temperature_k": 100.0, "max_temperature_k": 400.0}
    assert body["warnings"] == ["unsorted_temperature"]


def test_reversed_rows_get_no_net_and_the_flag(client: TestClient) -> None:
    case = next(case for case in CASES if case["name"] == "01_reversed_rows")

    body = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()

    assert body["status"] == "no_net"
    assert (body["first_temperature_k"], body["last_temperature_k"]) == (750.0, 25.0)
    assert body["warnings"] == ["unsorted_temperature"]


def test_flags_add_up(client: TestClient) -> None:
    body = _post(client, [100.0, 50.0, 400.0], [1e-6, 1e-6, 1e-6]).json()

    assert body["warnings"] == ["unsorted_temperature", "underdetermined_fit"]


def test_equal_temperatures_in_a_row_count_as_sorted(client: TestClient) -> None:
    temperature_k = [100.0, 150.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0]

    body = _post(client, temperature_k, _mild(temperature_k)).json()

    assert body["warnings"] == []


def test_order_of_middle_rows_changes_no_net_and_barely_any_value(client: TestClient) -> None:
    """The fit does not depend on the order, apart from rounding."""
    case = next(case for case in CASES if case["name"] == "01_Fe2VAl09Si01")
    order = [0, *range(28, 0, -1), 29]
    temperature_k = [case["temperature_k"][index] for index in order]
    seebeck = [case["seebeck_v_per_k"][index] for index in order]

    body = _post(client, temperature_k, seebeck).json()

    assert body["prediction"]["band_gap_k"] == pytest.approx(
        case["prediction"]["band_gap_k"], rel=1e-5
    )
    assert body["warnings"] == ["unsorted_temperature"]


def test_start_values_are_what_every_fit_mode_of_the_model_can_use(client: TestClient) -> None:
    assert DPB.has_initial_guess
    for case in SELECTED:
        body = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()
        for fit_mode in DPB.fit_modes:
            specs = {spec.name: spec for spec in fit_mode.parameters}
            for name, value in body["start_values"].items():
                limits = core_range(specs[name])
                assert limits.minimum <= value <= limits.maximum
                # So the issue's "display scale" and the core units are the same numbers here.
                assert specs[name].display_scale == specs[name].fit_scale


@pytest.mark.parametrize("fit_mode", DPB.fit_modes, ids=lambda fit_mode: fit_mode.id)
def test_start_values_go_straight_into_a_calculation(client: TestClient, fit_mode: Any) -> None:
    case = next(case for case in CASES if case["name"] == "01_Fe2VAl09Si01")
    start = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()["start_values"]

    response = client.post(
        "/api/calc",
        json={
            "model": "dpb",
            "fit_mode": fit_mode.id,
            "scattering": fit_mode.default_scattering,
            "parameters": default_start(fit_mode) | start,
            "min_temperature_k": 100.0,
            "max_temperature_k": 500.0,
            "points": 5,
        },
    )

    assert response.status_code == 200


def test_spb_is_refused_with_a_clear_error(client: TestClient) -> None:
    response = client.post(
        "/api/guess",
        json={"model": "spb", "temperature_k": SPANNING_30_ROWS, "seebeck_v_per_k": [1e-4] * 30},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "guess_unavailable",
        "message": "This model has no neural net guess",
        "details": [
            {
                "location": ["body", "model"],
                "code": "no_neural_net",
                "message": "See has_initial_guess in GET /api/models",
            }
        ],
    }
    assert response.json() == ERROR_EXAMPLES["guess_unavailable"]


def test_which_models_have_a_guess_is_in_their_descriptions(client: TestClient) -> None:
    models = client.get("/api/models").json()["models"]

    assert {model["id"]: model["has_initial_guess"] for model in models} == {
        "spb": False,
        "dpb": True,
    }


def test_unknown_model_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/guess", json={"model": "tpb", "temperature_k": [100.0], "seebeck_v_per_k": [1e-4]}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_calculation"
    assert response.json()["details"][0]["location"] == ["body", "model"]
    assert response.json()["details"][0]["code"] == "unknown_model"


@pytest.mark.parametrize(
    "changes",
    [
        {"temperature_k": []},
        {"seebeck_v_per_k": []},
        {"temperature_k": [100.0, 400.0]},
        {"temperature_k": [True]},
        {"seebeck_v_per_k": [True]},
        {"temperature_k": ["100.0"]},
        {"seebeck_v_per_k": ["1.5"]},
        {"temperature_k": [0.0]},
        {"temperature_k": [-100.0]},
        {"seebeck_v_per_k": [None]},
        {"model": None},
    ],
)
def test_request_that_breaks_the_contract_is_refused(
    client: TestClient, changes: dict[str, Any]
) -> None:
    body = {"model": "dpb", "temperature_k": [100.0], "seebeck_v_per_k": [1e-4]} | changes

    response = client.post("/api/guess", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_no_rows_at_all_are_refused(client: TestClient) -> None:
    response = _post(client, [], [])

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert [detail["location"] for detail in response.json()["details"]] == [
        ["body", "temperature_k"],
        ["body", "seebeck_v_per_k"],
    ]


@pytest.mark.parametrize("field", ["model", "temperature_k", "seebeck_v_per_k"])
def test_every_field_is_required(client: TestClient, field: str) -> None:
    body = {"model": "dpb", "temperature_k": [100.0], "seebeck_v_per_k": [1e-4]}
    del body[field]

    response = client.post("/api/guess", json=body)

    assert response.status_code == 422
    assert response.json()["details"][0]["location"] == ["body", field]


@pytest.mark.parametrize("field", ["temperature_k", "seebeck_v_per_k"])
@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_numbers_that_are_not_finite_are_refused(
    client: TestClient, field: str, number: str
) -> None:
    other = "seebeck_v_per_k" if field == "temperature_k" else "temperature_k"
    response = client.post(
        "/api/guess",
        content=f'{{"model": "dpb", "{field}": [{number}], "{other}": [100.0]}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_integers_are_numbers(client: TestClient) -> None:
    temperature_k = [100, 200, 250, 300, 350, 400]

    body = _post(client, temperature_k, [0] * 6).json()  # type: ignore[arg-type]

    assert body["net_range"] == {"min_temperature_k": 100.0, "max_temperature_k": 400.0}


def _worker_replaced_by(
    monkeypatch: pytest.MonkeyPatch, function: Any, settings: Settings | None = None
) -> TestClient:
    monkeypatch.setattr("seeband_api.guess.guess", function)
    return TestClient(create_app(settings))


def test_failed_fit_is_a_calculation_failure_in_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(data_processing, "fit_data", lambda _: None)

    with pytest.raises(CalculationFailed) as raised:
        guess_worker.guess("dpb", np.array([100.0, 400.0]), np.array([1e-4, 1e-4]))

    assert str(raised.value) == "ValueError"


def test_calculation_failure_answers_422_and_logs_only_its_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[logging.LogRecord] = []

    class Recorder(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    recorder = Recorder()
    logger = logging.getLogger("seeband_api")
    # Creating the app sets up the logger again, so this comes after.
    with _worker_replaced_by(monkeypatch, pool_functions.fail_a_guess) as test_client:
        logger.addHandler(recorder)
        try:
            response = _post(test_client, [100.0, 400.0], [1e-4, 1e-4])
        finally:
            logger.removeHandler(recorder)

    assert response.status_code == 422
    assert response.json()["code"] == "calculation_failed"
    [failure] = [record for record in records if record.getMessage() == "calculation_failed"]
    assert failure.__dict__["fields"] == {"exception_type": "ValueError"}


def test_slow_worker_answers_504(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(calc_timeout_s=0.2)
    with _worker_replaced_by(
        monkeypatch, pool_functions.sleep_through_a_guess, settings
    ) as test_client:
        response = _post(test_client, [100.0, 400.0], [1e-4, 1e-4])

    assert response.status_code == 504
    assert response.json()["code"] == "calculation_timeout"


def test_dead_worker_answers_503(monkeypatch: pytest.MonkeyPatch) -> None:
    with _worker_replaced_by(monkeypatch, pool_functions.die_during_a_guess) as test_client:
        response = _post(test_client, [100.0, 400.0], [1e-4, 1e-4])

    assert response.status_code == 503
    assert response.json()["code"] == "calculation_unavailable"


def test_guess_example_is_a_real_result_of_the_request_example(client: TestClient) -> None:
    body = client.post("/api/guess", json=REQUEST_EXAMPLE).json()

    example = RESPONSE_EXAMPLES["guess"]
    assert body["status"] == example["status"]
    assert body["net_range"] == example["net_range"]
    assert body["start_values"] == example["start_values"]
    assert body["warnings"] == example["warnings"]
    for key, value in example["prediction"].items():
        assert body["prediction"][key] == pytest.approx(value, rel=5e-4)


def test_no_net_example_is_a_real_result(client: TestClient) -> None:
    case = next(case for case in CASES if case["name"] == "02_SiP")

    body = _post(client, case["temperature_k"], case["seebeck_v_per_k"]).json()

    example = RESPONSE_EXAMPLES["no_net"]
    assert set(body) == set(example)
    assert body["first_temperature_k"] == pytest.approx(example["first_temperature_k"], rel=1e-3)
    assert body["last_temperature_k"] == example["last_temperature_k"]
    assert {key: body[key] for key in ("status", "reason", "available_ranges", "warnings")} == {
        key: example[key] for key in ("status", "reason", "available_ranges", "warnings")
    }


def test_not_finite_example_has_the_shape_of_a_real_result(client: TestClient) -> None:
    temperature_k = np.linspace(400.0, 700.0, 30).tolist()

    body = _post(client, temperature_k, [1.0] * 30).json()

    assert body == RESPONSE_EXAMPLES["not_finite"]


def test_contract_lists_the_route_with_its_three_answers() -> None:
    contract = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"

    operation = json.loads(contract.read_text(encoding="utf-8"))["paths"]["/api/guess"]["post"]

    assert operation["operationId"] == "post_guess"
    media = operation["responses"]["200"]["content"]["application/json"]
    assert set(media["examples"]) == {"guess", "no_net", "not_finite"}
    assert set(media["schema"]["discriminator"]["mapping"]) == {"guess", "no_net", "not_finite"}
    assert (
        "guess_unavailable"
        in (operation["responses"]["default"]["content"]["application/json"]["examples"])
    )
