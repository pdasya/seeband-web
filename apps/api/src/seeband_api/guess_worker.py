"""What runs in a worker process for `POST /api/guess`. It holds no state between calls."""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from seeband_core.initial_guess import NumericalEstimate, single_band_guess
from seeband_core.model_catalog import registry
from seeband_core.neural_nets import (
    NeuralNetGuess,
    NoNeuralNet,
    predict_band_parameters,
    seebeck_fit_is_underdetermined,
    start_values,
    temperatures_are_sorted,
)

from seeband_api.calc_worker import CalculationFailed


@dataclass(frozen=True, eq=False)
class GuessOutcome:
    """`start_values` is None for no net, and for a prediction that is not finite."""

    result: NeuralNetGuess | NoNeuralNet
    start_values: Mapping[str, float] | None
    unsorted_temperature: bool
    underdetermined_fit: bool


def guess(model_id: str, temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray) -> GuessOutcome:
    """Returns the neural net's guess. The route has checked that the model has one."""
    # The guess sets the same parameters, with the same controls, in every fit mode of a model.
    fit_mode = registry.get(model_id).describe().fit_modes[0]
    unsorted_temperature = not temperatures_are_sorted(temperature_k)
    try:
        result = predict_band_parameters(temperature_k, seebeck_v_per_k)
        if isinstance(result, NoNeuralNet):
            return GuessOutcome(result, None, unsorted_temperature, False)
        return GuessOutcome(
            result,
            start_values(result, fit_mode),
            unsorted_temperature,
            seebeck_fit_is_underdetermined(temperature_k, seebeck_v_per_k),
        )
    except (ArithmeticError, ValueError) as error:
        raise CalculationFailed(type(error).__name__) from error


def numerical_guess(
    model_id: str, temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray
) -> NumericalEstimate:
    """Keep numerical failures within the public calculation-error contract."""
    try:
        return single_band_guess(model_id, temperature_k, seebeck_v_per_k)
    except (ArithmeticError, ValueError) as error:
        raise CalculationFailed(type(error).__name__) from error
