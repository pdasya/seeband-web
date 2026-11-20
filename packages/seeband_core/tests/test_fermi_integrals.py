import math

import mpmath
import pytest
from seeband_core.fermi_integrals import fermi_integral, scaled_fermi_integral


@pytest.mark.parametrize("order", [-0.5, 0.0, 0.25, 0.5, 1.0, 2.0, 3.5])
@pytest.mark.parametrize(
    "reduced_mu",
    [
        -6000.0,
        -1000.0,
        -746.0,
        -745.2,
        -710.0,
        -700.0,
        -38.01,
        -37.99,
        -10.0,
        -9.90001,
        -9.89999,
        -0.001,
        0.0,
        0.001,
        0.1234,
        19.89999,
        19.90001,
        47.99999,
        48.00001,
        710.0,
        1000.0,
        6000.0,
    ],
)
def test_fermi_integrals_match_high_precision_reference(order: float, reduced_mu: float) -> None:
    with mpmath.workdps(60):
        exponent = mpmath.mpf(order) + 1
        eta = mpmath.mpf(reduced_mu)
        fugacity = mpmath.exp(eta)
        if order == 0.0:
            # mpmath's order-zero integral via polylog loses tiny fugacity.
            raw = mpmath.log1p(fugacity)
        else:
            raw = -mpmath.gamma(exponent) * mpmath.polylog(exponent, -fugacity).real
        expected_scaled = float(raw * mpmath.exp(-min(eta, 0)))
        expected_raw = float(raw)
    assert scaled_fermi_integral(order, reduced_mu) == pytest.approx(
        expected_scaled, rel=1e-12, abs=0.0
    )
    assert fermi_integral(order, reduced_mu) == pytest.approx(expected_raw, rel=1e-12, abs=0.0)


def test_subnormal_integral_survives_underflow_of_boltzmann_factor() -> None:
    eta = -745.2
    assert math.exp(eta) == 0.0
    assert fermi_integral(-0.5, eta) == math.ulp(0.0)


@pytest.mark.parametrize(
    ("order", "boltzmann_moment"),
    [(-0.5, math.sqrt(math.pi)), (0.0, 1.0), (0.5, math.sqrt(math.pi) / 2), (1.0, 1.0), (2.0, 2.0)],
)
def test_scaled_fermi_integral_reaches_boltzmann_limit(
    order: float, boltzmann_moment: float
) -> None:
    assert scaled_fermi_integral(order, -6000.0) == pytest.approx(boltzmann_moment, rel=1e-14)


def test_degenerate_integer_moments_include_thermal_correction() -> None:
    eta = 6000.0
    assert fermi_integral(0.0, eta) == eta
    assert fermi_integral(1.0, eta) == pytest.approx(eta**2 / 2 + math.pi**2 / 6, rel=1e-12)
    assert fermi_integral(2.0, eta) == pytest.approx(eta**3 / 3 + math.pi**2 * eta / 3, rel=1e-12)


@pytest.mark.parametrize("eta", [-38.0, -9.9, 0.0, 0.123, 19.9, 48.0])
def test_half_order_derivative_is_smooth(eta: float) -> None:
    half_step = 1e-4
    derivative = (fermi_integral(0.5, eta + half_step) - fermi_integral(0.5, eta - half_step)) / (
        2 * half_step
    )
    assert derivative == pytest.approx(0.5 * fermi_integral(-0.5, eta), rel=1e-8, abs=0.0)
