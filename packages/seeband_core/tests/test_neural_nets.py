import hashlib
import json
import os
import subprocess
import sys
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import data_processing, neural_nets

FIXTURE = Path(__file__).parent / "fixtures" / "neural_net_references.json"
CASES: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
SELECTED = [case for case in CASES if case["selected_range_k"] is not None]
NO_NET = [case for case in CASES if case["selected_range_k"] is None]
BAND_KEYS = ("m_eff", "band_gap_k", "fermi_energy_k")
# docs/neural-net-references.md gives the measured differences behind these.
INTERPOLATION_TOLERANCE = 1e-9
OUTPUT_ABSOLUTE_TOLERANCE = 5e-7
BAND_RELATIVE_TOLERANCE = 1e-5
BAND_ABSOLUTE_TOLERANCE = 1e-3
WEIGHTS_SHA256 = {
    (100, 400): "c46b2f9560f9cf1ecbcaf72806f41f36bd8da26c37e1c11da075e3324485913b",
    (200, 500): "175755f8bc3290aac0efe5c36c836eba3c61c7e58574e181434a6adaefa24b29",
    (300, 600): "679fd73c58b2f59b14f3d1156e04c2851ad765be786c3ef0767382c820169536",
    (300, 800): "9e31f340ba86cc81af2ace50a97542d4e61fe220e0f26d6766db4a70e02f39bc",
    (400, 700): "d014099837ee66d06f1a9f979cfe491850a2c0a94417fdfcd6e5130fc17d0c47",
}
NO_TENSORFLOW = """
import sys
from seeband_core import neural_nets
assert "tensorflow" not in sys.modules
assert "h5py" not in sys.modules
"""


def arrays(case: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    return np.array(case["temperature_k"]), np.array(case["seebeck_v_per_k"])


def band(values: dict[str, float]) -> list[float]:
    return [values[key] for key in BAND_KEYS]


def range_of(case: dict[str, Any]) -> tuple[int, int]:
    low_k, high_k = case["selected_range_k"]
    return low_k, high_k


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_selected_range_matches_the_desktop(case: dict[str, Any]) -> None:
    selected = neural_nets.select_range(arrays(case)[0])
    expected = case["selected_range_k"]
    assert selected == (tuple(expected) if expected else None)


def test_first_matching_range_wins() -> None:
    assert neural_nets.select_range(np.array([100.0, 900.0])) == (300, 800)


def test_selection_reads_only_the_first_and_last_rows() -> None:
    assert neural_nets.select_range(np.array([100.0, 1000.0, 400.0])) == (100, 400)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_each_step_matches_the_desktop(case: dict[str, Any]) -> None:
    temperature_k, seebeck_v_per_k = arrays(case)
    range_k = range_of(case)

    interpolated = neural_nets.interpolate_seebeck(temperature_k, seebeck_v_per_k, range_k)
    assert interpolated == pytest.approx(
        case["interpolated_seebeck_v_per_k"], rel=INTERPOLATION_TOLERANCE
    )

    inputs = neural_nets.network_input(interpolated)
    assert inputs == pytest.approx(case["network_input_mv_per_k"], rel=INTERPOLATION_TOLERANCE)

    output = neural_nets.run_network(range_k, inputs)
    assert output.dtype == np.float32
    assert output == pytest.approx(band(case["network_output"]), abs=OUTPUT_ABSOLUTE_TOLERANCE)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_recorded_output_gives_the_recorded_physical_values_exactly(case: dict[str, Any]) -> None:
    interpolated = np.array(case["interpolated_seebeck_v_per_k"])
    reversed_norm = neural_nets.reverse_normalisation(np.array(band(case["network_output"])))
    assert [float(value) for value in reversed_norm] == pytest.approx(
        band(case["reversed_norm"]), rel=1e-12
    )
    prediction = neural_nets.transform_prediction(interpolated, reversed_norm)
    assert [float(value) for value in prediction] == pytest.approx(
        band(case["prediction"]), rel=1e-12
    )


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_prediction_matches_the_desktop(case: dict[str, Any]) -> None:
    guess = neural_nets.predict_band_parameters(*arrays(case))
    assert isinstance(guess, neural_nets.NeuralNetGuess)
    assert guess.range_k == range_of(case)
    values = [guess.m_eff, guess.band_gap_k, guess.fermi_energy_k]
    assert values == pytest.approx(
        band(case["prediction"]), rel=BAND_RELATIVE_TOLERANCE, abs=BAND_ABSOLUTE_TOLERANCE
    )


@pytest.mark.parametrize("case", NO_NET, ids=lambda case: case["name"])
def test_no_net_is_an_explicit_result(case: dict[str, Any]) -> None:
    result = neural_nets.predict_band_parameters(*arrays(case))
    assert result == neural_nets.NoNeuralNet(case["temperature_k"][0], case["temperature_k"][-1])


def test_every_net_is_compared_with_the_desktop() -> None:
    assert {range_of(case) for case in SELECTED} == set(neural_nets.NET_RANGES_K)


@pytest.mark.parametrize("case", SELECTED[:2], ids=lambda case: case["name"])
def test_inputs_stay_unchanged(case: dict[str, Any]) -> None:
    temperature_k, seebeck_v_per_k = arrays(case)
    neural_nets.predict_band_parameters(temperature_k, seebeck_v_per_k)
    assert temperature_k.tolist() == case["temperature_k"]
    assert seebeck_v_per_k.tolist() == case["seebeck_v_per_k"]


@pytest.mark.filterwarnings("ignore")
def test_saturated_output_gives_infinity_as_on_the_desktop() -> None:
    mass, _, _ = neural_nets.reverse_normalisation(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    assert np.isinf(mass)


def test_failed_interpolation_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_processing, "fit_data", lambda data: None)
    with pytest.raises(ValueError, match="could not be fitted"):
        neural_nets.interpolate_seebeck(np.array([100.0, 400.0]), np.zeros(2), (100, 400))


def test_tensorflow_is_neither_imported_nor_a_dependency(tmp_path: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", NO_TENSORFLOW],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text("utf-8"))
    names = " ".join(project["project"]["dependencies"])
    assert "tensorflow" not in names
    assert "h5py" not in names


@pytest.mark.parametrize("range_k", neural_nets.NET_RANGES_K)
def test_weights_are_unchanged(range_k: tuple[int, int]) -> None:
    name = f"net_{range_k[0]}_{range_k[1]}.npz"
    content = resources.files("seeband_core").joinpath("data", "neural_nets", name).read_bytes()
    assert hashlib.sha256(content).hexdigest() == WEIGHTS_SHA256[range_k]
