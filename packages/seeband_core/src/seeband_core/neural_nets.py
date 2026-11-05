"""Neural net start values for DPB fits, ported from SeeBand modules/neural_nets.py.

Each net is four dense layers, run here with numpy instead of TensorFlow. Every step keeps the
desktop's behaviour, including choosing the net from the first and last rows, which P9 fixes.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import numpy as np
from numpy.polynomial import Chebyshev

from seeband_core import data_processing
from seeband_core.model_interface import FitMode
from seeband_core.model_scales import control_value

# The first range that the data span wins, so the order matters.
NET_RANGES_K = ((300, 800), (400, 700), (300, 600), (200, 500), (100, 400))
NET_INPUT_POINTS = 7
# The default degree of `data_processing.fit_data`, which the nets' input goes through.
SEEBECK_FIT_DEGREE = 5
LAYER_COUNT = 4
LEAKY_RELU_SLOPE = np.float32(0.1)
# The rational approximation that TensorFlow uses for tanh, through Eigen. np.tanh rounds
# differently and reaches 1 only at about 10, where this reaches it at about 7.906.
TANH_CLIP = np.float32(7.90531110763549805)
TANH_NUMERATOR = tuple(
    np.float32(coefficient)
    for coefficient in (
        -2.76076847742355e-16,
        2.00018790482477e-13,
        -8.60467152213735e-11,
        5.12229709037114e-08,
        1.48572235717979e-05,
        6.37261928875436e-04,
        4.89352455891786e-03,
    )
)
TANH_DENOMINATOR = tuple(
    np.float32(coefficient)
    for coefficient in (
        1.19825839466702e-06,
        1.18534705686654e-04,
        2.26843463243900e-03,
        4.89352518554385e-03,
    )
)


@dataclass(frozen=True)
class NeuralNetGuess:
    """The chosen net's range and prediction. Band gap and Fermi energy are in K."""

    range_k: tuple[int, int]
    m_eff: float
    band_gap_k: float
    fermi_energy_k: float


@dataclass(frozen=True)
class NoNeuralNet:
    """No net fits the data. The first and last temperatures are what the choice was based on."""

    first_temperature_k: float
    last_temperature_k: float


def select_range(temperature_k: np.ndarray) -> tuple[int, int] | None:
    """Return the first net range spanned by the first and last rows, or None."""
    for low_k, high_k in NET_RANGES_K:
        if temperature_k[0] <= low_k and temperature_k[-1] >= high_k:
            return low_k, high_k
    return None


def interpolate_seebeck(
    temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray, range_k: tuple[int, int]
) -> np.ndarray:
    """Return Seebeck in V/K at the net's input points, from a polynomial fit of the data."""
    fit = data_processing.fit_data(np.column_stack((temperature_k, seebeck_v_per_k)))
    if fit is None:
        raise ValueError("The Seebeck data could not be fitted")
    points_k = np.linspace(range_k[0], range_k[1], NET_INPUT_POINTS)
    interpolated: np.ndarray = data_processing.interpolate_data(fit, points_k)[:, 1]
    return interpolated


def temperatures_are_sorted(temperature_k: np.ndarray) -> bool:
    """Say whether the rows rise. If not, the first and last rows are not the real span (P9)."""
    return bool(np.all(temperature_k[:-1] <= temperature_k[1:]))


def seebeck_fit_is_underdetermined(temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray) -> bool:
    """Say whether the data leave the polynomial open, which makes its values arbitrary."""
    # With full=True, numpy gives the rank here, and does not warn about it.
    _, (_, rank, _, _) = Chebyshev.fit(
        temperature_k, seebeck_v_per_k, SEEBECK_FIT_DEGREE, full=True
    )
    return bool(rank <= SEEBECK_FIT_DEGREE)


def _seebeck_is_positive(interpolated_v_per_k: np.ndarray) -> bool:
    return bool(np.mean(interpolated_v_per_k[:3]) > 0)


def network_input(interpolated_v_per_k: np.ndarray) -> np.ndarray:
    """Return Seebeck in mV/K, flipped when the first three values are negative on average."""
    if _seebeck_is_positive(interpolated_v_per_k):
        return interpolated_v_per_k * 1e3
    return (-1) * interpolated_v_per_k * 1e3


@lru_cache(maxsize=len(NET_RANGES_K))
def _load_layers(range_k: tuple[int, int]) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    path = resources.files("seeband_core") / "data" / "neural_nets"
    layers = []
    with (path / f"net_{range_k[0]}_{range_k[1]}.npz").open("rb") as file, np.load(file) as weights:
        for index in range(LAYER_COUNT):
            kernel, bias = weights[f"kernel_{index}"], weights[f"bias_{index}"]
            # The cache shares these arrays between calls.
            kernel.flags.writeable = False
            bias.flags.writeable = False
            layers.append((kernel, bias))
    return tuple(layers)


def _tanh(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -TANH_CLIP, TANH_CLIP)
    squared = clipped * clipped
    numerator = TANH_NUMERATOR[0]
    for coefficient in TANH_NUMERATOR[1:]:
        numerator = numerator * squared + coefficient
    denominator = TANH_DENOMINATOR[0]
    for coefficient in TANH_DENOMINATOR[1:]:
        denominator = denominator * squared + coefficient
    result: np.ndarray = numerator * clipped / denominator
    return result


def _sum_with_fused_rounding(values: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Round to float32 only after each multiply and add together."""
    total = np.zeros(kernel.shape[1], dtype=np.float32)
    for value, row in zip(values, kernel, strict=True):
        exact = total.astype(np.float64) + np.float64(value) * row.astype(np.float64)
        total = exact.astype(np.float32)
    return total


def _sum_with_separate_rounding(values: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Round to float32 after each multiply and after each add."""
    total = np.zeros(kernel.shape[1], dtype=np.float32)
    for value, row in zip(values, kernel, strict=True):
        total = total + value * row
    return total


def run_network(range_k: tuple[int, int], input_mv_per_k: np.ndarray) -> np.ndarray:
    """Return the normalised output of a net, in float32 like the desktop's.

    These sums reproduce TensorFlow's rounding, as recorded on one Mac. The @ operator goes through
    BLAS, whose rounding changes with the machine, so results here would too.
    """
    values = input_mv_per_k.astype(np.float32)
    layers = _load_layers(range_k)
    for kernel, bias in layers[:-1]:
        values = _sum_with_fused_rounding(values, kernel) + bias
        values = np.where(values >= 0, values, LEAKY_RELU_SLOPE * values)
    kernel, bias = layers[-1]
    return _tanh(_sum_with_separate_rounding(values, kernel) + bias)


def _inverse_softsign(y: np.float64, shift: float, factor: float) -> np.float64:
    # A numpy scalar, because an output of exactly 1 gives inf on the desktop, not an error.
    result: np.float64 = (shift + (factor - np.sign(y) * shift) * y) / (1 - np.abs(y))
    return result


def reverse_normalisation(output: np.ndarray) -> tuple[np.float64, np.float64, np.float64]:
    """Return mass, gap in K and Fermi energy in K, computed in float64 as on the desktop."""
    mass, gap_k, fermi_energy_k = output.astype(np.float64)
    return (
        _inverse_softsign(mass, 0, 1),
        _inverse_softsign(gap_k, 2000, 1000),
        _inverse_softsign(fermi_energy_k, -500, 1000),
    )


def transform_prediction(
    interpolated_v_per_k: np.ndarray, reversed_norm: tuple[np.float64, np.float64, np.float64]
) -> tuple[np.float64, np.float64, np.float64]:
    """Convert back for negative Seebeck, where the net saw the sign flipped."""
    if _seebeck_is_positive(interpolated_v_per_k):
        return reversed_norm
    mass, gap_k, fermi_energy_k = reversed_norm
    return 1 / mass, gap_k, gap_k - fermi_energy_k


def predict_band_parameters(
    temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray
) -> NeuralNetGuess | NoNeuralNet:
    """Predict DPB start values. Non-finite values can come back in a guess, as on the desktop."""
    range_k = select_range(temperature_k)
    if range_k is None:
        return NoNeuralNet(float(temperature_k[0]), float(temperature_k[-1]))
    interpolated = interpolate_seebeck(temperature_k, seebeck_v_per_k, range_k)
    output = run_network(range_k, network_input(interpolated))
    mass, gap_k, fermi_energy_k = transform_prediction(interpolated, reverse_normalisation(output))
    return NeuralNetGuess(range_k, float(mass), float(gap_k), float(fermi_energy_k))


def start_values(guess: NeuralNetGuess, fit_mode: FitMode) -> dict[str, float] | None:
    """Return the parameters a guess sets in a fit mode, as the desktop's sliders would hold them.

    Returns None if a prediction is not finite, where the desktop's slider code raises.
    """
    prediction = {
        "m_eff": guess.m_eff,
        "band_gap": guess.band_gap_k,
        "fermi_energy": guess.fermi_energy_k,
    }
    if not all(math.isfinite(value) for value in prediction.values()):
        return None
    specs = {spec.name: spec for spec in fit_mode.parameters}
    return {name: control_value(specs[name], value) for name, value in prediction.items()}
