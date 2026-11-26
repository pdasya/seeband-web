"""Hall moments checked against independently evaluated Fermi integrals."""

import mpmath as mp
import numpy as np
import pytest
from seeband_core import math_module as mm
from seeband_core.transport import band_transport, fermi_integral


@pytest.mark.parametrize("scattering_lambda", [0.0, 2.0])
@pytest.mark.parametrize(
    "eta",
    [-700.0, -40.0, -6.0, -2.0, 0.0, 3.0, 10.0, 47.9999, 48.0, 48.0001, 60.0, 1000.0, 1e5],
)
def test_hall_moment_matches_unnormalized_fermi_integral(eta, scattering_lambda):
    temperature = np.array([300.0])
    _, _, _, weighted_hall = band_transport(
        temperature, np.array([eta]), 1.0, scattering_lambda, weighted_hall=True
    )
    factor = 3 * mm.hbar**3 * np.pi**2 / (mm.e * (2 * mm.kB * mm.me) ** 1.5)
    # Undo the public weighted Hall normalization to expose the scaled moment.
    actual = (
        -weighted_hall[0]
        / (factor * temperature[0] ** -1.5)
        / np.exp(min(eta, 0.0))
        * (scattering_lambda + 1.0) ** 2
    )
    with mp.workdps(60):
        power = mp.mpf(2) * scattering_lambda + mp.mpf("0.5")
        # Integration by parts: J_H=power*F_(power-1). In particular,
        # lambda=0 gives F_(-1/2)/2, with no Gamma normalization in F.
        expected = float(
            mp.re(-mp.gamma(power + 1) * mp.polylog(power, -mp.exp(eta))) / mp.exp(min(eta, 0.0))
        )
    assert actual == pytest.approx(expected, rel=1e-10, abs=0.0)
    if scattering_lambda == 0.0:
        assert fermi_integral(-0.5, eta) == pytest.approx(
            2 * expected * np.exp(min(eta, 0.0)), rel=1e-10, abs=0.0
        )


@pytest.mark.parametrize("scattering_lambda", [0.0, 2.0])
def test_weighted_hall_matches_finite_unweighted_hall_at_extreme_potentials(scattering_lambda):
    eta = np.array([-700.0, 0.0, 48.0, 60.0, 1e5])
    temperature = np.full(eta.size, 300.0)
    integral, seebeck, lorenz, hall = band_transport(temperature, eta, 1.0, scattering_lambda)
    weighted_hall = band_transport(temperature, eta, 1.0, scattering_lambda, weighted_hall=True)[3]
    assert np.isfinite([integral, seebeck, lorenz, hall, weighted_hall]).all()
    # Divide sequentially: integral**2 underflows in the depleted band.
    np.testing.assert_allclose(weighted_hall / integral / integral, hall, rtol=1e-12)
