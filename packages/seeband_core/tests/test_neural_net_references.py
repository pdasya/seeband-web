import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "neural_net_references.json"
# Order from Models._select_model, modules/neural_nets.py:24-30.
RANGES = [(300, 800), (400, 700), (300, 600), (200, 500), (100, 400)]
DOCUMENT: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = DOCUMENT["cases"]
SELECTED = [case for case in CASES if case["selected_range_k"] is not None]
# The net works in float32, so derived values match to about single precision.
FLOAT32 = 1e-5


def by_name(name: str) -> dict[str, Any]:
    return next(case for case in CASES if case["name"] == name)


def inverse_softsign(y: float, shift: float, factor: float) -> float:
    sign = (y > 0) - (y < 0)
    return (shift + (factor - sign * shift) * y) / (1 - abs(y))


def test_environment_and_sources_are_recorded() -> None:
    for key in ("python", "platform", "tensorflow", "keras", "numpy", "h5py"):
        assert DOCUMENT["environment"][key]
    assert len(DOCUMENT["source"]["commit"]) == 40
    files = DOCUMENT["model_files_sha256"]
    assert len(files) == 10
    assert all(len(digest) == 64 for digest in files.values())


def test_every_network_is_covered() -> None:
    assert {tuple(case["selected_range_k"]) for case in SELECTED} == set(RANGES)


@pytest.mark.parametrize("name", ["02_SiP", "01_reversed_rows"])
def test_no_model_cases_are_covered(name: str) -> None:
    case = by_name(name)
    assert case["selected_range_k"] is None
    assert "prediction" not in case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_selection_follows_first_and_last_rows(case: dict[str, Any]) -> None:
    first, last = case["temperature_k"][0], case["temperature_k"][-1]
    expected = next(([a, b] for a, b in RANGES if first <= a and last >= b), None)
    assert case["selected_range_k"] == expected


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_network_input_follows_the_sign_of_seebeck(case: dict[str, Any]) -> None:
    interpolated = case["interpolated_seebeck_v_per_k"]
    assert len(interpolated) == 7
    sign = 1 if sum(interpolated[:3]) > 0 else -1
    expected = [sign * value * 1e3 for value in interpolated]
    assert case["network_input"] == pytest.approx(expected)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_reversed_norm_follows_network_output(case: dict[str, Any]) -> None:
    mass, gap, fermi = case["network_output"]
    expected = [
        inverse_softsign(mass, 0, 1),
        inverse_softsign(gap, 2000, 1000),
        inverse_softsign(fermi, -500, 1000),
    ]
    assert case["reversed_norm"] == pytest.approx(expected, rel=FLOAT32)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_prediction_is_transformed_for_negative_seebeck(case: dict[str, Any]) -> None:
    mass, gap, fermi = case["reversed_norm"]
    if sum(case["interpolated_seebeck_v_per_k"][:3]) > 0:
        expected = [mass, gap, fermi]
    else:
        expected = [1 / mass, gap, gap - fermi]
    assert case["prediction"] == pytest.approx(expected, rel=FLOAT32)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_start_values_follow_slider_rounding_and_ranges(case: dict[str, Any]) -> None:
    mass, gap, fermi = case["prediction"]
    start = case["desktop_start_values"]
    assert start["m_eff"] == max(-3.0, min(3.0, round(mass * 100) / 100))
    assert start["band_gap_k"] == max(-3000, min(3000, round(gap)))
    assert start["fermi_energy_k"] == max(-3000, min(3000, round(fermi)))


def test_real_examples_keep_their_recorded_results() -> None:
    assert by_name("01_Fe2VAl09Si01")["selected_range_k"] == [400, 700]
    assert by_name("01_Fe2VAl09Si01")["desktop_start_values"] == {
        "m_eff": 1.57,
        "band_gap_k": 554,
        "fermi_energy_k": 1170,
    }
    assert by_name("03_AWI32_SI")["selected_range_k"] == [200, 500]
    assert by_name("03_AWI32_SI")["desktop_start_values"] == {
        "m_eff": 1.22,
        "band_gap_k": 1947,
        "fermi_energy_k": -350,
    }
