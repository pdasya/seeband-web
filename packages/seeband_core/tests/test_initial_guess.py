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
    assert single_band_guess("spb", np.array([100.0, 200.0, 300.0]), np.array(values)).reason in (
        "sign_change",
        "zero_seebeck",
    )


def test_rejects_too_few_distinct_temperatures():
    assert (
        single_band_guess("spb", np.array([100.0, 100.0, 300.0]), np.full(3, -1e-4)).reason
        == "too_few_temperatures"
    )


@pytest.mark.parametrize("ef", [1500.0, 2500.0])
def test_mott_limit_with_low_temperature_row(ef):
    from scipy.constants import Boltzmann, elementary_charge

    t = np.r_[2.0, np.linspace(100.0, 300.0, 20)]
    s = -(np.pi**2 / 3) * Boltzmann / elementary_charge * t / ef
    estimate = single_band_guess("spb", t, s)
    assert estimate["fermi_energy"] == pytest.approx(ef, rel=0.04)
    assert "low_temperature_omitted" in estimate.warnings


def test_bound_and_large_residual_are_reported():
    result = single_band_guess("spb", np.linspace(100.0, 600.0, 20), np.full(20, -5e-6))
    assert "estimate_at_bound" in result.warnings
    assert "large_estimate_residual" in result.warnings
    assert result.rmse_v_per_k > 20e-6


@pytest.mark.parametrize("ef", [5.0, 20.0])
def test_nondegenerate_limit(ef):
    from scipy.constants import Boltzmann, elementary_charge

    t = np.linspace(100.0, 600.0, 20)
    x = np.log(4 / (3 * np.sqrt(np.pi)) * (ef / t) ** 1.5)
    s = Boltzmann / elementary_charge * (2 - x)
    result = single_band_guess("spb", t, s)
    assert result["fermi_energy"] == pytest.approx(-ef, abs=1)
