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
P7: dict[str, Any] = json.loads((FIXTURES / "physics" / "p7.json").read_text("utf-8"))
# A share of the largest value of each case, because single values pass through zero. Set from the
# largest difference measured: see docs/interpolation.md.
TOLERANCE = 1e-9


def example(name: str) -> Measurement:
    kind = {"see": "seebeck", "rho": "resistivity", "hall": "hall"}[name.rsplit("_", 1)[1]]
    text = (FIXTURES / "examples" / f"{name}.txt").read_text(encoding="utf-8")
    return parse_table(text, kind).measurements[kind]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in REFERENCES["cases"]
        if case["min_k"] >= example(case["file"].removesuffix(".txt")).temperature_k.min()
        and case["max_k"] <= example(case["file"].removesuffix(".txt")).temperature_k.max()
    ],
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
    "case", P7["cases"], ids=lambda case: f"{case['file']}-{case['min_k']}-{case['max_k']}"
)
def test_p7_regression_outputs(case: dict[str, Any]) -> None:
    measurement = example(case["file"].removesuffix(".txt"))
    if "error" in case:
        with pytest.raises(ValueError, match=case["error"]):
            interpolate(measurement, case["min_k"], case["max_k"])
        return
    result = interpolate(measurement, case["min_k"], case["max_k"])
    assert result.measurement.temperature_k.tolist() == case["temperature_k"]
    recorded = np.array(case["values"])
    np.testing.assert_allclose(
        result.measurement.values, recorded, rtol=0, atol=TOLERANCE * np.max(np.abs(recorded))
    )
    assert result.range_limited is case["range_limited"]
    assert result.extrapolated is False
    assert result.measured_points_in_range == case["measured_points_in_range"]
    assert result.underdetermined is case["underdetermined"]
    assert np.all(result.measurement.temperature_k >= measurement.temperature_k.min())
    assert np.all(result.measurement.temperature_k <= measurement.temperature_k.max())


def test_p7_covers_original_cases_without_replacing_desktop_evidence() -> None:
    assert (
        P7["desktop_reference_sha256"]
        == hashlib.sha256((FIXTURES / "interpolation_references.json").read_bytes()).hexdigest()
    )
    keys = ("file", "file_sha256", "min_k", "max_k")
    assert [tuple(case[key] for key in keys) for case in P7["cases"]] == [
        tuple(case[key] for key in keys) for case in REFERENCES["cases"]
    ]


@pytest.mark.parametrize(
    ("low", "high", "message"),
    [
        (1, 80, "no usable overlap"),
        (200, 400, "no usable overlap"),
        (100, 200, "no usable overlap"),
        (180, 240, "at least 20"),
    ],
)
def test_unusable_measured_overlap_is_refused(low: float, high: float, message: str) -> None:
    measurement = linear([200, 220, 250, 300])
    if low == 180:
        measurement = linear([221, 250, 300])
    elif low == 200:
        measurement = linear([100, 150, 200])
    with pytest.raises(ValueError, match=message):
        interpolate(measurement, low, high)


def test_sparse_internal_window_is_interpolated_without_source_points() -> None:
    result = interpolate(linear([100, 500]), 200, 400)
    assert result.measured_points_in_range == 0
    assert result.underdetermined
    assert not result.range_limited
    assert not result.extrapolated
    assert result.measurement.temperature_k.tolist() == np.linspace(200, 400, 10).tolist()


def test_overlap_does_not_change_all_measurement_polynomial_inputs() -> None:
    from numpy.polynomial import Chebyshev

    measurement = example("01_Fe2VAl09Si01_see")
    result = interpolate(measurement, 50, 800)
    polynomial = Chebyshev.fit(measurement.temperature_k, measurement.values, 10)
    np.testing.assert_array_equal(
        result.measurement.values, polynomial(result.measurement.temperature_k)
    )


def test_unsorted_duplicate_inputs_and_fractional_limits_stay_in_bounds() -> None:
    measurement = linear([750.3, 25.1, 400.2, 750.3, 200.4])
    temperature_before = measurement.temperature_k.copy()
    values_before = measurement.values.copy()
    result = interpolate(measurement, 5.3, 800.7)
    assert result.measurement.temperature_k[0] == 25.1
    assert result.measurement.temperature_k[-1] == 750.3
    assert np.all(result.measurement.temperature_k >= 25.1)
    assert np.all(result.measurement.temperature_k <= 750.3)
    np.testing.assert_array_equal(measurement.temperature_k, temperature_before)
    np.testing.assert_array_equal(measurement.values, values_before)


def test_invalid_original_range_is_not_rescued_by_clipping() -> None:
    with pytest.raises(ValueError, match="too wide"):
        interpolate(linear([100, 200]), 1, 1e11)


def test_twenty_kelvin_overlap_keeps_the_desktop_one_point_grid() -> None:
    result = interpolate(linear([200, 220, 250]), 100, 220)
    assert result.measurement.temperature_k.tolist() == [200.0]
    assert result.range_limited
    assert not result.extrapolated


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


def test_requested_range_stops_at_measured_seebeck_limit() -> None:
    measurement = linear(np.linspace(25.0, 750.0, 30).tolist())
    result = interpolate(measurement, 50.0, 800.0)

    assert result.measurement.temperature_k[0] == 50.0
    assert result.measurement.temperature_k[-1] == 750.0
    assert np.all(result.measurement.temperature_k <= 750.0)
    assert len(result.measurement.temperature_k) == 35


def test_range_limiting_is_reported_at_either_end_and_not_at_the_limits() -> None:
    temperature_k = [100.0 + 20.0 * index for index in range(21)]
    measurement = linear(temperature_k)
    assert not interpolate(measurement, 100.0, 500.0).extrapolated
    assert not interpolate(measurement, 100.0, 500.0).range_limited
    for low, high in [(99.0, 500.0), (100.0, 501.0), (99.0, 501.0)]:
        result = interpolate(measurement, low, high)
        assert result.range_limited
        assert not result.extrapolated
        assert result.measurement.temperature_k.tolist() == np.linspace(100, 500, 20).tolist()
    assert not interpolate(measurement, 101.0, 499.0).range_limited


def test_a_range_with_no_data_says_so() -> None:
    measurement = linear([100.0 + 20.0 * index for index in range(21)])
    assert interpolate(measurement, 100.0, 500.0).measured_points_in_range == 21
    assert interpolate(measurement, 100.0, 140.0).measured_points_in_range == 3
    with pytest.raises(ValueError, match="no usable overlap"):
        interpolate(measurement, 600.0, 800.0)


def test_the_real_case_of_invented_data_is_refused() -> None:
    with pytest.raises(ValueError, match="no usable overlap"):
        interpolate(example("03_AWI32_SI_hall"), 5, 240)


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
        interpolate(Measurement(np.array([100.0, 200.0]), np.ones(2)), 100, 500)


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
