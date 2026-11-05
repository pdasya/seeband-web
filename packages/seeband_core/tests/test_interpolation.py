import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import data_processing
from seeband_core.data_parser import parse_table
from seeband_core.interpolation import in_fit_range, interpolate, interpolation_grid_k
from seeband_core.model_interface import Measurement

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCES: dict[str, Any] = json.loads(
    (FIXTURES / "interpolation_references.json").read_text("utf-8")
)
# Set from the largest difference measured: see docs/interpolation.md.
TOLERANCE = 1e-9


def example(name: str) -> Measurement:
    kind = {"see": "seebeck", "rho": "resistivity", "hall": "hall"}[name.rsplit("_", 1)[1]]
    text = (FIXTURES / "examples" / f"{name}.txt").read_text(encoding="utf-8")
    return parse_table(text, kind).measurements[kind]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "case",
    REFERENCES["cases"],
    ids=lambda case: f"{case['file']}-{case['min_k']}-{case['max_k']}",
)
def test_matches_the_desktop(case: dict[str, Any]) -> None:
    measurement = example(case["file"].removesuffix(".txt"))
    result = interpolate(measurement, case["min_k"], case["max_k"])
    assert result.measurement.temperature_k.tolist() == case["temperature_k"]
    assert result.measurement.values == pytest.approx(case["values"], rel=TOLERANCE)


def test_references_cover_every_example_and_range() -> None:
    assert len(REFERENCES["cases"]) == 36
    assert {case["file"] for case in REFERENCES["cases"]} == {
        path.name for path in (FIXTURES / "examples").glob("*.txt")
    }


@pytest.mark.parametrize(
    ("low", "high", "points"), [(50, 800, 37), (100, 500, 20), (0.5, 100, 4), (100, 120, 1)]
)
def test_the_grid_has_the_desktop_number_of_points(low: float, high: float, points: int) -> None:
    grid = interpolation_grid_k(low, high)
    assert len(grid) == points
    assert grid[0] == low


def test_the_grid_ends_at_both_limits() -> None:
    grid = interpolation_grid_k(50, 800)
    assert (grid[0], grid[-1]) == (50.0, 800.0)


@pytest.mark.parametrize(("low", "high"), [(100, 100), (200, 100), (100, 119)])
def test_a_range_too_narrow_is_an_error(low: float, high: float) -> None:
    with pytest.raises(ValueError, match="fit range"):
        interpolation_grid_k(low, high)


def test_extrapolation_is_reported() -> None:
    # This file covers 25 to 725 K or so, so 50 to 800 K runs past its end.
    measurement = example("01_Fe2VAl09Si01_see")
    assert interpolate(measurement, 50, 800).extrapolated
    assert not interpolate(measurement, 100, 500).extrapolated
    assert interpolate(measurement, 5, 240).extrapolated


def test_too_few_temperatures_are_reported() -> None:
    measurement = example("02_SiP_hall")
    assert np.unique(measurement.temperature_k).size <= 10
    assert interpolate(measurement, 310, 600).underdetermined
    assert not interpolate(example("01_Fe2VAl09Si01_see"), 100, 500).underdetermined


def test_a_measurement_stays_unchanged() -> None:
    measurement = example("01_Fe2VAl09Si01_see")
    before = measurement.values.copy()
    interpolate(measurement, 100, 500)
    in_fit_range(measurement, 100, 500)
    assert np.array_equal(measurement.values, before)


def test_bad_data_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="finite"):
        interpolate(Measurement(np.array([1.0, np.nan]), np.ones(2)), 100, 500)
    monkeypatch.setattr(data_processing, "fit_data", lambda data, degree: None)
    with pytest.raises(ValueError, match="could not be fitted"):
        interpolate(Measurement(np.array([1.0, 2.0]), np.ones(2)), 100, 500)


def test_the_polynomial_has_degree_ten() -> None:
    temperature_k = np.linspace(100, 800, 40)
    values = (temperature_k / 800) ** 10
    result = interpolate(Measurement(temperature_k, values), 100, 800)
    expected = (result.measurement.temperature_k / 800) ** 10
    assert result.measurement.values == pytest.approx(expected, rel=1e-9)
    too_high = (temperature_k / 800) ** 12
    worse = interpolate(Measurement(temperature_k, too_high), 100, 800)
    assert worse.measurement.values != pytest.approx(
        (result.measurement.temperature_k / 800) ** 12, rel=1e-9
    )


def test_fit_range_keeps_the_points_the_desktop_fitted() -> None:
    document = json.loads((FIXTURES / "golden" / "03_AWI32_SI.json").read_text("utf-8"))
    call = next(c for r in document["runs"] for c in r["calls"] if c["function"] == "spb_see_fit")
    result = in_fit_range(example("03_AWI32_SI_see"), 50, 800)
    assert result.temperature_k.tolist() == call["args"][0]
    assert result.values.tolist() == call["args"][1]


def test_fit_range_includes_both_limits() -> None:
    measurement = Measurement(np.array([1.0, 2.0, 3.0, 4.0]), np.arange(4.0))
    assert in_fit_range(measurement, 2.0, 3.0).temperature_k.tolist() == [2.0, 3.0]
