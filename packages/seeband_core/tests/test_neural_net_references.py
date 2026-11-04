import json
from fractions import Fraction
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "neural_net_references.json"
# Order from Models._select_model, modules/neural_nets.py:24-30.
RANGES = [(300, 800), (400, 700), (300, 600), (200, 500), (100, 400)]
DOCUMENT: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = DOCUMENT["cases"]
SELECTED = [case for case in CASES if case["selected_range_k"] is not None]
BAND_KEYS = ("m_eff", "band_gap_k", "fermi_energy_k")
# Network output is float32, but later steps ran in float64, so they recompute exactly.
EXACT = 1e-12
INTERPOLATION_DEGREE = 5
SEEBECK_V_PER_K_FLOOR = 1e-12

# Written separately from the fixture so that a regeneration that changes results fails.
# case: (network output, m_eff, band gap in K, Fermi energy in K)
EXPECTED = {
    "01_Fe2VAl09Si01": ((0.3886, -0.59119, -0.10378), 1.57, 554, 1170),
    "03_AWI32_SI": ((0.54976, -0.05022, 0.13015), 1.22, 1947, -350),
    "03_negated_seebeck": ((0.54976, -0.05022, 0.13015), 0.82, 1947, 2298),
    "synthetic_300_800": ((0.84051, 0.98057, -0.20795), 3.0, 3000, -763),
    "synthetic_400_700": ((0.84934, 0.95391, -0.35099), 3.0, 3000, -1041),
    "synthetic_300_600": ((0.77675, 0.37211, -0.36967), 3.0, 2593, -1086),
    "synthetic_200_500": ((0.80518, -0.56537, -0.31169), 3.0, 699, -953),
    "synthetic_100_400": ((0.675, -0.66705, -0.13092), 2.08, -3, -651),
}


def by_name(name: str) -> dict[str, Any]:
    return next(case for case in CASES if case["name"] == name)


def band(values: dict[str, float]) -> list[float]:
    return [values[key] for key in BAND_KEYS]


def inverse_softsign(y: float, shift: float, factor: float) -> float:
    sign = (y > 0) - (y < 0)
    return (shift + (factor - sign * shift) * y) / (1 - abs(y))


def least_squares_polynomial(xs: list[float], ys: list[float], degree: int) -> list[Fraction]:
    """Solve the normal equations exactly, so the result does not depend on numpy."""
    size = degree + 1
    fx = [Fraction(x) for x in xs]
    fy = [Fraction(y) for y in ys]
    powers = [sum(x**k for x in fx) for k in range(2 * degree + 1)]
    matrix = [[powers[row + col] for col in range(size)] for row in range(size)]
    right = [sum(y * x**row for x, y in zip(fx, fy, strict=True)) for row in range(size)]
    for pivot in range(size):
        best = next(row for row in range(pivot, size) if matrix[row][pivot] != 0)
        matrix[pivot], matrix[best] = matrix[best], matrix[pivot]
        right[pivot], right[best] = right[best], right[pivot]
        for row in range(pivot + 1, size):
            factor = matrix[row][pivot] / matrix[pivot][pivot]
            for col in range(pivot, size):
                matrix[row][col] -= factor * matrix[pivot][col]
            right[row] -= factor * right[pivot]
    solution = [Fraction(0)] * size
    for row in reversed(range(size)):
        known = sum(matrix[row][col] * solution[col] for col in range(row + 1, size))
        solution[row] = (right[row] - known) / matrix[row][row]
    return solution


def test_environment_and_sources_are_recorded() -> None:
    for key in ("python", "platform", "tensorflow", "keras", "numpy", "h5py"):
        assert DOCUMENT["environment"][key]
    files = DOCUMENT["model_files_sha256"]
    assert len(files) == 10
    assert all(len(digest) == 64 for digest in files.values())


def test_source_commit_matches_the_desktop_table() -> None:
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    assert DOCUMENT["source"]["commit"] == table["source"]["commit"]


def test_every_network_is_covered() -> None:
    assert {tuple(case["selected_range_k"]) for case in SELECTED} == set(RANGES)


@pytest.mark.parametrize("name", ["02_SiP", "01_reversed_rows"])
def test_no_model_cases_use_fresh_session_defaults(name: str) -> None:
    case = by_name(name)
    assert case["selected_range_k"] is None
    assert "prediction" not in case
    assert case["start_value_source"] == "fresh_session_defaults"

    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    for mode in table["modes"]:
        if mode["model"] == "DPB":
            parameters = {p["name"]: p for p in mode["parameters"]}
            start = case["desktop_start_values"]
            m_eff = parameters["m_eff"]
            assert start["m_eff"] == m_eff["slider"]["default"] * m_eff["fit_scale"]
            assert start["band_gap_k"] == parameters["band_gap"]["slider"]["default"]
            assert start["fermi_energy_k"] == parameters["fermi_energy"]["slider"]["default"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_selection_follows_first_and_last_rows(case: dict[str, Any]) -> None:
    first, last = case["temperature_k"][0], case["temperature_k"][-1]
    expected = next(([a, b] for a, b in RANGES if first <= a and last >= b), None)
    assert case["selected_range_k"] == expected


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_interpolation_follows_the_measurements(case: dict[str, Any]) -> None:
    low, high = case["selected_range_k"]
    coefficients = least_squares_polynomial(
        case["temperature_k"], case["seebeck_v_per_k"], INTERPOLATION_DEGREE
    )
    grid = [Fraction(low) + Fraction(high - low, 6) * step for step in range(7)]
    expected = [float(sum(c * x**k for k, c in enumerate(coefficients))) for x in grid]
    assert case["interpolated_seebeck_v_per_k"] == pytest.approx(
        expected, rel=EXACT, abs=SEEBECK_V_PER_K_FLOOR
    )


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_network_input_follows_the_sign_of_seebeck(case: dict[str, Any]) -> None:
    interpolated = case["interpolated_seebeck_v_per_k"]
    sign = 1 if sum(interpolated[:3]) > 0 else -1
    expected = [sign * value * 1e3 for value in interpolated]
    assert case["network_input_mv_per_k"] == pytest.approx(expected, rel=EXACT)


def test_negating_seebeck_gives_the_same_network_output() -> None:
    assert (
        by_name("03_negated_seebeck")["network_output"] == by_name("03_AWI32_SI")["network_output"]
    )


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_reversed_norm_follows_network_output(case: dict[str, Any]) -> None:
    mass, gap, fermi = band(case["network_output"])
    expected = [
        inverse_softsign(mass, 0, 1),
        inverse_softsign(gap, 2000, 1000),
        inverse_softsign(fermi, -500, 1000),
    ]
    assert band(case["reversed_norm"]) == pytest.approx(expected, rel=EXACT)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_prediction_is_transformed_for_negative_seebeck(case: dict[str, Any]) -> None:
    mass, gap, fermi = band(case["reversed_norm"])
    if sum(case["interpolated_seebeck_v_per_k"][:3]) > 0:
        expected = [mass, gap, fermi]
    else:
        expected = [1 / mass, gap, gap - fermi]
    assert band(case["prediction"]) == pytest.approx(expected, rel=EXACT)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_start_values_follow_slider_rounding_and_ranges(case: dict[str, Any]) -> None:
    mass, gap, fermi = band(case["prediction"])
    start = case["desktop_start_values"]
    assert case["start_value_source"] == "neural_net"
    assert start["m_eff"] == max(-3.0, min(3.0, round(mass * 100) / 100))
    assert start["band_gap_k"] == max(-3000, min(3000, round(gap)))
    assert start["fermi_energy_k"] == max(-3000, min(3000, round(fermi)))


def test_every_selected_case_is_pinned() -> None:
    assert {case["name"] for case in SELECTED} == set(EXPECTED)


@pytest.mark.parametrize("name", EXPECTED)
def test_results_match_recorded_values(name: str) -> None:
    case = by_name(name)
    output, m_eff, band_gap_k, fermi_energy_k = EXPECTED[name]
    assert band(case["network_output"]) == pytest.approx(output, abs=1e-5)
    assert case["desktop_start_values"] == {
        "m_eff": m_eff,
        "band_gap_k": band_gap_k,
        "fermi_energy_k": fermi_energy_k,
    }
