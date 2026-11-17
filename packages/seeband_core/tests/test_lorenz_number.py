"""R11: the Lorenz number L(T), which κ_e already holds, as a curve of its own."""

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


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_one_band_l_is_kappa_over_sigma_t(scattering: str) -> None:
    lorenz = _curve("spb", "spb_s_rho", scattering, "lorenz_number")
    kappa = _curve("spb", "spb_s_rho", scattering, "thermal_conductivity")
    sigma = _curve("spb", "spb_s_rho", scattering, "electrical_conductivity")
    expected = np.asarray(kappa.curves["thermal_conductivity_w_per_m_k"]) / (
        np.asarray(sigma.curves["electrical_conductivity_s_per_m"]) * lorenz.temperature_k
    )
    assert np.asarray(lorenz.curves[LORENZ_CURVE]).tobytes() == expected.tobytes()
    assert set(lorenz.curves) == {LORENZ_CURVE}


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_two_bands_give_the_effective_l_and_each_band_s(scattering: str) -> None:
    """κ_e = T (L₁σ₁ + L₂σ₂) plus a bipolar part that is not negative, so L ≥ the σ-weighted L."""
    lorenz = _curve("dpb", "dpb_s_rho", scattering, "lorenz_number")
    sigma = _curve("dpb", "dpb_s_rho", scattering, "electrical_conductivity_by_band")
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
    # Each band alone is a parabolic band, so its L lies between the limits of its scattering.
    low, high = sorted((4.0 if scattering == "ionized" else 2.0, math.pi**2 / 3))
    for band in (l1, l2):
        assert np.all((band / UNIT > low - 1e-9) & (band / UNIT < high + 1e-9))


def test_no_other_curve_changes() -> None:
    """L is new: the curves it is made of, and every other, are as they were."""
    before = _curve("dpb", "dpb_s_rho", "acPh", "thermal_conductivity")
    _curve("dpb", "dpb_s_rho", "acPh", "lorenz_number")
    after = _curve("dpb", "dpb_s_rho", "acPh", "thermal_conductivity")
    assert {name: np.asarray(v).tobytes() for name, v in before.curves.items()} == {
        name: np.asarray(v).tobytes() for name, v in after.curves.items()
    }


def test_modes_without_resistivity_say_why_they_have_no_l() -> None:
    for model_id, mode_id in (("spb", "spb_s"), ("dpb", "dpb_s")):
        fit_mode = registry.get(model_id).describe().fit_mode(mode_id)
        assert "lorenz_number" not in fit_mode.curve_kinds
        assert fit_mode.unavailable_reason("lorenz_number") == "needs_resistivity"
