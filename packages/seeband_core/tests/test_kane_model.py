"""Physical limits and inverse-series checks for the new SKB model (synthetic data)."""

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy.constants import Boltzmann, electron_mass, elementary_charge, hbar
from scipy.integrate import quad
from scipy.special import expit
from seeband_core.band_models import SkbModel, SpbModel, _BandModel
from seeband_core.kane import kane_dispersion, transport_integrals, zero_temperature_density
from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement
from seeband_core.model_scales import default_start

MODEL = SkbModel()
MODE = "skb_s_rho_rh"


def parameters() -> dict[str, float]:
    return default_start(MODEL.describe().fit_mode(MODE)) | {
        "band_mass": 0.2,
        "fermi_energy": 300.0,
    }


def curves(**changes: float) -> dict[str, np.ndarray]:
    return MODEL.calculate(CurveRequest(MODE, parameters() | changes, 100, 800, 12, "acPh")).curves


@pytest.mark.parametrize("eta", [-40.0, -10.0, 0.0, 20.0, 200.0, 1000.0])
def test_parabolic_integral_identity(eta: float) -> None:
    f = transport_integrals(eta, 0)
    assert math.exp(f.log_g) > 0
    log_one_plus_exp = np.logaddexp(0, eta)
    assert f.a * math.exp(min(eta, 0)) == pytest.approx(log_one_plus_exp / 3, rel=2e-9)


def test_classical_parabolic_limits() -> None:
    f = transport_integrals(-25, 0)
    assert f.variance == pytest.approx(2, rel=1e-8)
    assert f.hall_factor == pytest.approx(3 * math.pi / 8, rel=1e-8)


def test_degenerate_lorenz_limit() -> None:
    f = transport_integrals(1000, 0)
    assert f.variance == pytest.approx(math.pi**2 / 3, rel=1e-5)


@pytest.mark.parametrize(("eta", "alpha"), [(-30, 0.001), (0, 1), (8, 0.2), (150, 2)])
def test_quadrature_against_independent_adaptive_integrator(eta: float, alpha: float) -> None:
    upper = max(100, eta + 100)

    def kernel(x: float, moment: int) -> float:
        t = math.exp(-abs(x - eta))
        u = x + alpha * x * x
        v = (1 + 2 * alpha * x) ** 2 + 2
        return t / (1 + t) ** 2 * u / v * (x - eta) ** moment

    # Integrate the full interval, with breakpoints around the Fermi window.
    points = [p for p in (eta - 20, eta, eta + 20) if 0 < p < upper]
    values = [
        quad(
            kernel,
            0,
            upper,
            args=(j,),
            epsabs=1e-25 if eta < 0 else 1e-12,
            epsrel=1e-10,
            points=points,
        )[0]
        for j in range(3)
    ]
    f = transport_integrals(eta, alpha)
    assert f.mean_offset == pytest.approx(values[1] / values[0], rel=2e-8)
    assert f.variance == pytest.approx(
        values[2] / values[0] - (values[1] / values[0]) ** 2, rel=2e-8
    )


def test_dispersion_has_band_edge_mass_and_satisfies_kane_equation() -> None:
    k = np.array([0.0, 1e5, 1e8, 1e9])
    mass = 0.12
    gap = 0.2
    energy = kane_dispersion(k, mass, gap)
    rhs = hbar**2 * k**2 / (2 * mass * electron_mass) / elementary_charge
    np.testing.assert_allclose(energy * (1 + energy / gap), rhs, rtol=1e-12)
    assert energy[0] == 0
    assert energy[1] == pytest.approx(rhs[1], rel=1e-7)


def test_framework_parameters_and_common_adapter() -> None:
    assert isinstance(MODEL, _BandModel)
    specs = {p.name: p for p in MODEL.describe().fit_modes[0].parameters}
    assert set(specs) == {"band_mass", "fermi_energy", "A", "kane_gap_ev"}
    source = SpbModel().describe().fit_mode("spb_s_rho")
    for original in source.parameters:
        if original.name not in specs:
            continue
        actual = specs[original.name]
        assert actual.fit_scale == original.fit_scale
        assert actual.display_scale == original.display_scale
        assert actual.unit == original.unit
        assert actual.meaning == original.meaning
    assert MODEL.describe().fit_modes[0].degeneracy.band_2_default is None


def test_charge_neutrality_hall_and_chemical_potential() -> None:
    p = parameters()
    request = CurveRequest(MODE, p, 100, 800, 12, "acPh")
    r = MODEL.calculate(request)
    density = zero_temperature_density(p["band_mass"], p["fermi_energy"], p["kane_gap_ev"])
    derived = {}
    for kind in (
        "lorenz_number",
        "reduced_fermi_level",
        "carrier_concentration_by_band",
        "carrier_mobility",
        "hall_factor",
        "chemical_potential",
    ):
        derived |= MODEL.calculate(replace(request, kind=kind)).curves
    np.testing.assert_allclose(derived["carrier_concentration_band_1_per_cm3"], density * 1e-6)
    np.testing.assert_allclose(
        r.curves["hall_m3_per_c"], -derived["hall_factor"] / (elementary_charge * density)
    )
    np.testing.assert_allclose(
        derived["chemical_potential_k"], derived["reduced_fermi_level"] * r.temperature_k
    )
    np.testing.assert_allclose(
        r.curves["resistivity_ohm_m"]
        * elementary_charge
        * density
        * derived["mobility_m2_per_v_s"],
        1,
    )
    assert np.ptp(derived["lorenz_w_ohm_per_k2"]) > 0
    for i in (0, 5, 11):
        t = r.temperature_k[i]
        eta = derived["reduced_fermi_level"][i]
        alpha = Boltzmann * t / (elementary_charge * p["kane_gap_ev"])
        occupation, _ = quad(
            lambda x, alpha=alpha, eta=eta: (
                math.sqrt(x + alpha * x * x) * (1 + 2 * alpha * x) * expit(eta - x)
            ),
            0,
            max(100, eta + 100),
            epsabs=1e-11,
            epsrel=1e-10,
        )
        prefactor = (2 * p["band_mass"] * electron_mass * Boltzmann * t) ** 1.5 / (
            2 * math.pi**2 * hbar**3
        )
        assert prefactor * occupation == pytest.approx(density, rel=2e-8)


def test_parameter_conversion_preserves_initial_skb_curves() -> None:
    saved = json.loads((Path(__file__).parent / "fixtures/kane_compatibility.json").read_text())
    p = saved["parameters"]
    request = CurveRequest(MODE, p, 100, 800, 8, "acPh")
    calculated = dict(MODEL.calculate(request).curves)
    for kind in ("chemical_potential", "lorenz_number", "carrier_mobility"):
        calculated |= MODEL.calculate(replace(request, kind=kind)).curves
    for name, expected in saved["curves"].items():
        np.testing.assert_allclose(calculated[name], expected, rtol=2e-10, atol=1e-15)


@pytest.mark.parametrize("sign", [-1, 1])
def test_parabolic_limit_reuses_spb_acoustic_scale_and_fermi_convention(sign: int) -> None:
    p = parameters() | {
        "band_mass": sign * 0.7,
        "fermi_energy": sign * 300.0,
        "A": 40000.0,
        "kane_gap_ev": 1e10,
    }
    result = MODEL.calculate(CurveRequest(MODE, p, 100, 800, 8, "acPh"))
    spb = SpbModel()
    old = default_start(spb.describe().fit_mode("spb_s_rho")) | {
        n: p[n] for n in ("band_mass", "fermi_energy", "A")
    }
    expected = spb.calculate(CurveRequest("spb_s_rho", old, 100, 800, 8, "acPh"))
    for name, values in expected.curves.items():
        np.testing.assert_allclose(result.curves[name], values, rtol=3e-5, atol=1e-11)


def test_holes_flip_signed_curves_and_common_n1_sets_valley_mass() -> None:
    base = CurveRequest(MODE, parameters(), 100, 800, 12, "acPh")
    n = MODEL.calculate(base).curves
    p = MODEL.calculate(
        replace(base, parameters=parameters() | {"band_mass": -0.2, "fermi_energy": -300.0})
    ).curves
    for name in ("seebeck_v_per_k", "hall_m3_per_c"):
        np.testing.assert_allclose(p[name], -n[name])
    np.testing.assert_allclose(p["resistivity_ohm_m"], n["resistivity_ohm_m"])
    ordinary = MODEL.calculate(replace(base, kind="band_masses")).curves
    valleys = MODEL.calculate(replace(base, kind="band_masses", band_1_degeneracy=8)).curves
    np.testing.assert_allclose(
        valleys["band_edge_valley_mass_me"], ordinary["band_edge_valley_mass_me"] / 4
    )


@pytest.mark.parametrize("sign", [-1, 1])
def test_global_fit_recovers_synthetic_parameters_on_different_grids(sign: int) -> None:
    true = parameters() | {
        "band_mass": sign * 0.16,
        "fermi_energy": sign * 403.818691757203,
        "A": 13842.137464411026,
    }
    names = {
        "seebeck": "seebeck_v_per_k",
        "resistivity": "resistivity_ohm_m",
        "hall": "hall_m3_per_c",
    }
    measurements = {}
    for i, (quantity, column) in enumerate(names.items()):
        r = MODEL.calculate(CurveRequest(MODE, true, 100 + 15 * i, 700 - 10 * i, 9 + i, "acPh"))
        measurements[quantity] = Measurement(r.temperature_k, r.curves[column])
    start = true | {"band_mass": sign * 0.25, "fermi_energy": sign * 200.0, "A": 40000.0}
    before = {q: m.values.copy() for q, m in measurements.items()}
    result = MODEL.fit(
        FitRequest(MODE, measurements, start, scattering="acPh", extrapolated=sign == 1)
    )
    assert result.status == "converged"
    assert ("interpolation_extrapolates" in result.known_issues) == (sign == 1)
    for name in ("band_mass", "fermi_energy", "A"):
        assert result.parameters[name] == pytest.approx(true[name], rel=2e-4)
    for q, m in measurements.items():
        np.testing.assert_array_equal(m.values, before[q])


def test_bad_requests_and_bounds_are_not_silently_fixed() -> None:
    with pytest.raises(ValueError, match="band_mass"):
        curves(band_mass=0)
    with pytest.raises(ValueError):
        MODEL.calculate(CurveRequest(MODE, parameters(), 100, 800, 8, "acPh", band_2_degeneracy=2))
    with pytest.raises(ValueError):
        MODEL.calculate(CurveRequest(MODE, parameters(), 0, 300, 5, "acPh"))
    with pytest.raises(ValueError, match="Missing"):
        MODEL.fit(FitRequest(MODE, {}, parameters(), scattering="acPh"))
    with pytest.raises(ValueError):
        MODEL.fit(FitRequest(MODE, {}, parameters(), {"A": Bounds(2, 1)}, "acPh"))


def test_table_1_mass_at_350_k_as_forward_model() -> None:
    # Lin & Liu (2022), Table 1: S=342.3 uV/K, nH=3.646e24 m^-3,
    # Eg=.43 eV; published computed mDOS/me=.9523. Solve eta independently.
    from scipy.optimize import brentq

    q = Boltzmann / elementary_charge
    alpha = q * 350 / 0.43
    eta = brentq(lambda x: q * transport_integrals(x, alpha).mean_offset - 342.3e-6, -20, 20)
    f = transport_integrals(eta, alpha)
    n = 3.646e24 * f.hall_factor
    mass = hbar**2 / (2 * Boltzmann * 350) * (3 * math.pi**2 * n / math.exp(f.log_g)) ** (2 / 3)
    assert mass / electron_mass == pytest.approx(0.9523, abs=5e-5)
