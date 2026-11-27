"""Model Lorenz moments, independent of the absolute conductivity amplitude."""

import math

import numpy as np
import pytest
from seeband_core.band_models import LORENZ_BAND_CURVES, LORENZ_CURVE
from seeband_core.math_module import e, kB
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import default_start

# L in units of (k_B/e)², where its limits are pure numbers.
UNIT = (kB / e) ** 2


def _curve(model_id: str, mode_id: str, scattering: str, kind: str, **changes: float):
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(mode_id)
    low, high = changes.pop("low", 100.0), changes.pop("high", 800.0)
    n2 = changes.pop("n2", 1.0)
    parameters = default_start(fit_mode) | changes
    return model.calculate(
        CurveRequest(
            mode_id,
            parameters,
            low,
            high,
            5,
            scattering,
            kind,  # type: ignore[arg-type]
            band_2_degeneracy=n2,
        )
    )


@pytest.mark.parametrize("scattering", ["acPh", "dis"])
def test_one_band_reaches_2_when_nondegenerate_and_pi2_over_3_when_degenerate(
    scattering: str,
) -> None:
    """The limits of L for an energy-independent mean free path, Kim et al. (2015)."""
    # E_F just inside the band, at temperatures far above it: η → 0⁺, then far below it: η from
    # 300 to 600, short of the λ = 0 integrals' overflow above about 709.
    nondegenerate = _curve(
        "spb",
        "spb_s_rho",
        scattering,
        "lorenz_number",
        band_mass=1.0,
        fermi_energy=1e-3,
        low=1000.0,
        high=3000.0,
    )
    degenerate = _curve(
        "spb",
        "spb_s_rho",
        scattering,
        "lorenz_number",
        band_mass=1.0,
        fermi_energy=6000.0,
        low=10.0,
        high=20.0,
    )
    assert np.asarray(nondegenerate.curves[LORENZ_CURVE]) / UNIT == pytest.approx(2.0, rel=1e-4)
    assert np.asarray(degenerate.curves[LORENZ_CURVE]) / UNIT == pytest.approx(
        math.pi**2 / 3, rel=1e-4
    )


def test_ionized_impurities_reach_their_own_nondegenerate_limit_and_pi2_over_3() -> None:
    """With τ ∝ E^(3/2), L is 4 (k_B/e)² when nondegenerate; the degenerate limit is the same."""
    nondegenerate = _curve(
        "spb",
        "spb_s_rho",
        "ionized",
        "lorenz_number",
        band_mass=1.0,
        fermi_energy=1e-3,
        low=1000.0,
        high=3000.0,
    )
    degenerate = _curve(
        "spb",
        "spb_s_rho",
        "ionized",
        "lorenz_number",
        band_mass=1.0,
        fermi_energy=6000.0,
        low=10.0,
        high=20.0,
    )
    assert np.asarray(nondegenerate.curves[LORENZ_CURVE]) / UNIT == pytest.approx(4.0, rel=1e-4)
    assert np.asarray(degenerate.curves[LORENZ_CURVE]) / UNIT == pytest.approx(
        math.pi**2 / 3, rel=1e-3
    )


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis", "ionized"])
def test_one_band_l_is_kappa_over_sigma_t(scattering: str) -> None:
    lorenz = _curve("spb", "spb_s_rho", scattering, "lorenz_number", C=0.1)
    kappa = _curve("spb", "spb_s_rho", scattering, "thermal_conductivity", C=0.1)
    sigma = _curve("spb", "spb_s_rho", scattering, "electrical_conductivity", C=0.1)
    expected = np.asarray(kappa.curves["thermal_conductivity_w_per_m_k"]) / (
        np.asarray(sigma.curves["electrical_conductivity_s_per_m"]) * lorenz.temperature_k
    )
    np.testing.assert_allclose(lorenz.curves[LORENZ_CURVE], expected, rtol=1e-12)
    assert set(lorenz.curves) == {LORENZ_CURVE}


@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis", "ionized"])
def test_two_bands_give_the_effective_l_and_each_band_s(scattering: str) -> None:
    """κ_e = T (L₁σ₁ + L₂σ₂) plus a bipolar part that is not negative, so L ≥ the σ-weighted L.

    With acPhDis and C ≠ D, band 2's weight varies with T, which a constant B would miss.
    """

    def curve(kind):
        return _curve("dpb", "dpb_s_rho", scattering, kind, B=2.3, G=0.4, C=0.1, D=5.0, n2=3)

    lorenz = curve("lorenz_number")
    sigma = curve("electrical_conductivity_by_band")
    s1, s2 = (
        np.asarray(sigma.curves[name])
        for name in (
            "electrical_conductivity_band_1_s_per_m",
            "electrical_conductivity_band_2_s_per_m",
        )
    )
    l1, l2 = (np.asarray(lorenz.curves[name]) for name in LORENZ_BAND_CURVES)
    weighted = (l1 * s1 + l2 * s2) / (s1 + s2)
    effective = np.asarray(lorenz.curves[LORENZ_CURVE])
    assert set(lorenz.curves) == {LORENZ_CURVE, *LORENZ_BAND_CURVES}
    assert np.all(effective >= weighted * (1 - 1e-12))
    thermal = curve("thermal_conductivity").curves["thermal_conductivity_w_per_m_k"]
    np.testing.assert_allclose(effective * (s1 + s2) * lorenz.temperature_k, thermal, rtol=1e-12)
    # Each band alone is a parabolic band, so its L lies between the limits of its scattering.
    low, high = sorted((4.0 if scattering == "ionized" else 2.0, math.pi**2 / 3))
    for band in (l1, l2):
        assert np.all((band / UNIT > low - 1e-9) & (band / UNIT < high + 1e-9))


@pytest.mark.parametrize(
    ("model_id", "scattering"),
    [("spb", "acPh"), ("dpb", "acPh"), ("dpb", "dis"), ("dpb", "ionized")],
)
def test_lorenz_moments_survive_conductivity_underflow(model_id, scattering):
    # A subnormal amplitude: σ and κ_e underflow, but L does not depend on the amplitude.
    amplitude = {"F" if scattering == "dis" else "A": 1e-320}
    if model_id == "spb":
        parameters = {"band_mass": 1.0, "fermi_energy": 1e-6}
        expected = UNIT * 2.0
    else:
        # Symmetric intrinsic bands have equal unit-amplitude conductivities. A relative weight
        # of 3 gives weights 1/4 and 3/4, even after absolute underflow. Each band is
        # nondegenerate with η = −1000, so L_i = λ + 2 and S_i = ±(λ + 2 + 1000).
        lam = 2.0 if scattering == "ionized" else 0.0
        parameters = {"m_eff": 1.0, "band_gap": 4000.0, "fermi_energy": 0.0, "B": 3.0, "G": 3.0}
        expected = UNIT * (lam + 2 + 3.0 / 16.0 * (2 * (lam + 2 + 1000.0)) ** 2)
    with np.errstate(all="ignore"):
        result = _curve(
            model_id,
            f"{model_id}_s_rho",
            scattering,
            "lorenz_number",
            **parameters,
            **amplitude,
            low=2.0,
            high=2.0,
        )
    np.testing.assert_allclose(result.curves[LORENZ_CURVE], expected, rtol=1e-8)


def test_zero_conductivity_leaves_only_individual_band_moments():
    with np.errstate(all="ignore"):
        result = _curve("dpb", "dpb_s_rho", "acPh", "lorenz_number", A=0.0)
    assert np.isnan(result.curves[LORENZ_CURVE]).all()
    assert all(np.isfinite(result.curves[name]).all() for name in LORENZ_BAND_CURVES)


@pytest.mark.parametrize("amplitude", [0.0, math.nan, math.inf])
@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_an_undefined_conductivity_leaves_the_effective_l_undefined(model_id, amplitude):
    # σ and κ_e are zero, undefined or infinite, so κ_e/(σT) has no value either.
    with np.errstate(all="ignore"):
        result = _curve(model_id, f"{model_id}_s_rho", "acPh", "lorenz_number", A=amplitude)
    assert np.isnan(result.curves[LORENZ_CURVE]).all()


def test_a_mechanism_without_lorenz_moments_is_refused():
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    request = CurveRequest(
        fit_mode.id, default_start(fit_mode), 100, 300, 3, "acPh", "lorenz_number"
    )
    # Not a declared mechanism: it must not get the moments of another one.
    with pytest.raises(ValueError, match="No Lorenz moments"):
        model._lorenz_number(request, fit_mode, "unknown")
