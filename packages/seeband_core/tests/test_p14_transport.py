"""Limits and representative DPB cases for stable Fermi-integral transport."""

import numpy as np
import pytest
from seeband_core import math_module as te
from seeband_core.fit_module import PB_fit

SCATTERING = [2.0, 1.0] * 3


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("temperature", [2.0, 50.0, 800.0])
def test_electronic_thermal_conductivity_survives_a_dilute_dpb_band(scattering, temperature):
    _, thermal = PB_fit().dpb_thermCond_calc(
        temperature, temperature, 1, [1.0, 2000.0, -100.0], SCATTERING, 1.0, scattering
    )
    assert np.isfinite(thermal[0])
    assert thermal[0] > 0.0


def test_dilute_single_band_seebeck_has_its_boltzmann_limit():
    temperature = np.array([2.0])
    reduced_potential = -1000.0
    seebeck = te.spb_see_vs_temp(temperature, 0.0, 1.0, potentials=temperature * reduced_potential)
    np.testing.assert_allclose(seebeck, -te.kB / te.e * (2.0 - reduced_potential), rtol=1e-12)


def test_intrinsic_dpb_seebeck_retains_relative_weights_after_both_bands_underflow():
    temperature = np.array([2.0])
    gap = 4000.0
    # At the midpoint of a symmetric gap the carrier densities are equal.
    potential = np.array([gap / 2.0])
    result = te.dpb_see_vs_temp_single_scatter(
        temperature, 1.0, gap, 0.0, 1.0, 2.0, potentials=potential
    )
    expected = -te.kB / te.e * (2.0 + gap / (2.0 * temperature)) / 3.0
    np.testing.assert_allclose(result, expected, rtol=1e-12)


def test_dpb_lorenz_has_a_finite_boltzmann_limit_for_the_empty_band():
    _, lorenz = te.dpb_lorNum_vs_temp(np.array([2.0]), 1.0, 2000.0, -100.0, 1.0)
    np.testing.assert_allclose(lorenz, 2 * (te.kB / te.e) ** 2, rtol=1e-12)


def test_dpb_intrinsic_heat_conductivity_can_round_to_zero():
    _, thermal = PB_fit().dpb_thermCond_calc(
        2.0, 2.0, 1, [1.0, 4000.0, 0.0], SCATTERING, 1.0, "acPh"
    )
    np.testing.assert_array_equal(thermal, [0.0])


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
@pytest.mark.parametrize("gap", [2950.0, 4000.0])
def test_model_lorenz_remains_finite_when_absolute_conductivities_underflow(scattering, gap):
    from seeband_core.band_models import LORENZ_CURVE
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest
    from seeband_core.model_scales import default_start

    model = registry.get("dpb")
    mode = model.describe().fit_mode("dpb_s_rho")
    parameters = default_start(mode) | {
        "m_eff": 1.0,
        "band_gap": gap,
        "fermi_energy": 0.0,
        "A": 10.0,
        "B": 1.0,
        "F": 10.0,
        "G": 1.0,
    }
    with np.errstate(divide="ignore"):
        result = model.calculate(
            CurveRequest(mode.id, parameters, 2, 2, 1, scattering, "lorenz_number")
        )
    moment = 4 if scattering == "ionized" else 2
    expected = (te.kB / te.e) ** 2 * (moment + (moment + gap / 4.0) ** 2)
    np.testing.assert_allclose(result.curves[LORENZ_CURVE], expected, rtol=1e-11)


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_zero_dpb_conductivity_amplitude_gives_zero_heat_conductivity(scattering):
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest
    from seeband_core.model_scales import default_start

    model = registry.get("dpb")
    mode = model.describe().fit_mode("dpb_s_rho")
    parameters = default_start(mode) | {"A": 0.0, "F": 0.0}
    with np.errstate(divide="ignore"):
        result = model.calculate(
            CurveRequest(mode.id, parameters, 2, 800, 5, scattering, "thermal_conductivity")
        )
    np.testing.assert_array_equal(result.curves["thermal_conductivity_w_per_m_k"], np.zeros(5))


def test_signed_relative_amplitude_keeps_the_existing_seebeck_equation():
    temperature = np.array([300.0])
    mass, gap, fermi_energy, relative_amplitude = 1.0, 100.0, -100.0, -0.1
    chemical_potential = te.dpb_chemPot_vs_temp(temperature, gap, mass, fermi_energy, 1.0)[0]
    mu = [chemical_potential, chemical_potential - gap]
    signs = [-1.0, 1.0]
    conductivities = [
        te.sigma_general(x, sign, 1.0, -1.0, 300.0) for x, sign in zip(mu, signs, strict=True)
    ]
    onsager = [
        te.onsi_general(x, sign, 1.0, -1.0, 300.0) for x, sign in zip(mu, signs, strict=True)
    ]
    reference = (onsager[0] + relative_amplitude * onsager[1]) / (
        conductivities[0] + relative_amplitude * conductivities[1]
    )
    actual = te.dpb_see_vs_temp_single_scatter(
        temperature, mass, gap, fermi_energy, 1.0, relative_amplitude
    )
    np.testing.assert_allclose(actual, [reference], rtol=1e-12)
