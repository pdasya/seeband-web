"""FS18: a conductivity loaded in place of a resistivity, which the parser turns into 1/sigma."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.data_parser import ParseIssue, header_unit, parse_table, with_mapping
from seeband_core.measured_points import resistivity_from_conductivity
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest
from seeband_core.model_scales import default_start

EXAMPLE = Path(__file__).parent / "fixtures" / "examples" / "01_Fe2VAl09Si01"
# As in the golden regression, which fits must meet across environments.
FIT_TOLERANCE = 1e-5


def codes(issues: tuple[ParseIssue, ...]) -> list[str]:
    return [issue.code for issue in issues]


def test_resistivity_is_the_float_nearest_one_over_sigma() -> None:
    sigma = np.array([1.0, 3.0, 7e4, 1e10, 1e-300])
    assert resistivity_from_conductivity(sigma).tolist() == [1.0 / value for value in sigma]
    assert resistivity_from_conductivity(np.array([2.0, 1e5])).tolist() == [0.5, 1e-5]


def test_the_measured_conductivity_stays_as_it_was() -> None:
    sigma = np.array([1e5, 2e5])
    resistivity_from_conductivity(sigma)
    assert sigma.tolist() == [1e5, 2e5]


@pytest.mark.parametrize("value", [0.0, -1.0, 5e-324, np.inf, np.nan])
def test_a_conductivity_with_no_resistivity_raises(value: float) -> None:
    with pytest.raises(ValueError, match="no resistivity"):
        resistivity_from_conductivity(np.array([1e5, value]))


def test_no_conductivity_gives_no_resistivity() -> None:
    assert resistivity_from_conductivity(np.array([])).tolist() == []


@pytest.mark.parametrize(
    ("header", "unit"),
    [
        ("sigma", "S/m"),
        ("σ", "S/m"),
        ("Sigma", "S/m"),
        ("conductivity", "S/m"),
        ("sigma (S/m)", "S/m"),
        ("σ [S/cm]", "S/cm"),
        ("conductivity (1/Ohm m)", "S/m"),
        ("sigma (1/Ω cm)", "S/cm"),
        ("sigma (Ohm^-1 cm^-1)", "S/cm"),
    ],
)
def test_conductivity_headers_and_their_units(header: str, unit: str) -> None:
    table = parse_table(f"T\t{header}\n300\t2e5\n400\t1e5\n")
    assert table.mapping == {0: "temperature", 1: "conductivity"}
    assert table.units[1] == unit
    assert table.loaded_as == {"resistivity": "conductivity"}
    assert "resistivity" in table.measurements


def test_header_units_of_conductivity_are_not_read_for_another_quantity() -> None:
    assert header_unit("conductivity", "S/cm") == "S/cm"
    assert header_unit("resistivity", "S/cm") is None
    # Mega is not milli, as for a resistivity.
    assert header_unit("conductivity", "MS/m") is None


def test_a_conductivity_column_gives_a_resistivity_of_one_over_sigma() -> None:
    table = parse_table("T sigma\n400 1e5\n300 4e4\n")
    assert table.errors == ()
    measurement = table.measurements["resistivity"]
    assert measurement.temperature_k.tolist() == [300.0, 400.0]
    assert measurement.values.tolist() == [1.0 / 4e4, 1.0 / 1e5]
    assert set(table.measurements) == {"resistivity"}


def test_s_per_cm_is_a_hundred_s_per_m() -> None:
    per_cm = parse_table("T sigma(S/cm)\n300 400\n400 1000\n")
    per_m = parse_table("T sigma(S/m)\n300 4e4\n400 1e5\n")
    assert per_cm.units[1] == "S/cm"
    assert (
        per_cm.measurements["resistivity"].values.tolist()
        == per_m.measurements["resistivity"].values.tolist()
    )


def test_a_file_with_no_header_reads_as_the_conductivity_expected() -> None:
    table = parse_table("300 4e4\n400 1e5\n", expected="conductivity")
    assert table.mapping == {0: "temperature", 1: "conductivity"}
    assert table.loaded_as == {"resistivity": "conductivity"}
    assert codes(table.warnings) == ["few_rows"]


@pytest.mark.parametrize(
    ("expected", "header"), [("resistivity", "sigma"), ("conductivity", "rho")]
)
def test_rho_and_sigma_each_meet_the_other_expected(expected: Any, header: str) -> None:
    table = parse_table(f"T {header}\n300 1e-5\n400 2e-5\n", expected=expected)
    assert "expected_not_found" not in codes(table.warnings)
    assert "resistivity" in table.measurements


def test_resistivity_loaded_as_itself_says_so() -> None:
    table = parse_table("T S rho RH\n300 1e-4 1e-5 1e-8\n400 2e-4 2e-5 2e-8\n")
    assert table.loaded_as == {
        "seebeck": "seebeck",
        "resistivity": "resistivity",
        "hall": "hall",
    }


@pytest.mark.parametrize("value", ["0", "-2e4", "0.0e0", "1e-400"])
def test_a_conductivity_of_zero_or_below_is_an_error_on_its_line(value: str) -> None:
    table = parse_table(f"T sigma\n300 4e4\n400 {value}\n500 {value}\n")
    assert table.errors == (
        ParseIssue("non_positive_conductivity", 3, 1),
        ParseIssue("non_positive_conductivity", 4, 1),
    )
    assert table.measurements == {}
    assert table.loaded_as == {}


def test_a_conductivity_whose_inverse_overflows_is_an_error() -> None:
    table = parse_table("T sigma\n300 4e4\n400 1e-310\n")
    assert table.errors == (ParseIssue("non_positive_conductivity", 3, 1),)


def test_a_mapping_cannot_hold_both_rho_and_sigma() -> None:
    table = parse_table(
        "a b c\n300 1e-5 1e5\n400 2e-5 5e4\n",
        mapping={0: "temperature", 1: "resistivity", 2: "conductivity"},
    )
    assert table.errors == (ParseIssue("resistivity_and_conductivity", column=2),)
    assert table.measurements == {}

    mended = with_mapping(table, {0: "temperature", 2: "conductivity"})
    assert mended.errors == ()
    assert mended.measurements["resistivity"].values.tolist() == [1.0 / 1e5, 1.0 / 5e4]


def test_a_file_with_rho_and_sigma_headers_keeps_the_first() -> None:
    table = parse_table("T rho sigma\n300 1e-5 1e5\n400 2e-5 5e4\n")
    assert table.mapping == {0: "temperature", 1: "resistivity"}
    assert ParseIssue("repeated_header", column=2) in table.warnings
    assert table.loaded_as["resistivity"] == "resistivity"


def test_an_implausible_conductivity_is_a_warning_on_its_column() -> None:
    # S/cm values of a semiconductor read as S/m would be fine; 1e12 S/m is no measurement.
    table = parse_table("T sigma\n300 1e12\n400 2e12\n")
    assert ParseIssue("implausible_magnitude", column=1) in table.warnings
    assert table.errors == ()


def _fit(resistivity: Any) -> dict[str, float]:
    model = registry.get("dpb")
    mode = next(m for m in model.describe().fit_modes if m.id == "dpb_s_rho")
    seebeck = parse_table(Path(f"{EXAMPLE}_see.txt").read_text(), "seebeck")
    result = model.fit(
        FitRequest(
            "dpb_s_rho",
            {"seebeck": seebeck.measurements["seebeck"], "resistivity": resistivity},
            default_start(mode),
            scattering="acPh",
        ),
        lambda *_: None,
    )
    assert result.status == "converged"
    return dict(result.parameters)


def test_a_fit_from_sigma_is_the_fit_from_one_over_sigma_given_as_rho() -> None:
    """The conductivity is what a lab measured as 1/rho of the example, in S/cm."""
    rows = [line.split() for line in Path(f"{EXAMPLE}_rho.txt").read_text().strip().splitlines()]
    sigma_s_per_cm = [f"{1 / float(rho) / 100:.6e}" for _, rho in rows]
    by_hand = "".join(
        f"{t} {1.0 / (float(sigma) * 100)!r}\n"
        for (t, _), sigma in zip(rows, sigma_s_per_cm, strict=True)
    )
    loaded = parse_table(
        "".join(f"{t} {sigma}\n" for (t, _), sigma in zip(rows, sigma_s_per_cm, strict=True)),
        mapping={0: "temperature", 1: "conductivity"},
        units={1: "S/cm"},
    )
    inverted = parse_table(by_hand, "resistivity")
    original = parse_table(Path(f"{EXAMPLE}_rho.txt").read_text(), "resistivity")
    assert loaded.errors == inverted.errors == ()

    from_sigma = _fit(loaded.measurements["resistivity"])
    from_rho = _fit(inverted.measurements["resistivity"])
    from_original = _fit(original.measurements["resistivity"])

    assert from_sigma.keys() == from_rho.keys()
    for name, value in from_rho.items():
        assert abs(from_sigma[name] - value) <= FIT_TOLERANCE * abs(value), name
        # Seven digits of sigma move the fit no further than the golden tolerance either.
        assert abs(from_sigma[name] - from_original[name]) <= FIT_TOLERANCE * abs(
            from_original[name]
        ), name
