"""Neural net start values for DPB fits, ported from SeeBand modules/neural_nets.py.

Each net is four dense layers, run here with numpy instead of TensorFlow. Every step keeps the
desktop's behaviour, including choosing the net from the first and last rows, which P9 fixes.
"""

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import numpy as np

from seeband_core import data_processing

# The first range that the data span wins, so the order matters.
NET_RANGES_K = ((300, 800), (400, 700), (300, 600), (200, 500), (100, 400))
NET_INPUT_POINTS = 7
LAYER_COUNT = 4
LEAKY_RELU_SLOPE = np.float32(0.1)


@dataclass(frozen=True)
class NeuralNetGuess:
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
    for low_k, high_k in NET_RANGES_K:
        if temperature_k[0] <= low_k and temperature_k[-1] >= high_k:
            return low_k, high_k
    return None


def interpolate_seebeck(
    temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray, range_k: tuple[int, int]
) -> np.ndarray:
    fit = data_processing.fit_data(np.column_stack((temperature_k, seebeck_v_per_k)))
    if fit is None:
        raise ValueError("The Seebeck data could not be fitted")
    points_k = np.linspace(range_k[0], range_k[1], NET_INPUT_POINTS)
    interpolated: np.ndarray = data_processing.interpolate_data(fit, points_k)[:, 1]
    return interpolated


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
    with (path / f"net_{range_k[0]}_{range_k[1]}.npz").open("rb") as file, np.load(file) as weights:
        return tuple(
            (weights[f"kernel_{index}"], weights[f"bias_{index}"]) for index in range(LAYER_COUNT)
        )


def run_network(range_k: tuple[int, int], input_mv_per_k: np.ndarray) -> np.ndarray:
    """Return the normalised output of a net, in float32 like the desktop's."""
    values = input_mv_per_k.astype(np.float32)
    layers = _load_layers(range_k)
    for kernel, bias in layers[:-1]:
        values = values @ kernel + bias
        values = np.where(values >= 0, values, LEAKY_RELU_SLOPE * values)
    kernel, bias = layers[-1]
    output: np.ndarray = np.tanh(values @ kernel + bias)
    return output


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
    if _seebeck_is_positive(interpolated_v_per_k):
        return reversed_norm
    mass, gap_k, fermi_energy_k = reversed_norm
    return 1 / mass, gap_k, gap_k - fermi_energy_k


def predict_band_parameters(
    temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray
) -> NeuralNetGuess | NoNeuralNet:
    range_k = select_range(temperature_k)
    if range_k is None:
        return NoNeuralNet(float(temperature_k[0]), float(temperature_k[-1]))
    interpolated = interpolate_seebeck(temperature_k, seebeck_v_per_k, range_k)
    output = run_network(range_k, network_input(interpolated))
    mass, gap_k, fermi_energy_k = transform_prediction(interpolated, reverse_normalisation(output))
    return NeuralNetGuess(range_k, float(mass), float(gap_k), float(fermi_energy_k))
