"""Independent carrier-density and Putley checks for the P2 Hall correction."""

import numpy as np
import pytest
from scipy.constants import Boltzmann, elementary_charge, hbar, m_e
from scipy.integrate import quad
from scipy.special import expit
from seeband_core import math_module as math


def integral(order: float, eta: float) -> float:
    # x = u**2 removes the integrable singularity of F_{-1/2} at x=0.
    return quad(lambda u: 2 * u ** (2 * order + 1) * expit(eta - u * u), 0, np.inf)[0]


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("degeneracy", [1.0, 3.0])
@pytest.mark.parametrize("weight", [0.0, 0.8])
def test_hall_matches_independent_putley_sum(scattering, degeneracy, weight):
    temperature = np.array([50.0, 300.0, 800.0])
    eta1 = np.array([100.0, 2.0, -4.0])
    eta2 = np.array([-6.0, -1.0, 3.0])
    mass, ratio, a, c, d = 1.4, 1.2, 60000.0, 150.0, 600.0
    f0 = [np.logaddexp(0, eta) for eta in (eta1, eta2)]
    fm = [np.array([integral(-0.5, x) for x in eta]) for eta in (eta1, eta2)]
    if scattering == "acPh":
        sigma1, sigma2 = a * f0[0], a * weight / ratio * f0[1]
        rho = math.dpb_rho_vs_temp_acPh(temperature, *f0, a, weight, ratio)
        actual = math.dpb_hall_vs_temp_acPh(
            temperature, rho, *fm, ratio, degeneracy, a, weight, mass**1.5
        )
    elif scattering == "dis":
        sigma1 = a * temperature * f0[0]
        sigma2 = a * temperature * weight / ratio * f0[1]
        rho = math.dpb_rho_vs_temp_dis(temperature, *f0, a, weight, ratio)
        actual = math.dpb_hall_vs_temp_dis(
            temperature, rho, *fm, ratio, degeneracy, a, weight, mass**1.5
        )
    else:
        sigma1 = a * temperature / (c + temperature) * f0[0]
        sigma2 = a * temperature * weight / ratio / (d + temperature) * f0[1]
        rho = math.dpb_rho_vs_temp_acPh_dis(temperature, *f0, a, weight, c, d, ratio)
        actual = math.dpb_hall_vs_temp_acPh_dis(
            temperature, rho, *fm, ratio, degeneracy, a, weight, c, d, mass**1.5
        )
    hall = []
    for eta, effective_mass, valleys, sign in (
        (eta1, mass, 1, 1),
        (eta2, mass * ratio * degeneracy, degeneracy, -1),
    ):
        half = np.array([integral(0.5, x) for x in eta])
        minus_half = np.array([integral(-0.5, x) for x in eta])
        density = (
            valleys
            * (2 * effective_mass * m_e * Boltzmann * temperature) ** 1.5
            / (2 * np.pi**2 * hbar**3)
            * half
        )
        hall_factor = 0.75 * half * minus_half / np.logaddexp(0, eta) ** 2
        hall.append(sign * hall_factor / (elementary_charge * density))
    reference = (hall[0] * sigma1**2 + hall[1] * sigma2**2) / (sigma1 + sigma2) ** 2
    np.testing.assert_allclose(actual, reference, rtol=1e-5, atol=0)


@pytest.mark.parametrize("eta, expected", [(-15.0, 3 * np.pi / 8), (100.0, 1.0)])
def test_single_band_hall_factor_limits(eta, expected):
    factor = 0.75 * integral(0.5, eta) * integral(-0.5, eta) / np.logaddexp(0, eta) ** 2
    assert factor == pytest.approx(expected, rel=1e-3)
    # SPB's formula agrees at the same reduced potential; P12 is separate.
    temperature = np.array([300.0])
    density = (2 * m_e * Boltzmann * temperature) ** 1.5 / (2 * np.pi**2 * hbar**3)
    density *= integral(0.5, eta)
    hall = math.spb_hall_vs_temp(temperature, -eta * 300.0, -1.0, 1.0)
    np.testing.assert_allclose(hall * density * elementary_charge, factor, rtol=1e-5)
