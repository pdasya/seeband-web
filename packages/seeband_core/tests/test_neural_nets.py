import ast
import hashlib
import inspect
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
from seeband_core.model_catalog import registry

FIXTURE = Path(__file__).parent / "fixtures" / "neural_net_references.json"
CASES: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
SELECTED = [case for case in CASES if case["selected_range_k"] is not None]
NO_NET = [
    case
    for case in CASES
    if case["selected_range_k"] is None and case["name"] != "01_reversed_rows"
]
P9 = json.loads((FIXTURE.parent / "physics" / "p9.json").read_text())
BAND_KEYS = ("m_eff", "band_gap_k", "fermi_energy_k")
# docs/neural-net-references.md gives the measured differences behind these.
INTERPOLATION_TOLERANCE = 1e-9
BAND_TOLERANCE = 1e-12
# From TensorFlow 2.15.1 on one Mac, for tensors of three values: tf.keras.activations.tanh.
TENSORFLOW_TANH = {
    0.0: "0x0p+0",
    0.5: "0x1.d9353ep-2",
    1.0: "0x1.85efacp-1",
    3.0: "0x1.fd77dp-1",
    7.0: "0x1.ffffc8p-1",
    7.9: "0x1.fffff8p-1",
    7.905: "0x1.fffffcp-1",
    7.906: "0x1p+0",
    9.5: "0x1p+0",
    10.0: "0x1p+0",
    -0.5: "-0x1.d9353ep-2",
    -7.906: "-0x1p+0",
}
WEIGHTS_SHA256 = {
    (100, 400): "c46b2f9560f9cf1ecbcaf72806f41f36bd8da26c37e1c11da075e3324485913b",
    (200, 500): "175755f8bc3290aac0efe5c36c836eba3c61c7e58574e181434a6adaefa24b29",
    (300, 600): "679fd73c58b2f59b14f3d1156e04c2851ad765be786c3ef0767382c820169536",
    (300, 800): "9e31f340ba86cc81af2ace50a97542d4e61fe220e0f26d6766db4a70e02f39bc",
    (400, 700): "d014099837ee66d06f1a9f979cfe491850a2c0a94417fdfcd6e5130fc17d0c47",
}
HEAVY_PACKAGES = {"tensorflow", "keras", "h5py"}
RUN_A_NET_WITHOUT_HEAVY_PACKAGES = """
import sys
import numpy as np
from seeband_core import neural_nets
temperature_k = np.linspace(100.0, 800.0, 8)
guess = neural_nets.predict_band_parameters(temperature_k, 1e-7 * temperature_k)
assert guess.range_k == (300, 800)
assert not {"tensorflow", "keras", "h5py"} & set(sys.modules)
"""


def arrays(case: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    return np.array(case["temperature_k"]), np.array(case["seebeck_v_per_k"])


def band(values: dict[str, float]) -> list[float]:
    return [values[key] for key in BAND_KEYS]


def range_of(case: dict[str, Any]) -> tuple[int, int]:
    low_k, high_k = case["selected_range_k"]
    return low_k, high_k


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_selected_range_matches_desktop_or_documented_p9_correction(case: dict[str, Any]) -> None:
    selected = neural_nets.select_range(arrays(case)[0])
    expected = P9["overrides"].get(case["name"], case)["selected_range_k"]
    assert selected == (tuple(expected) if expected else None)


@pytest.mark.parametrize(
    ("first_k", "last_k", "expected"),
    [
        (100.0, 900.0, (300, 800)),
        (300.0, 700.0, (400, 700)),
        (200.0, 600.0, (300, 600)),
        (200.0, 500.0, (200, 500)),
        (100.0, 400.0, (100, 400)),
        (300.0, 800.0, (300, 800)),
        (300.0, 799.0, (400, 700)),
    ],
)
def test_first_matching_range_wins(
    first_k: float, last_k: float, expected: tuple[int, int]
) -> None:
    assert neural_nets.select_range(np.array([first_k, last_k])) == expected


def test_selection_uses_real_extrema_instead_of_endpoint_rows() -> None:
    assert neural_nets.select_range(np.array([100.0, 1000.0, 400.0])) == (300, 800)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
@pytest.mark.parametrize("permutation", ["reversed", "shuffled"])
def test_prediction_is_independent_of_paired_row_order(case, permutation):
    temperature_k, seebeck = arrays(case)
    order = (
        np.arange(len(temperature_k))[::-1]
        if permutation == "reversed"
        else np.random.default_rng(9).permutation(len(temperature_k))
    )
    temperatures, values = temperature_k[order], seebeck[order]
    before_t, before_s = temperatures.copy(), values.copy()
    guess = neural_nets.predict_band_parameters(temperatures, values)
    assert isinstance(guess, neural_nets.NeuralNetGuess)
    assert guess.range_k == range_of(case)
    assert [guess.m_eff, guess.band_gap_k, guess.fermi_energy_k] == pytest.approx(
        band(case["prediction"]), rel=BAND_TOLERANCE
    )
    np.testing.assert_array_equal(temperatures, before_t)
    np.testing.assert_array_equal(values, before_s)


def test_unsorted_no_net_reports_real_coverage():
    result = neural_nets.predict_band_parameters(
        np.array([500.0, 350.0, 450.0]), np.array([1e-5, 2e-5, 3e-5])
    )
    assert result == neural_nets.NoNeuralNet(350.0, 500.0)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_each_step_matches_the_desktop(case: dict[str, Any]) -> None:
    temperature_k, seebeck_v_per_k = arrays(case)
    range_k = range_of(case)

    interpolated = neural_nets.interpolate_seebeck(temperature_k, seebeck_v_per_k, range_k)
    assert interpolated == pytest.approx(
        case["interpolated_seebeck_v_per_k"], rel=INTERPOLATION_TOLERANCE, abs=0
    )

    inputs = neural_nets.network_input(interpolated)
    assert inputs == pytest.approx(
        case["network_input_mv_per_k"], rel=INTERPOLATION_TOLERANCE, abs=0
    )

    output = neural_nets.run_network(range_k, inputs)
    assert output.dtype == np.float32
    assert output.tolist() == band(case["network_output"])


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
    assert values == pytest.approx(band(case["prediction"]), rel=BAND_TOLERANCE)


@pytest.mark.parametrize("case", NO_NET, ids=lambda case: case["name"])
def test_no_net_is_an_explicit_result(case: dict[str, Any]) -> None:
    result = neural_nets.predict_band_parameters(*arrays(case))
    assert result == neural_nets.NoNeuralNet(case["temperature_k"][0], case["temperature_k"][-1])


def test_every_net_is_compared_with_the_desktop() -> None:
    assert {range_of(case) for case in SELECTED} == set(neural_nets.NET_RANGES_K)


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_inputs_stay_unchanged(case: dict[str, Any]) -> None:
    temperature_k, seebeck_v_per_k = arrays(case)
    neural_nets.predict_band_parameters(temperature_k, seebeck_v_per_k)
    assert temperature_k.tolist() == case["temperature_k"]
    assert seebeck_v_per_k.tolist() == case["seebeck_v_per_k"]


@pytest.mark.parametrize(
    ("millivolts", "flipped"),
    [
        ([3.0, -1.0, -1.0, -9.0, -9.0, -9.0, -9.0], False),
        ([-1.0, 0.0, 2.0, 9.0, 9.0, 9.0, 9.0], False),
        ([-3.0, 1.0, 1.0, 9.0, 9.0, 9.0, 9.0], True),
        ([-1.0, 0.0, 1.0, 9.0, 9.0, 9.0, 9.0], True),
    ],
)
def test_sign_follows_the_mean_of_the_first_three_values(
    millivolts: list[float], flipped: bool
) -> None:
    seebeck_mv_per_k = np.array(millivolts)
    inputs = neural_nets.network_input(seebeck_mv_per_k * 1e-3)
    expected = -seebeck_mv_per_k if flipped else seebeck_mv_per_k
    assert inputs == pytest.approx(expected)


@pytest.mark.parametrize(("value", "expected"), TENSORFLOW_TANH.items())
def test_tanh_matches_tensorflow_exactly(value: float, expected: str) -> None:
    result = neural_nets._tanh(np.array([value], dtype=np.float32))
    assert result.dtype == np.float32
    assert float(result[0]) == float.fromhex(expected)


@pytest.mark.filterwarnings("ignore")
def test_saturated_outputs_give_infinity_as_on_the_desktop() -> None:
    saturated = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    mass, gap_k, fermi_energy_k = neural_nets.reverse_normalisation(saturated)
    assert (mass, gap_k, fermi_energy_k) == (np.inf, np.inf, np.inf)
    negative_seebeck = np.array([-1.0, -1.0, -1.0])
    prediction = neural_nets.transform_prediction(negative_seebeck, (mass, gap_k, fermi_energy_k))
    assert prediction[0] == 0.0
    assert prediction[1] == np.inf
    assert np.isnan(prediction[2])


def start_values(case: dict[str, Any]) -> dict[str, float]:
    start = case["desktop_start_values"]
    return {
        "m_eff": start["m_eff"],
        "band_gap": start["band_gap_k"],
        "fermi_energy": start["fermi_energy_k"],
    }


@pytest.mark.parametrize("case", SELECTED, ids=lambda case: case["name"])
def test_start_values_are_what_the_desktop_sliders_hold(case: dict[str, Any]) -> None:
    guess = neural_nets.predict_band_parameters(*arrays(case))
    assert isinstance(guess, neural_nets.NeuralNetGuess)
    for fit_mode in registry.get("dpb").describe().fit_modes:
        assert neural_nets.start_values(guess, fit_mode) == start_values(case)


@pytest.mark.parametrize(
    ("m_eff", "band_gap_k", "fermi_energy_k"),
    [
        (float("inf"), 1.0, 1.0),
        (float("-inf"), 1.0, 1.0),
        (float("nan"), 1.0, 1.0),
        (1.0, float("inf"), 1.0),
        (1.0, float("nan"), 1.0),
        (1.0, 1.0, float("inf")),
        (1.0, 1.0, float("nan")),
    ],
)
def test_prediction_that_is_not_finite_gives_no_start_values(
    m_eff: float, band_gap_k: float, fermi_energy_k: float
) -> None:
    guess = neural_nets.NeuralNetGuess((100, 400), m_eff, band_gap_k, fermi_energy_k)
    fit_mode = registry.get("dpb").describe().fit_modes[0]
    assert neural_nets.start_values(guess, fit_mode) is None


def test_start_values_are_rounded_and_limited_one_by_one() -> None:
    guess = neural_nets.NeuralNetGuess((100, 400), -4.5, 2.5, -3000.6)
    fit_mode = registry.get("dpb").describe().fit_modes[0]
    assert neural_nets.start_values(guess, fit_mode) == {
        "m_eff": -3.0,
        "band_gap": 2.0,
        "fermi_energy": -3000.0,
    }


def test_sliders_can_round_a_small_m_eff_to_zero() -> None:
    guess = neural_nets.NeuralNetGuess((100, 400), -0.004, 1.0, 1.0)
    fit_mode = registry.get("dpb").describe().fit_modes[0]
    start = neural_nets.start_values(guess, fit_mode)
    assert start is not None
    assert str(start["m_eff"]) == "0.0"


@pytest.mark.parametrize(
    ("temperature_k", "expected"),
    [
        ([300.0], True),
        ([100.0, 100.0, 200.0], True),
        ([100.0, 200.0, 150.0], False),
        ([200.0, 100.0], False),
    ],
)
def test_sorted_rows_rise_or_stay(temperature_k: list[float], expected: bool) -> None:
    assert neural_nets.temperatures_are_sorted(np.array(temperature_k)) is expected


@pytest.mark.parametrize(
    ("temperature_k", "expected"),
    [
        ([100.0, 400.0], True),
        ([100.0, 150.0, 200.0, 300.0, 400.0], True),
        ([100.0, 150.0, 200.0, 300.0, 300.0, 400.0], True),
        ([100.0, 150.0, 200.0, 250.0, 300.0, 400.0], False),
    ],
)
def test_fit_needs_six_distinct_temperatures(temperature_k: list[float], expected: bool) -> None:
    seebeck_v_per_k = 1e-6 * np.array(temperature_k)
    temperatures = np.array(temperature_k)
    assert neural_nets.seebeck_fit_is_underdetermined(temperatures, seebeck_v_per_k) is expected


def test_degree_of_the_check_is_that_of_the_fit() -> None:
    default = inspect.signature(data_processing.fit_data).parameters["degree"].default
    assert neural_nets.SEEBECK_FIT_DEGREE == default


def test_cached_weights_cannot_be_changed() -> None:
    kernel, bias = neural_nets._load_layers((100, 400))[0]
    assert not kernel.flags.writeable
    assert not bias.flags.writeable


def test_failed_interpolation_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_processing, "fit_data", lambda data: None)
    with pytest.raises(ValueError, match="could not be fitted"):
        neural_nets.interpolate_seebeck(np.array([100.0, 400.0]), np.zeros(2), (100, 400))


def test_running_a_net_loads_no_heavy_package(tmp_path: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", RUN_A_NET_WITHOUT_HEAVY_PACKAGES],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def imported_packages(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name.partition(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.partition(".")[0])
    return names


def test_core_imports_no_heavy_package() -> None:
    package = resources.files("seeband_core")
    for path in package.iterdir():
        if path.name.endswith(".py"):
            assert not HEAVY_PACKAGES & imported_packages(path.read_text("utf-8")), path.name


def test_heavy_packages_are_not_dependencies() -> None:
    root = Path(__file__).parents[3]
    lock = tomllib.loads((root / "uv.lock").read_text("utf-8"))
    locked = {package["name"] for package in lock["package"]}
    assert not HEAVY_PACKAGES & locked


@pytest.mark.parametrize("range_k", neural_nets.NET_RANGES_K)
def test_weights_are_unchanged(range_k: tuple[int, int]) -> None:
    name = f"net_{range_k[0]}_{range_k[1]}.npz"
    content = resources.files("seeband_core").joinpath("data", "neural_nets", name).read_bytes()
    assert hashlib.sha256(content).hexdigest() == WEIGHTS_SHA256[range_k]


def test_p9_corrected_reversed_case_preserves_desktop_evidence():
    assert P9["desktop_reference_sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    for name, expected in P9["overrides"].items():
        original = next(case for case in CASES if case["name"] == name)
        reference = next(case for case in CASES if case["name"] == expected["reference_case"])
        assert expected["prediction"] == reference["prediction"]
        assert expected["selected_range_k"] == reference["selected_range_k"]
        guess = neural_nets.predict_band_parameters(*arrays(original))
        assert isinstance(guess, neural_nets.NeuralNetGuess)
        assert [guess.m_eff, guess.band_gap_k, guess.fermi_energy_k] == pytest.approx(
            band(expected["prediction"]), rel=BAND_TOLERANCE
        )
