import hashlib
import json
import random
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.data_parser import (
    MAX_ERRORS,
    MAX_LINE_LENGTH,
    MIN_ROWS,
    UNITS,
    ParseIssue,
    header_unit,
    parse_table,
    si_column,
    to_si,
    with_mapping,
)
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest
from seeband_core.model_scales import default_start

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
        ("T,S (mV/K)", 1),
        ("T,S (err)", 1),
        ("T (F),S", 0),
        ("T (°F),S", 0),
        ("T,rho (uOhm cm)", 1),
    ],
)
def test_a_column_in_another_unit_is_not_read_as_if_in_ours(header: str, column: int) -> None:
    table = parse_table(f"{header}\n300,1\n400,2\n")
    assert ParseIssue("unit_differs", column=column) in table.warnings
    assert column not in table.mapping


# Rows of a Fe2VAl-like sample: T in K, S in V/K, ρ in Ω·m, R_H in m³/C.
SI_ROWS = [
    (100.0, 5.0e-5, 4.0e-6, 2.0e-9),
    (200.0, 8.0e-5, 5.0e-6, 1.5e-9),
    (300.0, 1.0e-4, 6.0e-6, 1.2e-9),
    (400.0, 1.1e-4, 7.0e-6, 1.0e-9),
    (500.0, 1.15e-4, 8.0e-6, 0.9e-9),
    (600.0, 1.18e-4, 9.0e-6, 0.8e-9),
]


def lab_units_text(header: str) -> str:
    """The same rows in µV/K, mΩ·cm and cm³/C, written exactly in decimal."""
    rows = [f"{t:g} {s * 1e6:.6g} {rho * 1e5:.6g} {rh * 1e6:.6g}" for t, s, rho, rh in SI_ROWS]
    return header + "\n" + "\n".join(rows) + "\n"


def si_text() -> str:
    rows = [f"{t:g} {s:.6g} {rho:.6g} {rh:.6g}" for t, s, rho, rh in SI_ROWS]
    return "T S rho RH\n" + "\n".join(rows) + "\n"


@pytest.mark.parametrize(
    ("role", "written", "unit"),
    [
        ("seebeck", "V/K", "V/K"),
        ("seebeck", "uV/K", "uV/K"),
        ("seebeck", "µV/K", "uV/K"),
        ("seebeck", "μV / K", "uV/K"),
        ("resistivity", "Ohm m", "Ohm*m"),
        ("resistivity", "Ω·m", "Ohm*m"),
        ("resistivity", "mOhm cm", "mOhm*cm"),
        ("resistivity", "mΩ·cm", "mOhm*cm"),
        ("resistivity", "µΩ·m", "uOhm*m"),
        ("hall", "m^3/C", "m^3/C"),
        ("hall", "cm³/C", "cm^3/C"),
        ("hall", "cm3/C", "cm^3/C"),
        ("temperature", "K", "K"),
        ("temperature", "°C", "C"),
        ("temperature", "C", "C"),
        ("temperature", "degC", "C"),
        ("temperature", "℃", "C"),
        ("temperature", "ºC", "C"),
        ("temperature", "Celsius", "C"),
    ],
)
def test_a_header_names_its_unit_in_any_usual_spelling(role: Any, written: str, unit: str) -> None:
    assert header_unit(role, written) == unit


@pytest.mark.parametrize(
    ("role", "written"),
    [
        # Mega is not milli: lower case alone would read it 1e9 off.
        ("resistivity", "MOhm cm"),
        ("resistivity", "MΩ·cm"),
        ("seebeck", "mV/K"),
        ("seebeck", "V/s"),
        ("hall", "cm^3/A"),
        ("temperature", "°F"),
    ],
)
def test_a_unit_this_cannot_read_is_not_guessed(role: Any, written: str) -> None:
    assert header_unit(role, written) is None


def test_every_unit_converts_by_its_power_of_ten_and_si_not_at_all() -> None:
    texts = ("1", "-2.5", "123.456", "7.25e3")
    values = np.array([float(text) for text in texts])
    for role, units in UNITS.items():
        si, *others = units
        assert units[si].is_si
        others = [unit for unit in others if units[unit].offset == 0]
        assert to_si(role, si, texts, values).tolist() == values.tolist()
        for unit in others:
            exponent = units[unit].exponent
            expected = [
                float(f"{text}e{exponent}") if "e" not in text else 7.25e3 * 10.0**exponent
                for text in texts
            ]
            np.testing.assert_allclose(to_si(role, unit, texts, values), expected, rtol=1e-15)
    with pytest.raises(ValueError, match="not a unit of seebeck"):
        to_si("seebeck", "m^3/C", texts, values)


def test_a_converted_value_is_the_float_of_the_same_digits_in_si_to_the_last_bit() -> None:
    # A float product gives 4.9999999999999996e-05 for 50 µV/K, which a fit turns into 1e-8.
    rng = np.random.default_rng(20261112)
    texts = tuple(f"{value:.4f}" for value in rng.uniform(1, 999, 5000))
    values = np.array([float(text) for text in texts])
    micro = to_si("seebeck", "uV/K", texts, values)
    in_si = [float(f"{text}e-6") for text in texts]
    assert micro.tolist() == in_si
    milli_cm = to_si("resistivity", "mOhm*cm", texts, values)
    assert milli_cm.tolist() == [float(f"{text}e-5") for text in texts]


def test_lab_units_named_in_the_header_read_the_same_as_si() -> None:
    lab = parse_table(lab_units_text("T(K) S(uV/K) rho(mOhm cm) RH(cm^3/C)"))
    si = parse_table(si_text())
    assert lab.units == {0: "K", 1: "uV/K", 2: "mOhm*cm", 3: "cm^3/C"}
    assert si.units == {0: "K", 1: "V/K", 2: "Ohm*m", 3: "m^3/C"}
    assert codes(lab.warnings) == codes(si.warnings) == []
    for quantity in ("seebeck", "resistivity", "hall"):
        assert (
            lab.measurements[quantity].values.tolist() == si.measurements[quantity].values.tolist()
        )


def test_lab_units_chosen_by_a_user_read_the_same_as_si() -> None:
    mapping: Any = {0: "temperature", 1: "seebeck", 2: "resistivity", 3: "hall"}
    chosen: Any = {1: "uV/K", 2: "mOhm*cm", 3: "cm^3/C"}
    lab = parse_table(lab_units_text("T S rho RH"), mapping=mapping, units=chosen)
    si = parse_table(si_text())
    assert lab.units == {0: "K", **chosen}
    for quantity in ("seebeck", "resistivity", "hall"):
        assert (
            lab.measurements[quantity].values.tolist() == si.measurements[quantity].values.tolist()
        )


def _in_lab_units(path: Path, exponent: int) -> str:
    """An example file with its values shifted in decimal, as a lab would write them."""
    rows = [line.split() for line in path.read_text().strip().splitlines()]
    return "\n".join(f"{t} {Decimal(v).scaleb(exponent)}" for t, v in rows) + "\n"


def test_a_fit_from_lab_units_equals_the_fit_from_si() -> None:
    """FS20: SI data and the same data in µV/K and mΩ·cm give the same parameters."""
    example = FIXTURES / "examples" / "01_Fe2VAl09Si01"
    si = {
        "seebeck": parse_table(Path(f"{example}_see.txt").read_text(), "seebeck"),
        "resistivity": parse_table(Path(f"{example}_rho.txt").read_text(), "resistivity"),
    }
    lab = {
        "seebeck": parse_table(
            _in_lab_units(Path(f"{example}_see.txt"), 6),
            mapping={0: "temperature", 1: "seebeck"},
            units={1: "uV/K"},
        ),
        "resistivity": parse_table(
            _in_lab_units(Path(f"{example}_rho.txt"), 5),
            mapping={0: "temperature", 1: "resistivity"},
            units={1: "mOhm*cm"},
        ),
    }
    model = registry.get("dpb")
    mode = next(m for m in model.describe().fit_modes if m.id == "dpb_s_rho")
    results = [
        model.fit(
            FitRequest(
                "dpb_s_rho",
                {quantity: table.measurements[quantity] for quantity, table in tables.items()},  # type: ignore[index]
                default_start(mode),
                scattering="acPh",
            ),
            lambda *_: None,
        )
        for tables in (si, lab)
    ]
    assert results[0].status == results[1].status == "converged"
    for name, value in results[0].parameters.items():
        assert results[1].parameters[name] == pytest.approx(value, rel=1e-12, abs=0), name


def test_celsius_is_kelvin_less_273_15_to_the_last_bit() -> None:
    rng = np.random.default_rng(1112)
    texts = tuple(f"{value:.3f}" for value in rng.uniform(-200, 700, 5000))
    values = np.array([float(text) for text in texts])
    kelvin = to_si("temperature", "C", texts, values)
    assert kelvin.tolist() == [float(Decimal(text) + Decimal("273.15")) for text in texts]
    assert to_si("temperature", "C", ("26.85", "-273.15"), np.zeros(2)).tolist() == [300.0, 0.0]


def test_a_table_in_celsius_reads_as_the_same_table_in_kelvin() -> None:
    celsius = parse_table("T (°C) S\n-173.15 1e-6\n26.85 3e-6\n126.85 4e-6\n")
    kelvin = parse_table("T (K) S\n100 1e-6\n300 3e-6\n400 4e-6\n")
    assert celsius.units[0] == "C"
    assert (
        celsius.measurements["seebeck"].temperature_k.tolist()
        == kelvin.measurements["seebeck"].temperature_k.tolist()
        == [100.0, 300.0, 400.0]
    )


def test_celsius_below_zero_is_not_below_zero_kelvin() -> None:
    table = parse_table(
        "T S\n-50 1e-6\n20 2e-6\n", mapping={0: "temperature", 1: "seebeck"}, units={0: "C"}
    )
    assert table.errors == ()
    assert table.measurements["seebeck"].temperature_k.tolist() == [223.15, 293.15]


def test_celsius_below_absolute_zero_is_an_error_on_its_line() -> None:
    table = parse_table("T (°C) S\n-300 1e-6\n20 2e-6\n")
    assert table.errors == (ParseIssue("non_positive_temperature", 2, 0),)


def test_si_column_is_in_the_order_of_the_text_and_none_without_a_role() -> None:
    table = parse_table("T S (uV/K) x\n300 3 9\n100 1 9\n")
    column = si_column(table, 1)
    assert column is not None
    assert column.tolist() == [3e-6, 1e-6]
    assert si_column(table, 2) is None
    first = si_column(table, 1, rows=1)
    assert first is not None
    assert first.tolist() == [3e-6]


@pytest.mark.parametrize(
    ("text", "quantity", "expected"),
    [
        # Float reads these as 0, and Decimal cannot hold the exponent.
        ("T (K)\tS (uV/K)\n100\t1e-99999999999999999999\n200\t50\n", "seebeck", [0.0, 5e-5]),
        ("T (C)\tS (V/K)\n1e-99999999999999999999\t1e-4\n200\t2e-4\n", "seebeck", [1e-4, 2e-4]),
        ("T (K)\tS (uV/K)\n100\t1e-500\n200\t50\n", "seebeck", [0.0, 5e-5]),
    ],
)
def test_a_value_at_an_exponent_no_measurement_has_converts_as_read(
    text: str, quantity: Any, expected: list[float]
) -> None:
    table = parse_table(text)
    assert table.errors == ()
    assert table.measurements[quantity].values.tolist() == expected


def test_lab_units_read_as_si_are_called_implausible() -> None:
    table = parse_table(lab_units_text("T S rho RH"))
    # ρ of 0.9 mΩ·cm read as Ω·m, and R_H of 2e-3 cm³/C read as m³/C, are still possible values,
    # as the SiP example shows, so only the unit chosen catches them.
    assert [(issue.code, issue.column) for issue in table.warnings] == [
        ("implausible_magnitude", 1),
    ]
    # The values are read as written, as the warning only says they look wrong.
    assert table.measurements["seebeck"].values[0] == 50.0


def test_large_hall_values_read_as_si_are_called_implausible() -> None:
    table = parse_table("T RH\n100 0.5\n200 0.3\n")
    assert ParseIssue("implausible_magnitude", column=1) in table.warnings


def test_si_values_far_too_small_are_called_implausible() -> None:
    table = parse_table("T S\n100 1e-12\n200 2e-12\n")
    assert ParseIssue("implausible_magnitude", column=1) in table.warnings


def test_a_unit_from_another_quantity_is_refused_and_reads_nothing() -> None:
    table = parse_table(si_text(), mapping={0: "temperature", 1: "seebeck"}, units={1: "cm^3/C"})
    assert table.errors == (ParseIssue("unit_not_allowed", column=1),)
    assert table.measurements == {}


def test_a_unit_for_a_column_outside_the_mapping_is_ignored() -> None:
    table = parse_table(si_text(), mapping={0: "temperature", 1: "seebeck"}, units={2: "uV/K"})
    assert table.errors == ()
    assert table.units == {0: "K", 1: "V/K"}


def test_a_column_with_an_unreadable_unit_assigned_by_hand_is_read_in_si_and_says_so() -> None:
    table = parse_table("T S (mV/s)\n300 1e-4\n400 2e-4\n")
    assert ParseIssue("unit_differs", column=1) in table.warnings
    assigned = with_mapping(table, {0: "temperature", 1: "seebeck"})
    # No longer "not used", which would be false.
    assert ParseIssue("unit_differs", column=1) not in assigned.warnings
    assert ParseIssue("unit_assumed", column=1) in assigned.warnings
    assert assigned.units[1] == "V/K"
    assert assigned.measurements["seebeck"].values.tolist() == [1e-4, 2e-4]


def test_a_known_header_unit_carries_over_to_a_hand_assignment() -> None:
    table = parse_table("T Svalues (uV/K)\n300 100\n400 200\n")
    assigned = with_mapping(table, {0: "temperature", 1: "seebeck"})
    assert assigned.units[1] == "uV/K"
    np.testing.assert_allclose(assigned.measurements["seebeck"].values, [1e-4, 2e-4], rtol=1e-15)


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


def test_a_negative_resistivity_is_an_error_on_its_lines() -> None:
    table = parse_table("T rho\n100 1e-5\n200 -2e-5\n300 -1e-5\n", expected="resistivity")

    assert table.errors == (
        ParseIssue("negative_resistivity", 3, 1),
        ParseIssue("negative_resistivity", 4, 1),
    )
    assert table.measurements == {}


def test_negative_values_of_other_quantities_and_zero_resistivity_are_fine() -> None:
    table = parse_table("T S rho RH\n100 -1e-5 0 -1e-8\n200 -2e-5 1e-5 -2e-8\n")

    assert table.errors == ()
    assert set(table.measurements) == {"seebeck", "resistivity", "hall"}


def test_a_mapping_away_from_the_negative_column_clears_the_error() -> None:
    table = parse_table("T a b\n100 -1 1\n200 -2 2\n", mapping={0: "temperature", 1: "resistivity"})
    assert codes(table.errors) == ["negative_resistivity", "negative_resistivity"]

    repaired = with_mapping(table, {0: "temperature", 1: "seebeck", 2: "resistivity"})

    assert repaired.errors == ()
    assert set(repaired.measurements) == {"seebeck", "resistivity"}


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
