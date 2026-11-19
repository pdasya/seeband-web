"""Independent carrier-density and Putley checks for the P2 Hall correction."""

import numpy as np
import pytest
from scipy.constants import Boltzmann, elementary_charge, hbar, m_e
from scipy.integrate import quad
from scipy.special import expit
from seeband_core import math_module as math
from seeband_core.band_models import DpbModel
from seeband_core.fit_quality import curve_rmse
from seeband_core.model_interface import CurveRequest, FitRequest, Measurement
from seeband_core.model_scales import default_start


def integral(order: float, eta: float) -> float:
    # x = u**2 removes the integrable singularity of F_{-1/2} at x=0.
    return quad(lambda u: 2 * u ** (2 * order + 1) * expit(eta - u * u), 0, np.inf)[0]


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize(("n1", "n2"), [(1.0, 1.0), (1.0, 3.0), (2.5, 7.5)])
@pytest.mark.parametrize("weight", [0.0, 0.8])
def test_hall_matches_independent_putley_sum(scattering, n1, n2, weight):
    temperature = np.array([50.0, 300.0, 800.0])
    eta1 = np.array([100.0, 2.0, -4.0])
    eta2 = np.array([-6.0, -1.0, 3.0])
    mass, ratio, a, c, d = 1.4, 1.2, 60000.0, 150.0, 600.0
    degeneracy = n2 / n1
    f0 = [np.logaddexp(0, eta) for eta in (eta1, eta2)]
    fm = [np.array([integral(-0.5, x) for x in eta]) for eta in (eta1, eta2)]
    if scattering == "acPh":
        sigma1, sigma2 = a * f0[0], a * weight / ratio * f0[1]
        rho = math.dpb_rho_vs_temp_acPh(temperature, *f0, a, weight, ratio)
        actual = math.dpb_hall_vs_temp_acPh(
            temperature, rho, *fm, ratio, degeneracy, a, weight, mass**1.5, band_1_degeneracy=n1
        )
    elif scattering == "dis":
        sigma1 = a * temperature * f0[0]
        sigma2 = a * temperature * weight / ratio * f0[1]
        rho = math.dpb_rho_vs_temp_dis(temperature, *f0, a, weight, ratio)
        actual = math.dpb_hall_vs_temp_dis(
            temperature, rho, *fm, ratio, degeneracy, a, weight, mass**1.5, band_1_degeneracy=n1
        )
    else:
        sigma1 = a * temperature / (c + temperature) * f0[0]
        sigma2 = a * temperature * weight / ratio / (d + temperature) * f0[1]
        rho = math.dpb_rho_vs_temp_acPh_dis(temperature, *f0, a, weight, c, d, ratio)
        actual = math.dpb_hall_vs_temp_acPh_dis(
            temperature,
            rho,
            *fm,
            ratio,
            degeneracy,
            a,
            weight,
            c,
            d,
            mass**1.5,
            band_1_degeneracy=n1,
        )
    hall = []
    for eta, effective_mass, valleys, sign in (
        (eta1, mass, n1, 1),
        (eta2, mass * ratio * degeneracy, n2, -1),
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
    # Choose the zero-temperature Fermi energy whose conserved density gives this eta.
    temperature = np.array([300.0])
    density = (2 * m_e * Boltzmann * temperature) ** 1.5 / (2 * np.pi**2 * hbar**3)
    density *= integral(0.5, eta)
    fermi_energy = -300.0 * (1.5 * integral(0.5, eta)) ** (2 / 3)
    hall = math.spb_hall_vs_temp(temperature, fermi_energy, -1.0, 1.0)
    np.testing.assert_allclose(hall * density * elementary_charge, factor, rtol=1e-5)


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_dpb_calculation_uses_absolute_degeneracy_for_hall_and_density(scattering):
    model = DpbModel()
    mode_id = "dpb_s_rho_rh"
    parameters = default_start(model.describe().fit_mode(mode_id)) | {"m1": 1.4}
    n1, n2 = 2.5, 7.5
    for kind in ("measured", "carrier_concentration_by_band"):
        ratio_only = model.calculate(
            CurveRequest(mode_id, parameters, 150, 650, 6, scattering, kind, 1.0, n2 / n1)
        )
        absolute = model.calculate(
            CurveRequest(mode_id, parameters, 150, 650, 6, scattering, kind, n1, n2)
        )
        for name, values in ratio_only.curves.items():
            if kind == "carrier_concentration_by_band":
                expected = values * n1
            elif name == "hall_m3_per_c":
                expected = values / n1
            else:
                expected = values
            np.testing.assert_allclose(absolute.curves[name], expected, rtol=1e-12)


@pytest.mark.parametrize(
    ("scattering", "algorithm"),
    [
        ("acPh", "verified-sequential-v2"),
        ("dis", "verified-sequential-v2"),
        ("ionized", "verified-sequential-v2"),
        ("acPh", "legacy-sequential-v1"),
    ],
)
def test_dpb_hall_fit_recovers_per_valley_mass(scattering, algorithm):
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s_rho_rh")
    parameters = default_start(mode) | {"m1": 1.4}
    n1, n2 = 2.0, 2.0
    synthetic = model.calculate(CurveRequest(mode.id, parameters, 150, 650, 6, scattering))
    data = {
        q: Measurement(synthetic.temperature_k, synthetic.curves[key] / divisor)
        for q, key, divisor in (
            ("seebeck", "seebeck_v_per_k", 1.0),
            ("resistivity", "resistivity_ohm_m", 1.0),
            ("hall", "hall_m3_per_c", n1),
        )
    }
    held = frozenset(p.name for p in mode.parameters_for(scattering) if p.role == "fitted") - {"m1"}
    result = model.fit(
        FitRequest(
            mode.id,
            data,
            parameters | {"m1": 1.0},
            scattering=scattering,
            band_1_degeneracy=n1,
            band_2_degeneracy=n2,
            held=held,
            algorithm=algorithm,
        )
    )
    assert result.status == "converged"
    assert result.parameters["m1"] == pytest.approx(parameters["m1"], rel=1e-8)
    if result.diagnostics is not None:
        assert result.diagnostics.residuals["hall"].relative_l2 == pytest.approx(0.0, abs=1e-8)
    errors = curve_rmse(model, mode.id, result.parameters, data, scattering, n1, n2)
    assert errors["hall"].value == pytest.approx(0.0, abs=1e-6)
