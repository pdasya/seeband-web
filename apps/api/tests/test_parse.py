from collections.abc import Iterator
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_api.parse import MAX_TEXT_CHARACTERS, ParseRequest, ParseResponse
from seeband_core.data_parser import IssueCode, parse_table
from seeband_core.interpolation import interpolate
from seeband_core.model_interface import Measurement

EXAMPLES = (
    Path(__file__).parents[3] / "packages" / "seeband_core" / "tests" / "fixtures" / "examples"
)
SIX_ROWS = "T S\n100 1e-6\n200 2e-6\n300 3e-6\n400 4e-6\n500 5e-6\n600 6e-6\n"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _parse(client: TestClient, text: str, **fields: Any) -> dict[str, Any]:
    response = client.post("/api/parse", json={"text": text, **fields})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_returns_points_range_and_mapping(client: TestClient) -> None:
    body = _parse(client, SIX_ROWS)

    assert body["headers"] == ["T", "S"]
    assert body["column_count"] == 2
    assert body["row_count"] == 6
    assert body["mapping"] == [
        {"column": 0, "role": "temperature"},
        {"column": 1, "role": "seebeck"},
    ]
    assert body["measurements"] == {
        "seebeck": {
            "temperature_k": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
            "values": [1e-6, 2e-6, 3e-6, 4e-6, 5e-6, 6e-6],
            "points": 6,
            "min_temperature_k": 100.0,
            "max_temperature_k": 600.0,
        }
    }
    assert body["errors"] == []
    assert body["warnings"] == []
    assert body["interpolated"] == {}
    assert body["interpolation_failed"] == []


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.txt")), ids=lambda path: path.name)
def test_every_example_file_equals_the_core(client: TestClient, path: Path) -> None:
    quantities = {"see": "seebeck", "rho": "resistivity", "hall": "hall"}
    expected = quantities[path.stem.rsplit("_", 1)[1]]
    text = path.read_text(encoding="utf-8")
    core = parse_table(text, expected)  # type: ignore[arg-type]

    body = _parse(client, text, expected=expected)

    assert body["errors"] == []
    [(quantity, measurement)] = body["measurements"].items()
    assert quantity == expected
    assert measurement["temperature_k"] == core.measurements[expected].temperature_k.tolist()  # type: ignore[index]
    assert measurement["values"] == core.measurements[expected].values.tolist()  # type: ignore[index]
    assert measurement["points"] == len(core.lines)


def test_preview_keeps_the_order_of_the_text_and_is_short(client: TestClient) -> None:
    rows = [f"{500 - row} {row}" for row in range(30)]

    body = _parse(client, "T S\n" + "\n".join(rows))

    assert body["row_count"] == 30
    assert body["preview"] == [[500.0 - row, float(row)] for row in range(10)]
    assert body["measurements"]["seebeck"]["temperature_k"][0] == 471.0


def test_file_with_errors_keeps_its_preview_and_has_no_measurements(client: TestClient) -> None:
    body = _parse(client, "T S\n100 1e-6\n200 x\n300 3e-6\n")

    assert body["errors"] == [{"code": "not_numeric", "line": 3, "column": 1}]
    assert body["measurements"] == {}
    assert body["preview"] == [[100.0, 1e-6], [300.0, 3e-6]]


ERROR_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("no_data", {}, ""),
    ("line_too_long", {}, "100 1\n" + "1" * 2001 + " 2\n"),
    ("too_many_problems", {}, "100 1\n" + "200 x\n" * 60),
    ("too_few_columns", {}, "100 1\n200\n"),
    ("wrong_column_count", {}, "100 1\n200 2 3\n"),
    ("missing_value", {}, "100,,1\n200,2,1\n"),
    ("not_numeric", {}, "100 1\n200 nan\n"),
    ("not_finite", {}, "100 1\n200 1e999\n"),
    ("decimal_comma", {}, "300,5 1,2\n"),
    ("too_few_rows", {}, "100 1\n"),
    ("missing_temperature", {"mapping": [{"column": 1, "role": "seebeck"}]}, SIX_ROWS),
    ("non_positive_temperature", {}, "T S\n0 1\n100 2\n"),
    (
        "repeated_role",
        {
            "mapping": [
                {"column": 0, "role": "temperature"},
                {"column": 1, "role": "temperature"},
            ]
        },
        SIX_ROWS,
    ),
]
WARNING_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("preamble_skipped", {}, "A title\nT S\n100 1\n200 2\n"),
    (
        "header_mismatch",
        {"mapping": [{"column": 0, "role": "temperature"}, {"column": 1, "role": "seebeck"}]},
        "T S rho\n100 1\n200 2\n",
    ),
    ("unit_differs", {}, "T (K)\tS (uV/K)\n100\t1\n200\t2\n"),
    ("repeated_header", {}, "T S S\n100 1 2\n200 2 3\n"),
    ("columns_need_assigning", {}, "100 1 2\n200 2 3\n"),
    ("expected_not_found", {"expected": "hall"}, SIX_ROWS),
    ("no_quantity", {"mapping": [{"column": 0, "role": "temperature"}]}, SIX_ROWS),
    ("few_rows", {}, "T S\n100 1\n200 2\n"),
    ("unsorted_temperature", {}, "T S\n200 2\n100 1\n"),
    ("duplicate_temperature", {}, "T S\n100 2\n100 1\n"),
]


def test_cases_cover_every_code_of_the_parser() -> None:
    covered = {code for code, _, _ in ERROR_CASES + WARNING_CASES}

    assert covered == set(get_args(IssueCode))


@pytest.mark.parametrize(("code", "fields", "text"), ERROR_CASES, ids=[c[0] for c in ERROR_CASES])
def test_each_error_code_reaches_the_client(
    client: TestClient, code: str, fields: dict[str, Any], text: str
) -> None:
    body = _parse(client, text, **fields)

    assert code in [issue["code"] for issue in body["errors"]]
    assert body["measurements"] == {}


@pytest.mark.parametrize(
    ("code", "fields", "text"), WARNING_CASES, ids=[c[0] for c in WARNING_CASES]
)
def test_each_warning_code_reaches_the_client(
    client: TestClient, code: str, fields: dict[str, Any], text: str
) -> None:
    body = _parse(client, text, **fields)

    assert code in [issue["code"] for issue in body["warnings"]]
    assert body["errors"] == []


def test_a_user_can_assign_columns(client: TestClient) -> None:
    text = "100 1 7\n200 2 8\n"
    first = _parse(client, text)
    assert first["mapping"] == [{"column": 0, "role": "temperature"}]
    assert first["measurements"] == {}

    second = _parse(
        client,
        text,
        mapping=[
            {"column": 0, "role": "temperature"},
            {"column": 2, "role": "resistivity"},
        ],
    )

    assert second["measurements"]["resistivity"]["values"] == [7.0, 8.0]
    assert "seebeck" not in second["measurements"]


def test_expected_names_the_second_column(client: TestClient) -> None:
    assert list(_parse(client, "100 1\n200 2\n", expected="hall")["measurements"]) == ["hall"]


def test_many_warnings_are_cut_and_counted(client: TestClient) -> None:
    body = _parse(client, "text here\n" * 150 + "T S\n100 1\n200 2\n")

    assert len(body["warnings"]) == 100
    assert body["warnings_omitted"] == 150 + 1 - 100


def test_interpolation_equals_the_core_and_keeps_the_originals(client: TestClient) -> None:
    path = EXAMPLES / "01_Fe2VAl09Si01_see.txt"
    text = path.read_text(encoding="utf-8")
    core = parse_table(text, "seebeck").measurements["seebeck"]
    expected = interpolate(core, 50.0, 800.0)

    body = _parse(
        client,
        text,
        expected="seebeck",
        interpolate={"min_temperature_k": 50.0, "max_temperature_k": 800.0},
    )

    assert body["measurements"]["seebeck"]["temperature_k"] == core.temperature_k.tolist()
    data = body["interpolated"]["seebeck"]
    assert data["temperature_k"] == expected.measurement.temperature_k.tolist()
    assert data["values"] == expected.measurement.values.tolist()
    assert len(data["values"]) == 37
    assert data["extrapolated"] is expected.extrapolated
    assert data["extrapolated"] is True
    assert data["measured_points_in_range"] == expected.measured_points_in_range
    assert data["underdetermined"] is False
    assert body["interpolation_failed"] == []


def test_interpolation_reports_data_that_do_not_set_the_polynomial(client: TestClient) -> None:
    body = _parse(
        client, SIX_ROWS, interpolate={"min_temperature_k": 100.0, "max_temperature_k": 600.0}
    )

    assert body["interpolated"]["seebeck"]["underdetermined"] is True
    assert body["interpolated"]["seebeck"]["extrapolated"] is False


def test_one_quantity_failing_leaves_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    from seeband_api import parse_worker

    calls = []

    def fail_on_rho(measurement: Measurement, low: float, high: float) -> Any:
        calls.append(float(measurement.values[0]))
        if measurement.values[0] == 7.0:
            raise ValueError("The data could not be fitted")
        return interpolate(measurement, low, high)

    monkeypatch.setattr(parse_worker, "interpolate", fail_on_rho)
    outcome = parse_worker.parse(
        "T S rho\n100 1 7\n200 2 8\n300 3 9\n",
        None,
        None,
        parse_worker.FitRange(100.0, 300.0),
    )

    assert list(outcome.interpolated) == ["seebeck"]
    assert outcome.interpolation_failed == ("resistivity",)
    assert calls == [1.0, 7.0]


def test_errors_mean_no_interpolation(client: TestClient) -> None:
    body = _parse(
        client, "100 x\n", interpolate={"min_temperature_k": 100.0, "max_temperature_k": 600.0}
    )

    assert body["interpolated"] == {}


@pytest.mark.parametrize(
    "limits",
    [(100.0, 110.0), (1.0, 1e7)],
    ids=["under 20 K", "over 200000 K"],
)
def test_range_the_grid_cannot_use_is_refused(
    client: TestClient, limits: tuple[float, float]
) -> None:
    response = client.post(
        "/api/parse",
        json={
            "text": SIX_ROWS,
            "interpolate": {"min_temperature_k": limits[0], "max_temperature_k": limits[1]},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_parse_request"
    assert response.json()["details"][0]["code"] == "invalid_interpolation_range"
    assert response.json()["details"][0]["location"] == ["body", "interpolate"]


def test_unknown_column_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        json={"text": SIX_ROWS, "mapping": [{"column": 5, "role": "seebeck"}]},
    )

    assert response.status_code == 422
    assert response.json()["details"] == [
        {
            "location": ["body", "mapping"],
            "code": "unknown_column",
            "message": "The text has no such column",
        }
    ]


@pytest.mark.parametrize(
    "fields",
    [
        {"text": "x" * (MAX_TEXT_CHARACTERS + 1)},
        {"text": 5},
        {"text": SIX_ROWS, "expected": "nope"},
        {"text": SIX_ROWS, "mapping": [{"column": -1, "role": "seebeck"}]},
        {"text": SIX_ROWS, "mapping": [{"column": "0", "role": "seebeck"}]},
        {"text": SIX_ROWS, "mapping": [{"column": 0, "role": "nope"}]},
        {
            "text": SIX_ROWS,
            "mapping": [{"column": 0, "role": "seebeck"}, {"column": 0, "role": "hall"}],
        },
        {"text": SIX_ROWS, "interpolate": {"min_temperature_k": 0.0, "max_temperature_k": 100.0}},
        {"text": SIX_ROWS, "interpolate": {"min_temperature_k": 200.0, "max_temperature_k": 100.0}},
        {"text": SIX_ROWS, "interpolate": {"min_temperature_k": "100", "max_temperature_k": 200.0}},
    ],
)
def test_invalid_requests_are_refused(client: TestClient, fields: dict[str, Any]) -> None:
    response = client.post("/api/parse", json=fields)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_longest_text_allowed_is_read(client: TestClient) -> None:
    rows = "100 1\n" * (MAX_TEXT_CHARACTERS // 6)

    response = client.post("/api/parse", json={"text": rows})

    assert response.status_code == 200


def test_lone_surrogate_in_the_text_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        content='{"text": "T S\\ud800\\n1 2\\n"}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_calls_keep_no_state(client: TestClient) -> None:
    first = _parse(client, SIX_ROWS)

    _parse(client, "T rho\n1 1\n2 2\n")

    assert _parse(client, SIX_ROWS) == first


def test_examples_in_the_contract_are_what_the_api_answers(client: TestClient) -> None:
    request = ParseRequest.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]
    example = ParseResponse.model_config["json_schema_extra"]["examples"][0]  # type: ignore[index]

    assert client.post("/api/parse", json=request).json() == example
