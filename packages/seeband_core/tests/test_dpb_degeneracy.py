"""P6: public DPB S mass ratios must describe the optimized and drawn curve alike."""

import copy

import numpy as np
import pytest
from seeband_core import fit_module, math_module


@pytest.mark.parametrize("degeneracy", [1.0, 3.0, 0.5, 1.5])
def test_solver_objective_and_redraw_use_public_mass_ratio(monkeypatch, degeneracy):
    temperature = np.linspace(100.0, 800.0, 16)
    parameters = [1.2, 800.0, -150.0]
    bounds = ([0.8, 600.0, -250.0], [1.8, 1000.0, -50.0])
    _, measured = fit_module.PB_fit().dpb_see_calc(100, 800, 16, parameters, degeneracy)
    original = copy.deepcopy((temperature, measured, parameters, bounds))
    covariance = np.diag([0.04, 25.0, 9.0])
    progress = fit_module.FitProgress()

    def solver(objective, xdata, ydata, **kwargs):
        # Parameters, starts and bounds belong to public R=m2/m1 coordinates.
        assert kwargs["p0"] == parameters
        assert kwargs["bounds"] == bounds
        np.testing.assert_allclose(objective(xdata, *parameters), measured * 1e6, atol=1e-9)
        np.testing.assert_array_equal(ydata, measured * 1e6)
        return np.array(parameters), covariance

    monkeypatch.setattr(fit_module.opt, "curve_fit", solver)
    fitted = fit_module.PB_fit().dpb_see_fit(
        temperature, measured, parameters, bounds, degeneracy, progress
    )
    np.testing.assert_allclose(fitted, parameters, rtol=0, atol=1e-14)
    np.testing.assert_array_equal(progress.stage_fits["see"][0], parameters)
    np.testing.assert_array_equal(progress.stage_fits["see"][1], covariance)
    for actual, saved in zip((temperature, measured, parameters, bounds), original, strict=True):
        np.testing.assert_equal(actual, saved)


@pytest.mark.parametrize("degeneracy", [1.0, 3.0, 0.5, 1.5])
def test_synthetic_fit_recovers_public_parameters_and_curve(degeneracy):
    temperature = np.linspace(100.0, 800.0, 20)
    parameters = [1.2, 800.0, -150.0]
    _, measured = fit_module.PB_fit().dpb_see_calc(100, 800, 20, parameters, degeneracy)
    start = [1.15, 780.0, -140.0]
    bounds = ([0.8, 600.0, -250.0], [1.8, 1000.0, -50.0])
    fitted = fit_module.PB_fit().dpb_see_fit(temperature, measured, start, bounds, degeneracy)
    _, redrawn = fit_module.PB_fit().dpb_see_calc(100, 800, 20, fitted, degeneracy)
    np.testing.assert_allclose(fitted, parameters, rtol=1e-5)
    assert np.sqrt(np.mean((redrawn - measured) ** 2)) < 1e-10
    assert np.all(np.array(fitted) >= bounds[0])
    assert np.all(np.array(fitted) <= bounds[1])


def test_unit_degeneracy_preserves_original_objective():
    temperature = np.linspace(100.0, 800.0, 20)
    parameters = [1.2, 800.0, -150.0]
    _, drawn = fit_module.PB_fit().dpb_see_calc(100, 800, 20, parameters, 1.0)
    original = math_module.dpb_see_vs_temp(temperature, *parameters, 1.0)
    np.testing.assert_array_equal(drawn, original)


def independent_seebeck(temperature, ratio, gap, fermi_energy, degeneracy):
    """Quadrature and a signed charge root, independent of the core tables and fsolve."""
    from scipy.integrate import quad
    from scipy.optimize import brentq
    from scipy.special import expit

    def integral(order, eta):
        return quad(lambda x: x**order * expit(eta - x), 0, np.inf)[0]

    density_weight = degeneracy * abs(ratio) ** 1.5
    charge_at_zero = (2 / 3) * (
        -(max(-fermi_energy, 0) ** 1.5) + density_weight * max(fermi_energy - gap, 0) ** 1.5
    )
    result = []
    for temp in temperature:

        def charge(mu, temp=temp):
            return (
                temp**1.5
                * (-integral(0.5, -mu / temp) + density_weight * integral(0.5, (mu - gap) / temp))
                - charge_at_zero
            )

        mu = brentq(charge, -5000, 5000)
        eta1, eta2 = -mu / temp, (mu - gap) / temp
        f0_1, f0_2 = np.logaddexp(0, eta1), np.logaddexp(0, eta2)
        # Preserve the port's kB/e constants to isolate degeneracy from constant updates.
        thermopower1 = (1.38064852e-23 / 1.602176634e-19) * (2 * integral(1, eta1) - eta1 * f0_1)
        thermopower2 = -(1.38064852e-23 / 1.602176634e-19) * (2 * integral(1, eta2) - eta2 * f0_2)
        transport_weight = degeneracy / ratio
        result.append(
            (thermopower1 + transport_weight * thermopower2) / (f0_1 + transport_weight * f0_2)
        )
    return np.array(result)


@pytest.mark.parametrize("degeneracy", [1.0, 3.0, 1 / 3])
def test_fit_objective_matches_independent_density_and_transport_weights(monkeypatch, degeneracy):
    temperature = np.array([100.0, 300.0, 700.0])
    parameters = [1.2, 800.0, -150.0]
    reference = independent_seebeck(temperature, *parameters, degeneracy)

    def solver(objective, xdata, ydata, **kwargs):
        np.testing.assert_allclose(objective(xdata, *parameters) / 1e6, reference, atol=1e-11)
        return np.array(parameters), np.eye(3)

    monkeypatch.setattr(fit_module.opt, "curve_fit", solver)
    fit_module.PB_fit().dpb_see_fit(
        temperature, reference, parameters, ([0.8, 600, -250], [1.8, 1000, -50]), degeneracy
    )
    if degeneracy == 3.0:
        legacy = math_module.dpb_see_vs_temp(temperature, *parameters, degeneracy)
        assert np.max(np.abs(legacy - reference)) > 1e-4


def test_nonunit_synthetic_golden_results():
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "physics" / "p6.json"
    document = json.loads(fixture.read_text())
    assert document["synthetic"] is True
    for case in document["cases"]:
        temperature = np.array(case["temperature_k"])
        measured = np.array(case["seebeck_v_per_k"])
        degeneracy = case["degeneracy_ratio"]
        fitted = fit_module.PB_fit().dpb_see_fit(
            temperature, measured, case["start"], case["bounds"], degeneracy
        )
        np.testing.assert_allclose(fitted, case["fitted_parameters"], rtol=1e-5)
        _, redrawn = fit_module.PB_fit().dpb_see_calc(100, 800, 20, fitted, degeneracy)
        np.testing.assert_allclose(redrawn, case["redrawn_seebeck_v_per_k"], atol=1e-10)


@pytest.mark.parametrize("n1,n2", [(1, 3), (2, 6), (0.5, 1.5)])
def test_equal_degeneracy_ratios_have_equal_model_curves(n1, n2):
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest

    model = registry.get("dpb")
    parameters = {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": -150.0}
    result = model.calculate(
        CurveRequest("dpb_s", parameters, 100, 800, 20, band_1_degeneracy=n1, band_2_degeneracy=n2)
    )
    _, expected = fit_module.PB_fit().dpb_see_calc(100, 800, 20, list(parameters.values()), 3.0)
    np.testing.assert_array_equal(result.curves["seebeck_v_per_k"], expected)
