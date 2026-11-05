import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.data_parser import (
    MAX_ERRORS,
    MAX_LINE_LENGTH,
    MIN_ROWS,
    ParseIssue,
    parse_table,
    with_mapping,
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


@pytest.mark.parametrize("header", ["T", "T_K", "temp", "TEMP", "t_k", "T (K)", "T [K]", "T(K)"])
def test_recognised_temperature_headers(header: str) -> None:
    table = parse_table(f"{header}\tS\n300\t1e-6\n400\t2e-6\n")
    assert table.mapping[0] == "temperature"
    assert table.mapping[1] == "seebeck"
    assert "seebeck" in table.measurements
    assert "unit_differs" not in codes(table.warnings)


@pytest.mark.parametrize(
    ("header", "role"),
    [
        ("S", "seebeck"),
        ("seebeck", "seebeck"),
        ("Seebeck", "seebeck"),
        ("rho", "resistivity"),
        ("ρ", "resistivity"),
        ("resistivity", "resistivity"),
        ("RH", "hall"),
        ("R_H", "hall"),
        ("hall", "hall"),
        ("S (V/K)", "seebeck"),
        ("rho (Ohm m)", "resistivity"),
        ("rho(Ohm m)", "resistivity"),
        ("ρ [Ω·m]", "resistivity"),
        ("R_H (m^3/C)", "hall"),
        ("RH [m³/C]", "hall"),
    ],
)
def test_recognised_value_headers(header: str, role: str) -> None:
    table = parse_table(f"T,{header}\n300,1\n400,2\n")
    assert table.mapping == {0: "temperature", 1: role}
    assert table.headers == ("T", header)
    assert "unit_differs" not in codes(table.warnings)


def test_headers_read_the_same_with_spaces_tabs_and_commas() -> None:
    for line in (
        "T (K) rho (Ohm m)",
        "T (K)\trho (Ohm m)",
        "T (K), rho (Ohm m)",
        "T (K),rho (Ohm m),",
    ):
        table = parse_table(f"{line}\n300 1\n400 2\n")
        assert table.headers == ("T (K)", "rho (Ohm m)"), line
        assert table.mapping == {0: "temperature", 1: "resistivity"}


def test_quoted_headers_are_recognised() -> None:
    table = parse_table('"T","S"\n300,1\n400,2\n')
    assert table.mapping == {0: "temperature", 1: "seebeck"}


def test_one_table_maps_every_quantity_and_ignores_the_rest() -> None:
    table = parse_table("T S comment rho R_H\n300 1 9 2 3\n400 4 9 5 6\n")
    assert table.mapping == {0: "temperature", 1: "seebeck", 3: "resistivity", 4: "hall"}
    assert table.measurements["resistivity"].values.tolist() == [2.0, 5.0]
    assert table.measurements["hall"].values.tolist() == [3.0, 6.0]
    assert len(table.columns) == 5


@pytest.mark.parametrize(
    "text",
    [
        "t (s)\tT (K)\tS (V/K)\n10\t300\t1\n20\t400\t2\n",
        "t T S\n10 300 1\n20 400 2\n",
        "s T S\n10 300 1\n20 400 2\n",
    ],
)
def test_lower_case_t_and_s_are_not_taken_for_temperature_or_seebeck(text: str) -> None:
    table = parse_table(text)
    assert table.mapping == {1: "temperature", 2: "seebeck"}
    assert table.measurements["seebeck"].temperature_k.tolist() == [300.0, 400.0]
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


@pytest.mark.parametrize(
    ("header", "column"),
    [
        ("T,S (uV/K)", 1),
        ("T,S (err)", 1),
        ("T (C),S", 0),
        ("T (°C),S", 0),
        ("T,rho (uOhm cm)", 1),
    ],
)
def test_a_column_in_another_unit_is_not_read_as_if_in_ours(header: str, column: int) -> None:
    table = parse_table(f"{header}\n300,1\n400,2\n")
    assert ParseIssue("unit_differs", column=column) in table.warnings
    assert column not in table.mapping


def test_a_column_with_an_error_does_not_replace_the_real_one() -> None:
    table = parse_table("T S(err) S\n300 9 1\n400 9 2\n")
    assert table.mapping == {0: "temperature", 2: "seebeck"}
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_a_repeated_header_warns_and_keeps_the_first() -> None:
    table = parse_table("T S seebeck\n300 1 2\n400 3 4\n")
    assert ParseIssue("repeated_header", column=2) in table.warnings
    assert table.mapping == {0: "temperature", 1: "seebeck"}


def test_no_header_and_no_expected_quantity_maps_only_temperature() -> None:
    table = parse_table(TWO_ROWS)
    assert table.mapping == {0: "temperature"}
    assert table.measurements == {}
    assert table.errors == ()
    assert "no_quantity" in codes(table.warnings)


@pytest.mark.parametrize(
    "text",
    [
        "# T S rho\n300 1 2\n400 3 4\n",
        "300,5,1,2\n400,5,3,4\n",
        "300,5, 1,2\n400,5, 3,4\n",
        "300,5 , 1,2\n400,5 , 3,4\n",
        "300,5, 1\n400,5, 2\n",
    ],
)
def test_more_than_two_columns_with_no_header_are_not_guessed(text: str) -> None:
    table = parse_table(text, "resistivity")
    assert table.mapping == {0: "temperature"}
    assert table.measurements == {}
    assert "columns_need_assigning" in codes(table.warnings)
    assert "expected_not_found" in codes(table.warnings)
    assert len(table.columns) >= 3


@pytest.mark.parametrize("header", ["T x", "T S"])
def test_a_header_without_the_expected_quantity_warns(header: str) -> None:
    table = parse_table(f"{header}\n300 1\n400 2\n", "hall")
    assert "expected_not_found" in codes(table.warnings)
    assert "hall" not in table.measurements


def test_a_header_with_no_temperature_is_an_error_with_columns_to_assign() -> None:
    table = parse_table("S rho\n1 2\n3 4\n")
    assert codes(table.errors) == ["missing_temperature"]
    assert table.measurements == {}
    assert len(table.columns) == 2


def test_a_user_can_assign_columns() -> None:
    table = parse_table("a b c\n300 1 2\n400 3 4\n")
    assert codes(table.errors) == ["missing_temperature"]
    chosen = with_mapping(table, {0: "temperature", 2: "hall"})
    assert chosen.errors == ()
    assert chosen.mapping == {0: "temperature", 2: "hall"}
    assert chosen.measurements["hall"].values.tolist() == [2.0, 4.0]
    assert "few_rows" in codes(chosen.warnings)


def test_a_mapping_can_come_with_the_text() -> None:
    table = parse_table("a b\n300 1\n400 2\n", mapping={0: "temperature", 1: "seebeck"})
    assert table.errors == ()
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_a_user_mapping_can_repair_a_non_positive_temperature() -> None:
    table = parse_table("T x\n0 300\n1 400\n")
    assert codes(table.errors) == ["non_positive_temperature"]
    chosen = with_mapping(table, {1: "temperature", 0: "seebeck"})
    assert chosen.errors == ()
    assert chosen.measurements["seebeck"].temperature_k.tolist() == [300.0, 400.0]


@pytest.mark.parametrize("mapping", [{5: "temperature"}, {-1: "temperature"}, {0: "nothing"}])
def test_a_mapping_that_cannot_apply_raises(mapping: Any) -> None:
    with pytest.raises(ValueError):
        with_mapping(parse_table(TWO_ROWS), mapping)


def test_a_mapping_cannot_use_a_role_twice() -> None:
    table = with_mapping(parse_table("1 2 3\n4 5 6\n"), {0: "temperature", 1: "hall", 2: "hall"})
    assert codes(table.errors) == ["repeated_role", "repeated_role"]
    assert table.measurements == {}


def test_a_mapping_cannot_hide_a_bad_line() -> None:
    table = parse_table("300 1\n400 abc\n500 3\n")
    chosen = with_mapping(table, {0: "temperature", 1: "seebeck"})
    assert codes(chosen.errors) == ["not_numeric"]
    assert chosen.measurements == {}


def test_an_unknown_expected_quantity_raises() -> None:
    with pytest.raises(ValueError):
        parse_table(TWO_ROWS, "foo")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", [ParseIssue("no_data")]),
        ("\n\n# nothing\n", [ParseIssue("no_data")]),
        ("T S\n", [ParseIssue("no_data")]),
        ("300\n400\n", [ParseIssue("too_few_columns", 1), ParseIssue("too_few_columns", 2)]),
        ("300 1\n400\n", [ParseIssue("too_few_columns", 2)]),
        ("300\n400 1\n500 2\n", [ParseIssue("too_few_columns", 1)]),
        ("300 1\n400 2 3\n", [ParseIssue("wrong_column_count", 2)]),
        ("300 1 2\n400 3\n", [ParseIssue("wrong_column_count", 2)]),
        ("300 1\n400 abc\n", [ParseIssue("not_numeric", 2, 1)]),
        ("300 1\nnan 2\n", [ParseIssue("not_numeric", 2, 0)]),
        ("300 1\n400 inf\n", [ParseIssue("not_numeric", 2, 1)]),
        ("300 1\n400 1e999\n", [ParseIssue("not_finite", 2, 1)]),
        ("300 1\n400 1.0D-6\n", [ParseIssue("not_numeric", 2, 1)]),
        ("300 1 2\n400,,2\n", [ParseIssue("missing_value", 2, 1)]),
        ("300 1\n", [ParseIssue("too_few_rows")]),
        ("300 1\n0 2\n", [ParseIssue("non_positive_temperature", 2, 0)]),
        ("-5 1\n300 2\n", [ParseIssue("non_positive_temperature", 1, 0)]),
        (
            "300,5\t1,2\n400,5\t3,4\n",
            [ParseIssue("decimal_comma", 1), ParseIssue("decimal_comma", 2)],
        ),
        ("300,5 1,2\n", [ParseIssue("decimal_comma", 1)]),
        ("300,1.5 2.0\n", [ParseIssue("decimal_comma", 1)]),
        # A typo in the first row is an error on its line, and does not become a header.
        ("3O0 1e-6\n400 2e-6\n500 3e-6\n", [ParseIssue("not_numeric", 1, 0)]),
        ("300 1e\n400 2\n", [ParseIssue("not_numeric", 1, 1)]),
        ("1.0D-6 300\n400 2\n", [ParseIssue("not_numeric", 1, 0)]),
        ("300;1\n400;2\n", [ParseIssue("too_few_columns", 1), ParseIssue("too_few_columns", 2)]),
    ],
)
def test_problems_are_specific(text: str, expected: list[ParseIssue]) -> None:
    table = parse_table(text, "seebeck")
    assert list(table.errors) == expected
    assert table.measurements == {}


def test_comma_and_space_separators_are_not_taken_for_decimal_commas() -> None:
    table = parse_table("300, 1\n400, 2\n", "seebeck")
    assert table.errors == ()
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_rows_that_could_be_read_stay_for_a_preview() -> None:
    table = parse_table("T S\n300 1\n400 abc\n500 3\n")
    assert codes(table.errors) == ["not_numeric"]
    assert table.columns[0].tolist() == [300.0, 500.0]
    assert table.lines == (2, 4)
    assert table.headers == ("T", "S")
    assert table.measurements == {}


def test_a_header_with_the_wrong_column_count_leaves_columns_to_assign() -> None:
    for line in ("Temperature Seebeck coefficient", "T Kelvin S"):
        table = parse_table(f"{line}\n300 1\n400 2\n")
        assert "header_mismatch" in codes(table.warnings)
        assert codes(table.errors) == ["missing_temperature"]
        assert len(table.columns) == 2
        assert table.headers is None


def test_text_before_a_table_is_skipped_with_a_warning() -> None:
    table = parse_table("Sample A\nmeasured Tuesday\nT S\n300 1\n400 2\n")
    assert table.headers == ("T", "S")
    assert table.warnings[:2] == (
        ParseIssue("preamble_skipped", 1),
        ParseIssue("preamble_skipped", 2),
    )
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_comments_after_values_are_ignored() -> None:
    table = parse_table("300 1 # first\n400 2\n", "seebeck")
    assert table.errors == ()
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0]


def test_a_bom_after_a_blank_line_is_ignored() -> None:
    table = parse_table("\n\ufeff300 1\n400 2\n", "seebeck")
    assert table.errors == ()
    assert table.lines == (2, 3)


def test_a_line_number_counts_blank_and_comment_lines() -> None:
    table = parse_table("# note\n\n300 1\n\n400 abc\n")
    assert table.errors == (ParseIssue("not_numeric", 5, 1),)


def test_unsorted_rows_are_sorted_with_a_warning() -> None:
    table = parse_table("400 2\n300 1\n500 3\n", "seebeck")
    assert ParseIssue("unsorted_temperature", column=0) in table.warnings
    assert table.columns[0].tolist() == [400.0, 300.0, 500.0]
    measurement = table.measurements["seebeck"]
    assert measurement.temperature_k.tolist() == [300.0, 400.0, 500.0]
    assert measurement.values.tolist() == [1.0, 2.0, 3.0]


def test_duplicate_temperatures_stay_in_order_with_a_warning() -> None:
    table = parse_table("300 1\n300 2\n400 3\n", "seebeck")
    assert ParseIssue("duplicate_temperature", 2, 0) in table.warnings
    assert table.measurements["seebeck"].values.tolist() == [1.0, 2.0, 3.0]


def test_a_duplicate_found_after_sorting_names_its_own_line() -> None:
    table = parse_table("300 1\n400 2\n# note\n300 3\n", "seebeck")
    assert ParseIssue("duplicate_temperature", 4, 0) in table.warnings
    assert table.measurements["seebeck"].values.tolist() == [1.0, 3.0, 2.0]


def test_temperature_in_another_column_sorts_every_quantity() -> None:
    table = parse_table("S T rho\n1 400 2\n3 300 4\n")
    assert table.measurements["seebeck"].values.tolist() == [3.0, 1.0]
    assert table.measurements["resistivity"].values.tolist() == [4.0, 2.0]
    assert ParseIssue("non_positive_temperature", 3, 1) in parse_table("S T\n1 400\n3 0\n").errors


def test_measurements_do_not_share_memory_with_columns() -> None:
    table = parse_table(TWO_ROWS, "seebeck")
    assert not np.shares_memory(table.measurements["seebeck"].values, table.columns[1])


def test_few_distinct_temperatures_give_a_warning() -> None:
    assert "few_rows" in codes(parse_table(TWO_ROWS, "seebeck").warnings)
    five = "".join(f"{100 + index} 1\n" for index in range(5))
    assert "few_rows" in codes(parse_table(five, "seebeck").warnings)
    six = "".join(f"{100 + index} 1\n" for index in range(6))
    assert "few_rows" not in codes(parse_table(six, "seebeck").warnings)
    repeated = "".join(f"{100 + index % 3} 1\n" for index in range(9))
    assert "few_rows" in codes(parse_table(repeated, "seebeck").warnings)
    assert MIN_ROWS == 2


def test_a_very_long_line_is_refused_quickly() -> None:
    long_field = "1" * (MAX_LINE_LENGTH + 1)
    table = parse_table(f"300 1\n400 {long_field}\n500 3\n", "seebeck")
    assert table.errors == (ParseIssue("line_too_long", 2),)
    started = time.perf_counter()
    parse_table("(" * 40_000 + "\n1 2\n3 4\n")
    parse_table("1" * 40_000 + "x 1\n")
    parse_table("T," + " " * 40_000 + ",S\n1 2\n3 4\n")
    assert time.perf_counter() - started < 1.0


def test_the_list_of_problems_stops() -> None:
    table = parse_table("abc x\n" * 2 + "300 1\n" + "400 abc\n" * 1000)
    assert len(table.errors) <= MAX_ERRORS + 2
    assert table.errors[-1].code == "too_many_problems"


def test_only_real_line_breaks_count_for_line_numbers() -> None:
    table = parse_table("300 1\x0c\n400 abc\n")
    assert table.errors == (ParseIssue("not_numeric", 2, 1),)
    assert parse_table("300 1\r400 2\r", "seebeck").lines == (1, 2)


def test_problems_hold_no_measured_values() -> None:
    table = parse_table("300 1\n400 123.456abc\n")
    assert "123.456" not in repr(table.errors)
    assert table.headers is None


def test_number_forms() -> None:
    table = parse_table("3e2 +1\n.5e3 -.5\n600. 5e+0\n", "seebeck")
    assert table.errors == ()
    assert table.measurements["seebeck"].temperature_k.tolist() == [300.0, 500.0, 600.0]
    assert table.measurements["seebeck"].values.tolist() == [1.0, -0.5, 5.0]


SEPARATORS = (" ", "  ", "\t", ",", ", ", " , ")
HEADERS = ("T S", "T,S", "T\tS", "temp seebeck", "x y", "T S extra", "")


def test_structured_input_keeps_every_number_or_reports_a_problem() -> None:
    generator = random.Random(14)
    reached = 0
    for _ in range(3000):
        count = generator.randint(0, 8)
        temperature_k = [round(generator.uniform(1, 900), 3) for _ in range(count)]
        values = [round(generator.uniform(-1, 1), 6) for _ in range(count)]
        separator = generator.choice(SEPARATORS)
        rows = [f"{t!r}{separator}{v!r}" for t, v in zip(temperature_k, values, strict=True)]
        if rows and generator.random() < 0.2:
            rows[generator.randrange(len(rows))] += generator.choice([" x", ",", " 1", "e"])
        text = "\n".join([generator.choice(HEADERS), *rows])
        table = parse_table(text, generator.choice(["seebeck", None]))
        if table.errors:
            assert table.measurements == {}
        for measurement in table.measurements.values():
            reached += 1
            measurement.check("fuzz")
            assert sorted(temperature_k) == measurement.temperature_k.tolist()
            expected = [
                v for _, v in sorted(zip(temperature_k, values, strict=True), key=lambda p: p[0])
            ]
            assert expected == measurement.values.tolist()
    assert reached > 500


FUZZ_ALPHABET = "0123456789.,eE+- \t\n#TSrhoρ()[]_\r\ufeffna"


def test_any_small_input_gives_a_table_and_never_raises() -> None:
    generator = random.Random(14)
    for _ in range(3000):
        text = "".join(generator.choices(FUZZ_ALPHABET, k=generator.randint(0, 40)))
        table = parse_table(text, generator.choice(["seebeck", "hall", None]))
        if table.errors:
            assert table.measurements == {}
        for measurement in table.measurements.values():
            measurement.check("fuzz")
