"""P13: positive parallel-channel transport with signed carrier occupations."""

import numpy as np
import pytest
from seeband_core import fit_module as fit
from seeband_core import math_module as te

T = np.array([100.0, 300.0, 800.0])


def transport(scatter, mass, gap=0.0, degen=1.0, b=1.0):
    f0 = te.dpb_fermiInt_vs_temp(0, T, mass, gap, -200.0, degen)
    fm = te.dpb_fermiInt_vs_temp(-0.5, T, mass, gap, -200.0, degen)
    scattering = [2.0, b] + ([150.0, 600.0] if scatter == "acPh_dis" else [])
    sigma = getattr(te, f"dpb_ind_elecCond_vs_temp_{scatter}")(T, *f0, *scattering, mass)
    rho = getattr(te, f"dpb_rho_vs_temp_{scatter}")(T, *f0, *scattering, mass)
    kappa = getattr(te, f"dpb_thermCond_vs_temp_{scatter}")(
        T, *f0, *scattering, mass, gap, -200.0, degen
    )
    hall_scattering = [2.0, b] + ([150.0, 600.0] if scatter == "acPh_dis" else [])
    hall = getattr(te, f"dpb_hall_vs_temp_{scatter}")(
        T, rho, *fm, mass, degen, *hall_scattering, 1.0
    )
    return sigma, rho, kappa, hall


@pytest.mark.parametrize("scatter", ["acPh", "dis", "acPh_dis"])
def test_identical_valence_channels_add(scatter):
    # Equal C=D is required to give the identical channels equal scattering.
    scattering = [2.0, 1.0] + ([450.0, 450.0] if scatter == "acPh_dis" else [])
    f0 = te.dpb_fermiInt_vs_temp(0, T, -1.0, 0.0, -200.0, 1.0)
    fm = te.dpb_fermiInt_vs_temp(-0.5, T, -1.0, 0.0, -200.0, 1.0)
    sigma = getattr(te, f"dpb_ind_elecCond_vs_temp_{scatter}")(T, *f0, *scattering, -1.0)
    rho = getattr(te, f"dpb_rho_vs_temp_{scatter}")(T, *f0, *scattering, -1.0)
    single_rho = 1 / sigma[0]
    hall = getattr(te, f"dpb_hall_vs_temp_{scatter}")(T, rho, *fm, -1.0, 1.0, *scattering, 1.0)
    only_first = scattering.copy()
    only_first[1] = 0.0
    single_hall = getattr(te, f"dpb_hall_vs_temp_{scatter}")(
        T, single_rho, *fm, -1.0, 1.0, *only_first, 1.0
    )
    kappa = getattr(te, f"dpb_thermCond_vs_temp_{scatter}")(
        T, *f0, *scattering, -1.0, 0.0, -200.0, 1.0
    )
    lorentz = te.dpb_lorNum_vs_temp(T, -1.0, 0.0, -200.0, 1.0)[0]
    np.testing.assert_allclose(sigma[1], sigma[0], rtol=1e-12)
    np.testing.assert_allclose(1 / rho, 2 * sigma[0], rtol=1e-12)
    np.testing.assert_allclose(kappa, 2 * T * lorentz * sigma[0], rtol=1e-12)
    np.testing.assert_allclose(hall, single_hall / 2, rtol=1e-12)
    assert np.all(hall > 0)
    band = te.dpb_ind_see_vs_temp(T, -1.0, 0.0, -200.0, 1.0)[0]
    np.testing.assert_allclose(te.dpb_see_vs_temp(T, -1.0, 0.0, -200.0, 1.0), band)
    np.testing.assert_allclose(
        te.dpb_see_vs_temp_single_scatter(T, -1.0, 0.0, -200.0, 1.0, 1.0), band
    )
    np.testing.assert_allclose(
        te.dpb_see_vs_temp_double_scatter(T, -1.0, 0.0, -200.0, 1.0, 1.0, 450.0, 450.0), band
    )


@pytest.mark.parametrize("scatter", ["acPh", "dis", "acPh_dis"])
@pytest.mark.parametrize("mass", [-2.0, 2.0])
@pytest.mark.parametrize("degen", [1.0, 3.0])
def test_positive_channels_reconstruct_transport_and_convex_seebeck(scatter, mass, degen):
    sigma, rho, kappa, _ = transport(scatter, mass, 300.0, degen, 0.4)
    assert np.all(np.array(sigma) > 0)
    assert np.all(rho > 0)
    assert np.all(kappa > 0)
    np.testing.assert_allclose(sum(sigma) * rho, 1.0, rtol=1e-12)
    parameters = (T, mass, 300.0, -200.0, degen, 0.4)
    if scatter == "acPh_dis":
        see = te.dpb_see_vs_temp_double_scatter(*parameters, 150.0, 600.0)
        contributions = te.dpb_indCont_see_vs_temp_double_scatter(*parameters, 150.0, 600.0)
    else:
        see = te.dpb_see_vs_temp_single_scatter(*parameters)
        contributions = te.dpb_indCont_see_vs_temp_single_scatter(*parameters)
    band1, band2 = te.dpb_ind_see_vs_temp(*parameters[:5])
    np.testing.assert_allclose(see, sum(contributions), rtol=1e-12)
    np.testing.assert_allclose(see, (sigma[0] * band1 + sigma[1] * band2) / sum(sigma), rtol=1e-12)
    assert np.all(see >= np.minimum(band1, band2) - 1e-18)
    assert np.all(see <= np.maximum(band1, band2) + 1e-18)
    signed_density = te.dpb_ind_carCon_vs_temp(T, -200.0, mass, 300.0, degen)
    assert np.all(signed_density[0] < 0)
    assert np.all(np.sign(signed_density[1]) == np.sign(mass))


def run_fit(mode, start, bounds, progress=None):
    data = [T, np.ones(3)] * (3 if mode == "hall" else 2)
    if mode == "see":
        return fit.PB_fit().dpb_see_fit(T, np.ones(3), start, bounds, 1.0, progress)
    args = [*data, start, bounds, [2.0, 0.4, 0.5, 2.0, 2.0, 0.4], ([0.1] * 6, [10.0] * 6)]
    if mode == "hall":
        args += [1.0, [[0.1], [10.0]]]
    function = fit.PB_fit().dpb_see_res_hall_fit if mode == "hall" else fit.PB_fit().dpb_see_res_fit
    return function(*args, 1.0, "acPh", 0.01, 2, progress=progress)


@pytest.mark.parametrize("mode", ["see", "rho", "hall"])
@pytest.mark.parametrize(
    "mass,bounds",
    [
        (0.0, ([-3, -1000, -1000], [3, 1000, 1000])),
        (-1.0, ([0, -1000, -1000], [3, 1000, 1000])),
        (1.0, ([-3, -1000, -1000], [0, 1000, 1000])),
        (float("nan"), ([-3, -1000, -1000], [3, 1000, 1000])),
    ],
)
def test_invalid_branch_starts_are_explicit(mode, mass, bounds):
    with pytest.raises(ValueError, match="carrier branch"):
        run_fit(mode, [mass, 300.0, -200.0], bounds)


@pytest.mark.parametrize("mode", ["see", "rho", "hall"])
@pytest.mark.parametrize("mass", [-1.0, 1.0])
def test_actual_solver_never_evaluates_the_other_branch(monkeypatch, mode, mass):
    # A linear surrogate drives real SciPy toward an optimum on the forbidden branch.
    # Intercept the observable seam, leaving bounds, solver and iterative stages real.
    seen = []

    def observable(t, value, gap, ef, *args, **kwargs):
        seen.append(value)
        assert value * mass > 0
        return np.full_like(t, value)

    monkeypatch.setattr(te, "dpb_see_vs_temp", observable)
    monkeypatch.setattr(te, "dpb_see_vs_temp_single_scatter", observable)
    progress = fit.FitProgress(held={"res": frozenset({0, 1}), "hall": frozenset({0})})
    result = run_fit(mode, [mass, 300.0, -200.0], ([-3, 0, -500], [3, 500, -100]), progress)
    assert result[0] * mass > 0
    assert len(seen) > 1


@pytest.mark.parametrize("mass", [-2.0, 2.0])
def test_seebeck_only_positive_weights_reconstruct_for_nonunit_degeneracy(mass):
    args = (T, mass, 300.0, -200.0, 3.0)
    total = te.dpb_see_vs_temp(*args)
    np.testing.assert_allclose(total, sum(te.dpb_indCont_see_vs_temp(*args)), rtol=1e-12)
    np.testing.assert_allclose(total, te.dpb_see_vs_temp_single_scatter(*args, 1.0), rtol=1e-12)


@pytest.mark.parametrize("scatter", ["acPh", "dis", "acPh_dis"])
@pytest.mark.parametrize("mass", [-2.0, 2.0])
def test_band_removal_recovers_first_channel_transport(scatter, mass):
    sigma, rho, kappa, _ = transport(scatter, mass, 300.0, 3.0, 0.0)
    np.testing.assert_array_equal(sigma[1], 0.0)
    np.testing.assert_allclose(rho, 1 / sigma[0], rtol=1e-12)
    lorentz = te.dpb_lorNum_vs_temp(T, mass, 300.0, -200.0, 3.0)[0]
    np.testing.assert_allclose(kappa, T * lorentz * sigma[0], rtol=1e-12)
    band1 = te.dpb_ind_see_vs_temp(T, mass, 300.0, -200.0, 3.0)[0]
    parameters = (T, mass, 300.0, -200.0, 3.0, 0.0)
    total = (
        te.dpb_see_vs_temp_double_scatter(*parameters, 150.0, 600.0)
        if scatter == "acPh_dis"
        else te.dpb_see_vs_temp_single_scatter(*parameters)
    )
    np.testing.assert_allclose(total, band1, rtol=1e-12)


@pytest.mark.parametrize("mass", [-1e-30, 1e-30])
def test_tiny_nonzero_start_is_accepted_without_a_mass_scale_floor(monkeypatch, mass):
    monkeypatch.setattr(te, "dpb_see_vs_temp", lambda t, *args, **kwargs: np.ones_like(t))
    progress = fit.FitProgress(held={"see": frozenset({0, 1, 2})})
    result = run_fit("see", [mass, 300.0, -200.0], ([-3, 0, -500], [3, 500, -100]), progress)
    assert result[0] == mass


@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("mass", [-1.7, 1.7])
def test_physical_synthetic_fit_recovers_mass_and_curve(mode_id, mass):
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement
    from seeband_core.model_scales import default_start

    model = registry.get("dpb")
    mode = model.describe().fit_mode(mode_id)
    parameters = default_start(mode) | {
        "m_eff": mass,
        "band_gap": 300.0,
        "fermi_energy": -200.0,
        "A": 2e5,
        "B": 1.0,
        "m1": 1.0,
    }
    parameters = {s.name: parameters[s.name] for s in mode.parameters}
    scattering = None if mode_id == "dpb_s" else "acPh"
    reference = model.calculate(CurveRequest(mode_id, parameters, 100, 800, 12, scattering))
    curve_names = {
        "seebeck": "seebeck_v_per_k",
        "resistivity": "resistivity_ohm_m",
        "hall": "hall_m3_per_c",
    }
    measurements = {
        q: Measurement(reference.temperature_k, reference.curves[curve_names[q]])
        for q in mode.quantities
    }
    held = frozenset(
        s.name for s in mode.parameters_for(scattering) if s.role == "fitted" and s.name != "m_eff"
    )
    result = model.fit(
        FitRequest(
            mode_id,
            measurements,
            parameters | {"m_eff": mass * 0.8},
            bounds={"m_eff": Bounds(-3, 3)},
            scattering=scattering,
            held=held,
        )
    )
    assert result.status == "converged", result.message
    assert result.parameters["m_eff"] * mass > 0
    assert result.parameters["m_eff"] == pytest.approx(mass, rel=1e-6)
    redrawn = model.calculate(CurveRequest(mode_id, result.parameters, 100, 800, 12, scattering))
    for name, values in reference.curves.items():
        np.testing.assert_allclose(redrawn.curves[name], values, rtol=1e-6, atol=1e-14)
