from collections.abc import Iterator
from pathlib import Path
from typing import Any, get_args

import numpy as np
import pytest
from fastapi.testclient import TestClient
from seeband_api import parse_worker
from seeband_api.main import create_app
from seeband_api.parse import (
    MAX_TEXT_CHARACTERS,
    PARSE_EXAMPLE_REQUESTS,
    PARSE_EXAMPLE_RESPONSES,
    to_parse_response,
)
from seeband_api.parse_worker import ParseOutcome
from seeband_core.data_parser import IssueCode, parse_table
from seeband_core.interpolation import InterpolatedData, interpolate
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
        {"column": 0, "role": "temperature", "unit": "K"},
        {"column": 1, "role": "seebeck", "unit": "V/K"},
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


def test_a_value_decimal_cannot_hold_in_a_lab_unit_is_read_not_a_500(client: TestClient) -> None:
    body = _parse(client, "T (K)\tS (uV/K)\n100\t1e-99999999999999999999\n200\t50\n")

    assert body["errors"] == []
    assert body["measurements"]["seebeck"]["values"] == [0.0, 5e-5]
    assert body["preview_si"] == [[100.0, 0.0], [200.0, 5e-5]]


def test_file_with_errors_keeps_its_preview_and_has_no_measurements(client: TestClient) -> None:
    body = _parse(client, "T S\n100 1e-6\n200 x\n300 3e-6\n")

    assert body["errors"] == [{"code": "not_numeric", "line": 3, "column": 1}]
    assert body["measurements"] == {}
    assert body["preview"] == [[100.0, 1e-6], [300.0, 3e-6]]


ERROR_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("no_data", {}, ""),
    ("wrong_encoding", {}, "T\x00S\x00\nA\x00\n"),
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
    ("negative_resistivity", {"expected": "resistivity"}, "T rho\n100 -1e-5\n200 1e-5\n"),
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
    (
        "unit_not_allowed",
        {
            "mapping": [
                {"column": 0, "role": "temperature"},
                {"column": 1, "role": "seebeck", "unit": "cm^3/C"},
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
    ("unit_differs", {}, "T (K)\tS (mV/K)\n100\t1\n200\t2\n"),
    (
        "unit_assumed",
        {"mapping": [{"column": 0, "role": "temperature"}, {"column": 1, "role": "seebeck"}]},
        "T (K)\tS (mV/K)\n100\t1e-6\n200\t2e-6\n",
    ),
    ("implausible_magnitude", {}, "T S\n100 50\n200 60\n"),
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
    assert first["mapping"] == [{"column": 0, "role": "temperature", "unit": "K"}]
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


def test_a_unit_named_in_the_header_is_read_and_returned(client: TestClient) -> None:
    body = _parse(client, "T (K)\tS (uV/K)\n100\t50\n200\t80\n")

    assert body["mapping"][1] == {"column": 1, "role": "seebeck", "unit": "uV/K"}
    assert body["measurements"]["seebeck"]["values"] == pytest.approx([5e-5, 8e-5], rel=1e-15)
    assert body["preview"] == [[100.0, 50.0], [200.0, 80.0]]
    assert [row[0] for row in body["preview_si"]] == [100.0, 200.0]
    assert [row[1] for row in body["preview_si"]] == pytest.approx([5e-5, 8e-5], rel=1e-15)


def test_a_unit_a_user_chooses_converts_the_values(client: TestClient) -> None:
    mapping = [
        {"column": 0, "role": "temperature"},
        {"column": 1, "role": "resistivity", "unit": "mOhm*cm"},
    ]
    body = _parse(client, "100 0.4\n200 0.5\n", mapping=mapping)

    assert body["mapping"][1]["unit"] == "mOhm*cm"
    assert body["measurements"]["resistivity"]["values"] == pytest.approx([4e-6, 5e-6], rel=1e-15)
    assert body["warnings"] == [{"code": "few_rows"}]


def test_a_column_with_no_role_has_no_si_preview(client: TestClient) -> None:
    body = _parse(client, "100 1 7\n200 2 8\n")

    assert body["preview_si"] == [[100.0, None, None], [200.0, None, None]]


def test_microvolts_read_as_volts_are_called_implausible(client: TestClient) -> None:
    body = _parse(client, "T S\n100 50\n200 80\n")

    assert {"code": "implausible_magnitude", "column": 1} in body["warnings"]
    # Read as written: the warning only says that it looks wrong.
    assert body["measurements"]["seebeck"]["values"] == [50.0, 80.0]


def test_an_unknown_unit_is_refused_by_the_contract(client: TestClient) -> None:
    mapping = [
        {"column": 0, "role": "temperature"},
        {"column": 1, "role": "seebeck", "unit": "mV/K"},
    ]
    response = client.post("/api/parse", json={"text": SIX_ROWS, "mapping": mapping})

    assert response.status_code == 422


def test_expected_names_the_second_column(client: TestClient) -> None:
    assert list(_parse(client, "100 1\n200 2\n", expected="hall")["measurements"]) == ["hall"]


def test_many_preamble_warnings_are_cut_and_hide_nothing_else(client: TestClient) -> None:
    text = "x y\n" * 150 + "T (K)\tS (mV/K)\n300\t1\n100\t2\n100\t3\n"

    body = _parse(client, text, expected="seebeck")

    codes = [issue["code"] for issue in body["warnings"]]
    assert codes.count("preamble_skipped") == 100
    preamble_lines = [i["line"] for i in body["warnings"] if i["code"] == "preamble_skipped"]
    assert preamble_lines == list(range(1, 101))
    assert body["warnings_omitted"] == 150 - 100
    for code in ("unit_differs", "few_rows", "unsorted_temperature", "no_quantity"):
        assert code in codes, code
    assert "expected_not_found" in codes


def test_a_choice_of_columns_is_kept_while_rows_have_errors(client: TestClient) -> None:
    mapping = [{"column": 0, "role": "temperature"}, {"column": 2, "role": "hall"}]

    body = _parse(client, "T S rho\n100 1 2\n200 x 3\n300 3 4\n", mapping=mapping)

    assert body["mapping"] == mapping
    assert [issue["code"] for issue in body["errors"]] == ["not_numeric"]
    assert body["measurements"] == {}


def test_a_stale_expected_warning_goes_with_the_mapping_that_fixes_it(client: TestClient) -> None:
    mapping = [{"column": 0, "role": "temperature"}, {"column": 1, "role": "hall"}]

    body = _parse(client, "T S\n100 1\n200 x\n", expected="hall", mapping=mapping)

    assert "expected_not_found" not in [issue["code"] for issue in body["warnings"]]


def test_unknown_column_is_refused_while_rows_have_errors(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        json={"text": "T S\n100 1\n200 x\n", "mapping": [{"column": 9, "role": "seebeck"}]},
    )

    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "unknown_column"


def test_mapping_is_ignored_when_no_row_could_be_read(client: TestClient) -> None:
    body = _parse(client, "T S\n100 x\n", mapping=[{"column": 9, "role": "seebeck"}])

    assert body["errors"]
    assert body["mapping"] == []


@pytest.mark.parametrize(
    ("text", "column_count", "headers"),
    [
        ("T S\n100 1\n200 2\n", 2, ["T", "S"]),
        ("T S\n300,5 1,2\n400,5 1,3\n", 2, ["T", "S"]),
        ("T S\n1e999 1\n2e999 2\n", 2, ["T", "S"]),
        ("100 1 2\n200 x 3\n", 3, None),
        ("", 0, None),
    ],
)
def test_column_count_agrees_with_the_headers(
    client: TestClient, text: str, column_count: int, headers: list[str] | None
) -> None:
    body = _parse(client, text)

    assert body["column_count"] == column_count
    assert body.get("headers") == headers


def test_no_header_is_left_out_not_empty(client: TestClient) -> None:
    assert "headers" not in _parse(client, "100 1\n200 2\n", expected="seebeck")


@pytest.mark.parametrize(
    "text",
    [
        "T S\n100 1\n200 2\n".encode("utf-16").decode("utf-8", errors="replace"),
        "T S\n100 1\n200 2\n".encode("utf-16-le").decode("utf-8", errors="replace"),
    ],
    ids=["utf-16 with mark", "utf-16 without mark"],
)
def test_utf_16_read_as_utf_8_says_so(client: TestClient, text: str) -> None:
    body = _parse(client, text)

    assert [issue["code"] for issue in body["errors"]] == ["wrong_encoding"]


def test_several_quantities_are_read_and_interpolated(client: TestClient) -> None:
    text = "T S rho RH\n100 1 4 7\n200 2 5 8\n300 3 6 9\n"
    mapping_free = _parse(
        client, text, interpolate={"min_temperature_k": 100.0, "max_temperature_k": 300.0}
    )

    assert list(mapping_free["measurements"]) == ["seebeck", "resistivity", "hall"]
    assert list(mapping_free["interpolated"]) == ["seebeck", "resistivity", "hall"]
    assert mapping_free["measurements"]["hall"]["values"] == [7.0, 8.0, 9.0]


def test_mapping_and_expected_reach_the_parser_with_interpolation(client: TestClient) -> None:
    body = _parse(
        client,
        "100 1 7\n200 2 8\n300 3 9\n",
        mapping=[{"column": 0, "role": "temperature"}, {"column": 2, "role": "hall"}],
        interpolate={"min_temperature_k": 100.0, "max_temperature_k": 300.0},
    )

    assert list(body["interpolated"]) == ["hall"]
    expected_only = _parse(
        client,
        "100 1\n200 2\n300 3\n",
        expected="resistivity",
        interpolate={"min_temperature_k": 100.0, "max_temperature_k": 300.0},
    )
    assert list(expected_only["interpolated"]) == ["resistivity"]


def test_value_that_is_not_finite_comes_back_as_null() -> None:
    table = parse_table("T S\n100 1\n200 2\n", "seebeck")
    data = InterpolatedData(
        Measurement(np.array([100.0, 200.0]), np.array([np.inf, 1.0])), False, 2, False, False
    )

    response = to_parse_response(ParseOutcome(table, {"seebeck": data}, ()))

    assert response.interpolated["seebeck"].values == [None, 1.0]


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
    assert len(data["values"]) == 35
    assert data["extrapolated"] is expected.extrapolated
    assert data["extrapolated"] is False
    assert data["range_limited"] is True
    assert data["measured_points_in_range"] == expected.measured_points_in_range
    assert data["underdetermined"] is False
    assert body["interpolation_failed"] == []


def test_interpolation_reports_data_that_do_not_set_the_polynomial(client: TestClient) -> None:
    body = _parse(
        client, SIX_ROWS, interpolate={"min_temperature_k": 100.0, "max_temperature_k": 600.0}
    )

    assert body["interpolated"]["seebeck"]["underdetermined"] is True
    assert body["interpolated"]["seebeck"]["extrapolated"] is False
    assert body["interpolated"]["seebeck"]["range_limited"] is False


def test_no_measured_overlap_reaches_existing_failure_response(client: TestClient) -> None:
    body = _parse(
        client, SIX_ROWS, interpolate={"min_temperature_k": 700.0, "max_temperature_k": 800.0}
    )
    assert body["interpolated"] == {}
    assert body["interpolation_failed"] == ["seebeck"]
    assert body["measurements"]["seebeck"]["points"] == 6


@pytest.mark.parametrize("hall_overlaps", [True, False])
def test_each_quantity_uses_its_own_overlap_and_failure_keeps_other_quantities(
    monkeypatch: pytest.MonkeyPatch,
    hall_overlaps: bool,
) -> None:
    # The text parser uses one shared temperature column. Supply valid parsed measurements
    # with distinct domains to exercise the worker's per-quantity interpolation contract.
    from dataclasses import replace

    table = parse_table("T S rho RH\n100 1 4 7\n200 2 5 8\n300 3 6 9\n")
    measurements = {
        "seebeck": Measurement(np.array([25.0, 400.0, 750.0]), np.array([1e-6, 2e-6, 3e-6])),
        "resistivity": Measurement(np.array([100.0, 500.0, 900.0]), np.array([1e-5, 2e-5, 3e-5])),
        "hall": Measurement(
            np.array([200.0, 600.0] if hall_overlaps else [900.0, 1000.0]),
            np.array([1e-8, 2e-8]),
        ),
    }
    monkeypatch.setattr(
        parse_worker, "_read", lambda *args: replace(table, measurements=measurements)
    )
    outcome = parse_worker.parse("", None, None, parse_worker.FitRange(50.0, 800.0))
    response = to_parse_response(outcome)
    assert response.interpolation_failed == ([] if hall_overlaps else ["hall"])
    assert outcome.failure_types == (() if hall_overlaps else ("ValueError",))
    assert response.interpolated["seebeck"].temperature_k == np.linspace(50, 750, 35).tolist()
    assert response.interpolated["resistivity"].temperature_k == np.linspace(100, 800, 35).tolist()
    if hall_overlaps:
        assert response.interpolated["hall"].temperature_k == np.linspace(200, 600, 20).tolist()
    for data in response.interpolated.values():
        assert data.range_limited
        assert not data.extrapolated
    assert response.measurements["hall"].temperature_k == (
        [200.0, 600.0] if hall_overlaps else [900.0, 1000.0]
    )


@pytest.mark.parametrize("failing", [1.0, 4.0, 7.0], ids=["first", "middle", "last"])
def test_one_quantity_failing_leaves_the_others(
    monkeypatch: pytest.MonkeyPatch, failing: float
) -> None:
    def fail_on_one(measurement: Measurement, low: float, high: float) -> Any:
        if measurement.values[0] == failing:
            raise ValueError("The data could not be fitted")
        return interpolate(measurement, low, high)

    monkeypatch.setattr(parse_worker, "interpolate", fail_on_one)
    outcome = parse_worker.parse(
        "T S rho RH\n100 1 4 7\n200 2 5 8\n300 3 6 9\n",
        None,
        None,
        parse_worker.FitRange(100.0, 300.0),
    )

    names = {1.0: "seebeck", 4.0: "resistivity", 7.0: "hall"}
    assert outcome.interpolation_failed == (names[failing],)
    assert set(outcome.interpolated) == set(names.values()) - {names[failing]}
    assert outcome.failure_types == ("ValueError",)


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

    # So it is not the size of the text that refuses it.
    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "too_many_rows"


def test_longest_text_of_notes_is_a_file_with_problems(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": "x" * MAX_TEXT_CHARACTERS})

    assert response.status_code == 200
    assert response.json()["row_count"] == 0


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


@pytest.mark.parametrize("name", PARSE_EXAMPLE_REQUESTS)
def test_examples_in_the_contract_are_what_the_api_answers(client: TestClient, name: str) -> None:
    answer = client.post("/api/parse", json=PARSE_EXAMPLE_REQUESTS[name]).json()
    example = PARSE_EXAMPLE_RESPONSES[name]

    # The polynomial differs from the rounded example in its last digits.
    if example["interpolated"]:
        got = answer["interpolated"]["seebeck"]
        want = example["interpolated"]["seebeck"]
        assert got["values"] == pytest.approx(want["values"], rel=1e-6)
        got["values"] = want["values"]
    assert answer == example
