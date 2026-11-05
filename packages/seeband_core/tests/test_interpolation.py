import hashlib
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import interpolation
from seeband_core.data_parser import parse_table
from seeband_core.interpolation import in_fit_range, interpolate, interpolation_grid_k
from seeband_core.model_interface import Measurement

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCES: dict[str, Any] = json.loads(
    (FIXTURES / "interpolation_references.json").read_text("utf-8")
)
# A share of the largest value of each case, because single values pass through zero. Set from the
# largest difference measured: see docs/interpolation.md.
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
    recorded = np.array(case["values"])
    limit = TOLERANCE * np.max(np.abs(recorded))
    assert np.max(np.abs(result.measurement.values - recorded)) <= limit


def test_references_cover_every_example_and_range() -> None:
    assert len(REFERENCES["cases"]) == 36
    for case in REFERENCES["cases"]:
        content = (FIXTURES / "examples" / case["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == case["file_sha256"]
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


@pytest.mark.parametrize(
    ("low", "high", "message"),
    [
        (100, 100, "below its maximum"),
        (200, 100, "below its maximum"),
        (100, 119, "at least 20"),
        (0, 100, "above 0 K"),
        (-40, 100, "above 0 K"),
        (float("nan"), 100, "finite"),
        (100, float("inf"), "finite"),
        (1, 1e11, "too wide"),
    ],
)
def test_a_range_it_cannot_use_is_an_error(low: float, high: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        interpolation_grid_k(low, high)


def linear(temperature_k: list[float]) -> Measurement:
    values = np.array(temperature_k)
    return Measurement(values, 1e-6 * values)


def test_extrapolation_is_reported_at_either_end_and_not_at_the_limits() -> None:
    temperature_k = [100.0 + 20.0 * index for index in range(21)]
    measurement = linear(temperature_k)
    assert not interpolate(measurement, 100.0, 500.0).extrapolated
    assert interpolate(measurement, 99.0, 500.0).extrapolated
    assert interpolate(measurement, 100.0, 501.0).extrapolated
    assert not interpolate(measurement, 101.0, 499.0).extrapolated


def test_a_range_with_no_data_says_so() -> None:
    measurement = linear([100.0 + 20.0 * index for index in range(21)])
    assert interpolate(measurement, 100.0, 500.0).measured_points_in_range == 21
    assert interpolate(measurement, 100.0, 140.0).measured_points_in_range == 3
    away = interpolate(measurement, 600.0, 800.0)
    assert away.measured_points_in_range == 0
    assert away.extrapolated


def test_the_real_case_of_invented_data_is_reported() -> None:
    result = interpolate(example("03_AWI32_SI_hall"), 5, 240)
    assert result.measured_points_in_range == 0
    assert result.extrapolated


@pytest.mark.parametrize(("count", "expected"), [(9, True), (10, True), (11, False), (12, False)])
def test_too_few_temperatures_are_reported(count: int, expected: bool) -> None:
    measurement = linear([100.0 + 50.0 * index for index in range(count)])
    assert interpolate(measurement, 100.0, 300.0).underdetermined is expected


def test_duplicates_do_not_count_as_temperatures() -> None:
    temperature_k = [100.0 + 50.0 * (index % 5) for index in range(30)]
    assert interpolate(linear(temperature_k), 100.0, 300.0).underdetermined


def test_clustered_temperatures_count_as_too_few() -> None:
    clustered = [100.0 + 1e-6 * index for index in range(10)] + [500.0]
    assert interpolate(linear(clustered), 100.0, 300.0).underdetermined


def test_the_real_short_file_is_reported() -> None:
    assert interpolate(example("02_SiP_hall"), 310, 600).underdetermined
    assert not interpolate(example("01_Fe2VAl09Si01_see"), 100, 500).underdetermined


def test_interpolating_gives_no_warnings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        interpolate(example("02_SiP_hall"), 310, 600)


def test_a_measurement_stays_unchanged() -> None:
    measurement = example("01_Fe2VAl09Si01_see")
    shuffled = Measurement(measurement.temperature_k[::-1].copy(), measurement.values[::-1].copy())
    temperature_before = shuffled.temperature_k.copy()
    values_before = shuffled.values.copy()
    interpolate(shuffled, 100, 500)
    in_fit_range(shuffled, 100, 500)
    assert np.array_equal(shuffled.temperature_k, temperature_before)
    assert np.array_equal(shuffled.values, values_before)


def test_bad_data_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="finite"):
        interpolate(Measurement(np.array([1.0, np.nan]), np.ones(2)), 100, 500)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise np.linalg.LinAlgError

    monkeypatch.setattr(interpolation.Chebyshev, "fit", fail)
    with pytest.raises(ValueError, match="could not be fitted"):
        interpolate(Measurement(np.array([1.0, 2.0]), np.ones(2)), 100, 500)


@pytest.mark.parametrize(("power", "exact"), [(10, True), (11, False), (9, True)])
def test_the_polynomial_has_degree_ten(power: int, exact: bool) -> None:
    temperature_k = np.linspace(100, 800, 40)
    result = interpolate(Measurement(temperature_k, (temperature_k / 800) ** power), 100, 800)
    expected = (result.measurement.temperature_k / 800) ** power
    difference = np.max(np.abs(result.measurement.values - expected))
    assert bool(difference < 1e-9) is exact


def test_fit_range_keeps_the_points_the_desktop_fitted() -> None:
    document = json.loads((FIXTURES / "golden" / "03_AWI32_SI.json").read_text("utf-8"))
    call = next(c for r in document["runs"] for c in r["calls"] if c["function"] == "spb_see_fit")
    result = in_fit_range(example("03_AWI32_SI_see"), 50, 800)
    assert result.temperature_k.tolist() == call["args"][0]
    assert result.values.tolist() == call["args"][1]


def test_fit_range_includes_both_limits() -> None:
    measurement = Measurement(np.array([1.0, 2.0, 3.0, 4.0]), np.arange(4.0))
    assert in_fit_range(measurement, 2.0, 3.0).temperature_k.tolist() == [2.0, 3.0]
