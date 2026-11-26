"""Mixed acoustic/alloy scattering follows bandwise Matthiessen addition."""

from dataclasses import replace

import numpy as np
import pytest
from seeband_core.model_catalog import registry
from seeband_core.model_descriptions import explicit_dpb_description
from seeband_core.model_interface import (
    Bounds,
    CurveRequest,
    ExplicitBands,
    FitRequest,
    Measurement,
)
from seeband_core.model_scales import default_start


@pytest.mark.parametrize("model_id,explicit", [("spb", False), ("dpb", False), ("dpb", True)])
def test_bandwise_resistivities_add_at_and_away_from_reference_temperature(model_id, explicit):
    model = registry.get(model_id)
    mode_id = model_id + "_s_rho"
    mode = (
        explicit_dpb_description().fit_mode(mode_id)
        if explicit
        else model.describe().fit_mode(mode_id)
    )
    p = default_start(mode) | dict(A=60000, C=0.5, B=0.8, D=2.0, fermi_energy=-150)
    settings = ExplicitBands("cb_cb", 2e24) if explicit else None
    p |= (
        dict(m1=1.2, mass_ratio=1.7, band_offset_k=800)
        if explicit
        else dict(m_eff=1.7, band_gap=800)
    )
    # 1/sigma_mix,i = 1/sigma_ac,i + 1/sigma_dis,i. Match disorder
    # amplitudes using the dimensionless ratios defined at T_ref=300 K.
    p |= dict(F=p["A"] / (300 * p["C"]), G=p["B"] * p["C"] / p["D"])
    kind = "electrical_conductivity_by_band" if model_id == "dpb" else "electrical_conductivity"
    req = CurveRequest(mode_id, p, 100, 700, 4, "acPhDis", kind, explicit_bands=settings)
    mixed = model.calculate(req)
    acoustic = model.calculate(replace(req, scattering="acPh"))
    disorder = model.calculate(replace(req, scattering="dis"))
    assert 300 in mixed.temperature_k
    for name, sigma in mixed.curves.items():
        np.testing.assert_allclose(
            1 / sigma, 1 / acoustic.curves[name] + 1 / disorder.curves[name], rtol=2e-12
        )


@pytest.mark.parametrize("explicit", [False, True])
def test_s_only_is_structural_and_ignores_all_mixed_amplitudes(explicit):
    model = registry.get("dpb")
    mode = (
        explicit_dpb_description().fit_mode("dpb_s")
        if explicit
        else model.describe().fit_mode("dpb_s")
    )
    assert not {p.name for p in mode.parameters_for("acPhDis")} & {"A", "B", "C", "D"}
    p = default_start(mode)
    if explicit:
        p |= dict(m1=1.2, mass_ratio=1.7, band_offset_k=800)
    else:
        p |= dict(m_eff=1.7, band_gap=800, fermi_energy=-150)
    req = CurveRequest(
        "dpb_s",
        p,
        150,
        650,
        4,
        "acPhDis",
        explicit_bands=ExplicitBands("vb_cb", 2e24) if explicit else None,
    )
    before = model.calculate(req)
    after = model.calculate(replace(req, parameters=p | dict(A=1e9, B=3, C=0.5, D=8)))
    np.testing.assert_array_equal(before.curves["seebeck_v_per_k"], after.curves["seebeck_v_per_k"])


@pytest.mark.parametrize("model_id,explicit", [("spb", False), ("dpb", False), ("dpb", True)])
def test_verified_fit_recovers_mixed_ratios_from_synthetic_data(model_id, explicit):
    model = registry.get(model_id)
    mode_id = model_id + "_s_rho"
    mode = (
        explicit_dpb_description().fit_mode(mode_id)
        if explicit
        else model.describe().fit_mode(mode_id)
    )
    p = default_start(mode) | dict(A=60000, C=0.5)
    if model_id == "dpb":
        p |= dict(B=1.0, D=1.5)
        p |= (
            dict(m1=1.2, mass_ratio=1.7, band_offset_k=800)
            if explicit
            else dict(m_eff=1.7, band_gap=800, fermi_energy=-150)
        )
    settings = ExplicitBands("vb_cb", 2e24) if explicit else None
    req = CurveRequest(mode_id, p, 100, 700, 9, "acPhDis", explicit_bands=settings)
    synthetic = model.calculate(req)
    measurements = {
        q: Measurement(synthetic.temperature_k, synthetic.curves[name])
        for q, name in (("seebeck", "seebeck_v_per_k"), ("resistivity", "resistivity_ohm_m"))
    }
    free = {"C", "D"} if model_id == "dpb" else {"C"}
    active = {s.name for s in mode.parameters_for("acPhDis") if s.role == "fitted"}
    fit = FitRequest(
        mode_id,
        measurements,
        p | {name: p[name] * 1.1 for name in free},
        {name: Bounds(p[name] * 0.5, p[name] * 1.5) for name in free},
        "acPhDis",
        held=frozenset(active - free),
        explicit_bands=settings,
    )
    result = model.fit(fit)
    assert result.status == "converged", (result.message, result.diagnostics)
    for name in free:
        assert result.parameters[name] == pytest.approx(p[name], rel=2e-6)
    assert result.diagnostics.stage_consistent
    assert result.diagnostics.residuals["resistivity"].relative_l2 < 1e-8
    with pytest.raises(ValueError, match="lower bound"):
        model.fit(replace(fit, bounds={"C": Bounds(1, 0)}))
    with pytest.raises(ValueError, match="finite and nonnegative"):
        model.fit(replace(fit, bounds={"C": Bounds(-0.1, 1)}))


@pytest.mark.parametrize("ratio", [-1.0, float("nan"), float("inf")])
@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_public_mixed_curves_reject_nonphysical_crossover_ratio(model_id, ratio):
    model = registry.get(model_id)
    mode_id = model_id + "_s_rho"
    p = default_start(model.describe().fit_mode(mode_id)) | {"C": ratio}
    with pytest.raises(ValueError, match="finite and nonnegative"):
        model.calculate(CurveRequest(mode_id, p, 100, 700, 4, "acPhDis"))


def test_mixed_spb_initial_estimate_uses_the_acoustic_energy_exponent():
    from seeband_core import math_module as mm
    from seeband_core.initial_guess import single_band_guess

    t = np.linspace(100.0, 800.0, 12)
    s = mm.spb_see_vs_temp(t, -900.0, -1.0)
    estimate = single_band_guess("spb", t, s, "acPhDis")
    assert estimate.start_values["fermi_energy"] == pytest.approx(-900.0, abs=1.0)
    assert estimate.rmse_v_per_k < 1e-8


def test_intrinsic_dilute_mixed_lorenz_retains_temperature_dependent_band_weights():
    from seeband_core import math_module as mm

    model = registry.get("dpb")
    p = default_start(model.describe().fit_mode("dpb_s_rho")) | dict(
        m_eff=1.0, band_gap=4000.0, fermi_energy=0.0, B=0.8, C=0.5, D=2.0
    )
    result = model.calculate(CurveRequest("dpb_s_rho", p, 2, 3, 2, "acPhDis", "lorenz_number"))
    t = result.temperature_k
    relative = p["B"] * (t + 300 * p["C"]) / (t + 300 * p["D"])
    # Symmetric intrinsic bands have eta=-gap/(2T), opposite S, and L_i=2(kB/e)^2.
    expected = (mm.kB / mm.e) ** 2 * (
        2 + 4 * relative / (1 + relative) ** 2 * (2 + p["band_gap"] / (2 * t)) ** 2
    )
    np.testing.assert_allclose(result.curves["lorenz_number_w_ohm_per_k2"], expected, rtol=1e-11)
