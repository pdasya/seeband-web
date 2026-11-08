import numpy as np
import pytest
from seeband_core import math_module
from seeband_core.initial_guess import single_band_guess


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("energy_k", [10.0, 700.0, 2800.0])
def test_recovers_spb_parameters_from_irregular_reversed_rows(sign, energy_k):
    t = np.array([110.0, 140.0, 210.0, 280.0, 350.0, 460.0, 590.0])[::-1]
    s = math_module.spb_see_vs_temp(t, sign * energy_k, sign * 1.7)
    original_t, original_s = t.copy(), s.copy()
    result = single_band_guess("spb", t, s)
    assert result["fermi_energy"] == pytest.approx(sign * energy_k, abs=1)
    assert result["band_mass"] == sign
    np.testing.assert_array_equal(t, original_t)
    np.testing.assert_array_equal(s, original_s)


@pytest.mark.parametrize("values", [[0.0, 0.0, 0.0], [-1e-4, 0.0, 1e-4]])
def test_rejects_seebeck_without_a_single_band_solution(values):
    with pytest.raises(ValueError):
        single_band_guess("spb", np.array([100.0, 200.0, 300.0]), np.array(values))


def test_rejects_too_few_distinct_temperatures():
    with pytest.raises(ValueError):
        single_band_guess("spb", np.array([100.0, 100.0, 300.0]), np.full(3, -1e-4))
