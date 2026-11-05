import hashlib
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.data_parser import (
    MIN_ROWS,
    ParseIssue,
    parse_table,
    to_measurements,
)

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = sorted((FIXTURES / "examples").glob("*.txt"))
QUANTITIES: dict[str, Any] = {"see": "seebeck", "rho": "resistivity", "hall": "hall"}
TWO_ROWS = "300 1e-6\n400 2e-6\n"


def codes(issues: tuple[ParseIssue, ...]) -> list[str]:
    return [issue.code for issue in issues]


def test_examples_are_the_files_the_golden_results_used() -> None:
    assert len(EXAMPLES) == 9
    for path in EXAMPLES:
        name, kind = path.stem.rsplit("_", 1)
        document = json.loads((FIXTURES / "golden" / f"{name}.json").read_text("utf-8"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert document["input_files_sha256"][kind] == digest, path.name


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.stem)
def test_every_example_reads_cleanly(path: Path) -> None:
    quantity = QUANTITIES[path.stem.rsplit("_", 1)[1]]
    table = parse_table(path.read_text(encoding="utf-8"), quantity)
    assert table.errors == ()
    # This real file measures 100 K twice.
    expected = (
        (ParseIssue("duplicate_temperature", 7, 0),) if path.stem == "01_Fe2VAl09Si01_hall" else ()
    )
    assert table.warnings == expected
    assert table.mapping == {0: "temperature", 1: quantity}
    measurement = table.measurements[quantity]
    assert np.all(np.diff(measurement.temperature_k) >= 0)
    lines = path.read_text(encoding="utf-8").split()
    assert measurement.temperature_k[0] == float(lines[0])
    assert measurement.values[0] == float(lines[1])
    assert measurement.temperature_k[-1] == float(lines[-2])
    assert measurement.values[-1] == float(lines[-1])


@pytest.mark.parametrize("name", ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"])
def test_examples_hold_the_numbers_the_desktop_fitted(name: str) -> None:
    document = json.loads((FIXTURES / "golden" / f"{name}.json").read_text("utf-8"))
    call = next(c for r in document["runs"] for c in r["calls"] if c["function"] == "spb_see_fit")
    table = parse_table((FIXTURES / "examples" / f"{name}_see.txt").read_text("utf-8"), "seebeck")
    temperature_k = table.measurements["seebeck"].temperature_k
    values = table.measurements["seebeck"].values
    inside = (temperature_k >= 50) & (temperature_k <= 800)
    assert temperature_k[inside].tolist() == call["args"][0]
    assert values[inside].tolist() == call["args"][1]


@pytest.mark.parametrize(
    "text",
    [
        "300  1e-6\n400   2e-6\n",  # Two spaces, which fail on the desktop.
        "300, 1e-6\n400, 2e-6\n",  # A comma and a space, which fail on the desktop.
        "300,1e-6\n400,2e-6\n",
        "300\t1e-6\n400\t2e-6\n",
        "300 \t 1e-6\n400\t\t2e-6\n",
        "  300 1e-6  \n400 2e-6\n",
        "300,1e-6,\n400,2e-6,\n",
        "300 1e-6\r\n400 2e-6\r\n",
        "﻿300 1e-6\n400 2e-6\n",
        "# measured in 2024\n\n300 1e-6\n\n400 2e-6\n",
        "3e2 1E-6\n+400. 2.0e-6\n",
    ],
)
def test_every_separator_gives_the_same_numbers(text: str) -> None:
    table = parse_table(text, "seebeck")
    assert table.errors == ()
    measurement = table.measurements["seebeck"]
    assert measurement.temperature_k.tolist() == [300.0, 400.0]
    assert measurement.values.tolist() == [1e-6, 2e-6]


@pytest.mark.parametrize("header", ["T", "T_K", "temp", "t", "TEMP", "T (K)", "T [K]"])
def test_recognised_temperature_headers(header: str) -> None:
    table = parse_table(f"{header}\tS\n300\t1e-6\n400\t2e-6\n")
    assert table.mapping[0] == "temperature"
    assert table.mapping[1] == "seebeck"
    assert "seebeck" in table.measurements


@pytest.mark.parametrize(
    ("header", "role"),
    [
        ("S", "seebeck"),
        ("seebeck", "seebeck"),
        ("rho", "resistivity"),
        ("ρ", "resistivity"),
        ("resistivity", "resistivity"),
        ("RH", "hall"),
        ("R_H", "hall"),
        ("hall", "hall"),
    ],
)
def test_recognised_value_headers(header: str, role: str) -> None:
    table = parse_table(f"T,{header}\n300,1\n400,2\n")
    assert table.mapping == {0: "temperature", 1: role}
    assert table.headers == ("T", header)


def test_one_table_maps_every_quantity_and_ignores_the_rest() -> None:
    table = parse_table("T S comment rho R_H\n300 1 9 2 3\n400 4 9 5 6\n")
    assert table.mapping == {0: "temperature", 1: "seebeck", 3: "resistivity", 4: "hall"}
    assert table.measurements["resistivity"].values.tolist() == [2.0, 5.0]
    assert table.measurements["hall"].values.tolist() == [3.0, 6.0]
    assert len(table.columns) == 5


def test_a_unit_in_a_header_is_not_converted_and_gives_a_warning() -> None:
    table = parse_table("T (K)\tS (uV/K)\n300\t1\n400\t2\n")
    assert codes(table.warnings).count("unit_not_checked") == 2
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_a_header_with_spaces_keeps_its_units() -> None:
    table = parse_table("T (K) S [V/K]\n300 1\n400 2\n")
    assert table.headers == ("T (K)", "S [V/K]")
    assert table.mapping == {0: "temperature", 1: "seebeck"}


def test_no_header_and_no_expected_quantity_maps_only_temperature() -> None:
    table = parse_table(TWO_ROWS)
    assert table.mapping == {0: "temperature"}
    assert table.measurements == {}
    assert table.errors == ()


def test_a_header_with_no_temperature_is_an_error() -> None:
    table = parse_table("S rho\n1 2\n3 4\n")
    assert codes(table.errors) == ["missing_temperature"]
    assert table.measurements == {}
    assert len(table.columns) == 2


def test_a_user_can_assign_columns() -> None:
    table = parse_table("a b c\n300 1 2\n400 3 4\n")
    assert codes(table.errors) == ["missing_temperature"]
    measurements, errors, warnings = to_measurements(
        table.columns, table.lines, {0: "temperature", 2: "hall"}
    )
    assert (errors, warnings) == ([], [])
    assert measurements["hall"].values.tolist() == [2.0, 4.0]


def test_a_repeated_role_warns_and_keeps_the_first() -> None:
    table = parse_table("T S seebeck\n300 1 2\n400 3 4\n")
    assert ParseIssue("repeated_role", column=2) in table.warnings
    assert table.mapping == {0: "temperature", 1: "seebeck"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", [ParseIssue("no_data")]),
        ("\n\n# nothing\n", [ParseIssue("no_data")]),
        ("T S\n", [ParseIssue("no_data")]),
        ("300\n400\n", [ParseIssue("too_few_columns", 1), ParseIssue("too_few_columns", 2)]),
        ("300 1\n400\n", [ParseIssue("too_few_columns", 2)]),
        ("300 1\n400 2 3\n", [ParseIssue("wrong_column_count", 2)]),
        ("300 1\n400 abc\n", [ParseIssue("not_numeric", 2, 1)]),
        ("300 1\nnan 2\n", [ParseIssue("not_numeric", 2, 0)]),
        ("300 1\n400 inf\n", [ParseIssue("not_numeric", 2, 1)]),
        ("300 1\n400 1e999\n", [ParseIssue("not_finite", 2, 1)]),
        ("300,1\n400,,2\n", [ParseIssue("wrong_column_count", 2)]),
        ("300 1\n", [ParseIssue("too_few_rows")]),
        ("300 1\n0 2\n", [ParseIssue("non_positive_temperature", 2, 0)]),
        ("-5 1\n300 2\n", [ParseIssue("non_positive_temperature", 1, 0)]),
        (
            "300,5\t1,2\n400,5\t3,4\n",
            [ParseIssue("decimal_comma", 1), ParseIssue("decimal_comma", 2)],
        ),
    ],
)
def test_problems_are_specific(text: str, expected: list[ParseIssue]) -> None:
    table = parse_table(text, "seebeck")
    assert list(table.errors) == expected
    assert table.measurements == {}


def test_a_line_number_counts_blank_and_comment_lines() -> None:
    table = parse_table("# note\n\n300 1\n\n400 abc\n")
    assert table.errors == (ParseIssue("not_numeric", 5, 1),)


def test_a_header_with_a_missing_value_uses_its_column_count() -> None:
    table = parse_table("T,S\n300,1\n400,,\n")
    assert codes(table.errors) == ["too_few_columns"]


def test_unsorted_rows_are_sorted_with_a_warning() -> None:
    table = parse_table("400 2\n300 1\n500 3\n", "seebeck")
    assert table.warnings[-1] == ParseIssue("unsorted_temperature", column=0)
    measurement = table.measurements["seebeck"]
    assert measurement.temperature_k.tolist() == [300.0, 400.0, 500.0]
    assert measurement.values.tolist() == [1.0, 2.0, 3.0]


def test_duplicate_temperatures_stay_in_order_with_a_warning() -> None:
    table = parse_table("300 1\n300 2\n400 3\n", "seebeck")
    assert ParseIssue("duplicate_temperature", 2, 0) in table.warnings
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0, 3.0]


def test_few_rows_give_a_warning() -> None:
    assert "few_rows" in codes(parse_table(TWO_ROWS, "seebeck").warnings)
    many = "".join(f"{100 + index} 1\n" for index in range(6))
    assert "few_rows" not in codes(parse_table(many, "seebeck").warnings)
    assert MIN_ROWS == 2


def test_problems_hold_no_measured_values() -> None:
    table = parse_table("300 1\n400 123.456abc\n")
    assert "123.456" not in repr(table.errors)


FUZZ_ALPHABET = "0123456789.,eE+- \t\n#TSrhoρ()[]_\r﻿na"


def test_any_small_input_gives_a_table_and_never_raises() -> None:
    generator = random.Random(14)
    for _ in range(3000):
        text = "".join(generator.choices(FUZZ_ALPHABET, k=generator.randint(0, 40)))
        table = parse_table(text, generator.choice(["seebeck", "hall", None]))
        if table.errors:
            assert table.measurements == {}
        for measurement in table.measurements.values():
            measurement.check("fuzz")
