"""Fits reject genuine no-root trials but preserve informative solver failures."""

import numpy as np
import pytest
from seeband_core import fit_module as fm
from seeband_core import math_module as mm


def test_spb_fit_recovers_after_a_no_root_trial():
    temperatures = np.array([100.0, 200.0, 300.0, 400.0])
    expected_energy = 3.758784715
    measured = mm.spb_see_vs_temp(temperatures, expected_energy, 1.0)
    result = fm.PB_fit().spb_see_fit(temperatures, measured, 1.0, [100.0], ([-1000.0], [1000.0]))
    assert result[0] == pytest.approx(expected_energy, rel=1e-7)


@pytest.mark.parametrize("energy", [0.0, -1.0])
def test_invalid_start_is_not_treated_as_a_rejectable_trial(energy):
    with pytest.raises(mm.NoFiniteChemicalPotentialError):
        fm.PB_fit().spb_see_fit(
            np.array([100.0, 200.0]), np.array([1e-4, 1e-4]), 1.0, [energy], ([-1000.0], [1000.0])
        )


def test_numerical_failure_at_a_valid_trial_is_fatal(monkeypatch):
    original = mm.spb_see_vs_temp

    def fail_trial(temperatures, energy, mass, **kwargs):
        if energy != 100.0:
            raise mm.ChemicalPotentialError(100.0, "density residual exceeds tolerance", 0.1)
        return original(temperatures, energy, mass, **kwargs)

    monkeypatch.setattr(mm, "spb_see_vs_temp", fail_trial)
    with pytest.raises(mm.ChemicalPotentialError, match="density residual"):
        fm.PB_fit().spb_see_fit(
            np.array([100.0, 200.0]), np.array([1e-4, 1e-4]), 1.0, [100.0], ([-1000.0], [1000.0])
        )


@pytest.mark.parametrize("held", [frozenset(), frozenset({0})])
def test_jacobian_reverses_a_no_root_stencil_including_held_parameters(held):
    # Two valence bands have a finite root only when EF < max(0, gap).
    # The default positive EF difference exits this domain at the valid start.
    def model(temperatures, gap, energy):
        mm.dpb_chemPot_vs_temp(temperatures, gap, -1.0, energy, 1.0)
        return np.full(temperatures.shape, energy) + gap * np.arange(len(temperatures))

    progress = fm.FitProgress(held={"see": held})
    result, _ = fm._curve_fit(
        progress,
        "see",
        model,
        np.array([100.0, 200.0, 300.0]),
        np.array([0.75, 1.75, 2.75]),
        p0=[1.0, 1.0 - 1e-12],
        bounds=([0.5, 0.0], [1.5, 2.0]),
    )
    np.testing.assert_allclose(result, [1.0, 0.75], atol=1e-7)
    assert "see" in progress.stage_fits


def test_all_held_parameters_still_require_a_valid_start():
    progress = fm.FitProgress(held={"see": frozenset({0})})
    with pytest.raises(mm.NoFiniteChemicalPotentialError):
        fm.PB_fit().spb_see_fit(
            np.array([100.0, 200.0]),
            np.array([1e-4, 1e-4]),
            1.0,
            [0.0],
            ([-1000.0], [1000.0]),
            progress,
        )


def test_valid_model_matches_default_scipy_fit_and_covariance():
    temperatures = np.array([1.0, 2.0, 4.0, 8.0])
    measured = np.array([2.4, 3.8, 8.3, 15.9])

    def model(x, slope, intercept):
        return slope * x + intercept

    options = {"p0": [1.0, -0.2], "bounds": ([0.0, -1.0], [3.0, 1.0])}
    expected = fm.opt.curve_fit(model, temperatures, measured, **options)
    actual = fm._curve_fit(None, "see", model, temperatures, measured, **options)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])


def test_numerical_failure_at_an_optimizer_trial_is_fatal():
    def model(temperatures, energy):
        mm.spb_chemPot_vs_temp(temperatures, 1.0, energy)
        if energy < 50.0:
            raise mm.ChemicalPotentialError(100.0, "bracketed density solve failed")
        return np.full(temperatures.shape, energy)

    with pytest.raises(mm.ChemicalPotentialError, match="bracketed density"):
        fm._curve_fit(
            None,
            "see",
            model,
            np.array([100.0, 200.0]),
            np.array([10.0, 10.0]),
            p0=[100.0],
            bounds=([-1000.0], [1000.0]),
        )


def test_jacobian_shortens_stencil_when_opposite_step_exits_box_bounds():
    def model(temperatures, energy):
        mm.dpb_chemPot_vs_temp(temperatures, 1.0, -1.0, energy, 1.0)
        return np.full(temperatures.shape, energy)

    start = 1.0 - 1e-12
    result, covariance = fm._curve_fit(
        None,
        "see",
        model,
        np.array([100.0, 200.0]),
        np.array([start, start]),
        p0=[start],
        bounds=([1.0 - 1e-9], [2.0]),
    )
    assert result[0] == pytest.approx(start, abs=1e-14)
    assert np.isfinite(covariance).all()


def test_optimizer_interior_adjustment_outside_density_domain_is_a_numerical_failure():
    def model(temperatures, energy):
        mm.dpb_chemPot_vs_temp(temperatures, 1.0, -1.0, energy, 1.0)
        return np.full(temperatures.shape, energy)

    start = 1.0 - 1e-12
    with pytest.raises(mm.ChemicalPotentialError, match="initial interior adjustment") as caught:
        fm._curve_fit(
            None,
            "see",
            model,
            np.array([100.0, 200.0]),
            np.array([start, start]),
            p0=[start],
            bounds=([start], [2.0]),
        )
    assert not isinstance(caught.value, mm.NoFiniteChemicalPotentialError)
    assert isinstance(caught.value.__cause__, mm.NoFiniteChemicalPotentialError)


def test_supplied_start_on_density_boundary_remains_a_domain_error():
    def model(temperatures, energy):
        mm.dpb_chemPot_vs_temp(temperatures, 1.0, -1.0, energy, 1.0)
        return np.full(temperatures.shape, energy)

    with pytest.raises(mm.NoFiniteChemicalPotentialError):
        fm._curve_fit(
            None,
            "see",
            model,
            np.array([100.0, 200.0]),
            np.array([1.0, 1.0]),
            p0=[1.0],
            bounds=([1.0], [2.0]),
        )
