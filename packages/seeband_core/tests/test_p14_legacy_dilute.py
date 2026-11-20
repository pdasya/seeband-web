"""Boltzmann limits through the legacy DPB curve calculations."""

from decimal import Decimal, localcontext

import numpy as np
import pytest
from seeband_core import math_module as te
from seeband_core.fit_module import PB_fit


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("gap", [2950.0, 2990.0])
def test_legacy_intrinsic_dpb_conductivities_keep_representable_values(scattering, gap):
    curves = PB_fit()
    args = (2.0, 2.0, 1, [1.0, gap, 1000.0], [1e6, 1.0, 0.01, 0.01, 1e6, 1.0], 1.0, scattering)
    with np.errstate(over="ignore", divide="ignore"):
        _, sigma = curves.dpb_elecCond_calc(*args)
        _, sigma1, sigma2 = curves.dpb_ind_elecCond_calc(*args)
        _, kappa = curves.dpb_thermCond_calc(*args)

    with localcontext() as context:
        context.prec = 70
        x = -Decimal(str(gap)) / 4
        # At 2 K, the acoustic, disorder and mixed prefactors are A, 2A and 2A/5.
        prefactor = {"acPh": Decimal("1e6"), "dis": Decimal("2e6"), "acPhDis": Decimal("4e5")}
        band_sigma = prefactor[scattering] * x.exp()
        kb_over_e = Decimal(str(te.kB)) / Decimal(str(te.e))
        lorenz = kb_over_e**2 * (2 + (2 - x) ** 2)
        thermal = 2 * (2 * band_sigma) * lorenz
    assert sigma[0] == float(2 * band_sigma)
    assert sigma1[0] == sigma2[0] == float(band_sigma)
    assert kappa[0] == float(thermal)


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("b", [1.0, 1.05])
@pytest.mark.parametrize("n1", [1.0, 3.0])
def test_legacy_intrinsic_dpb_hall_cancels_before_the_inverse_density_scaling(scattering, b, n1):
    with np.errstate(invalid="ignore", over="ignore", divide="ignore"):
        _, _, _, hall = PB_fit().dpb_see_res_hall_calc(
            2.0,
            2.0,
            1,
            [1.0, 2860.0, 1000.0],
            [1e6, b, 0.01, 0.01, 1e6, b],
            1.0,
            1.0,
            scattering,
            band_1_degeneracy=n1,
        )

    # At equal DOS masses and identical temperature laws, the weighted Hall
    # coefficient is the single-band result times (1-B)/(1+B).
    with localcontext() as context:
        context.prec = 70
        band_prefactor = 3 * te.hbar**3 * np.pi**2 / (2 * te.e * (4 * te.kB * te.me) ** 1.5)
        correction = (1 - Decimal(str(b))) / (1 + Decimal(str(b)))
        expected = (
            Decimal(715).exp()
            * Decimal(str(band_prefactor * np.sqrt(np.pi)))
            * correction
            / Decimal(str(n1))
        )
    np.testing.assert_allclose(hall, [float(expected)], rtol=1e-12, atol=0)


@pytest.mark.parametrize("mode", ["dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("scattering", ["acPh", "dis"])
def test_legacy_measured_dpb_resistivity_inverts_the_representable_conductivity(mode, scattering):
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest

    model = registry.get("dpb")
    parameters = {
        "m_eff": 1.0,
        "band_gap": 3000.0,
        "fermi_energy": 0.0,
        "A": 1e22,
        "B": 1.0,
        "C": 0.0,
        "D": 0.0,
        "F": 1e22,
        "G": 1.0,
        "m1": 1.0,
    }
    with np.errstate(divide="ignore"):
        measured = model.calculate(CurveRequest(mode, parameters, 2.0, 2.0, 1, scattering))
        sigma = model.calculate(
            CurveRequest(mode, parameters, 2.0, 2.0, 1, scattering, "electrical_conductivity")
        ).curves["electrical_conductivity_s_per_m"]
    rho = measured.curves["resistivity_ohm_m"]
    with localcontext() as context:
        context.prec = 70
        prefactor = Decimal("2e22") if scattering == "acPh" else Decimal("4e22")
        expected = Decimal(750).exp() / prefactor
    np.testing.assert_allclose(rho, [float(expected)], rtol=1e-12)
    np.testing.assert_allclose(rho * sigma, [1.0], rtol=1e-15)


def test_legacy_measured_dpb_rejects_negative_hall_band_mass():
    with pytest.raises(ValueError, match="band mass"):
        PB_fit().dpb_see_res_hall_calc(
            300.0, 300.0, 1, [1.0, 400.0, 20.0], [1e6, 1.0, 0.0, 0.0, 1e6, 1.0], -1.0, 1.0, "acPh"
        )
