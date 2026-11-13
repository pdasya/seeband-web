"""Physical limits and synthetic recovery for the repaired SPB Hall mode (P4/P12)."""

import json
from pathlib import Path

import numpy as np
import pytest
from seeband_core import math_module as math


@pytest.mark.parametrize("mass", [-1.5, 1.5])
def test_hall_factor_uses_conserved_carrier_density(mass: float) -> None:
    temperatures = np.array([100.0, 300.0, 600.0, 900.0])
    fermi_energy = np.sign(mass) * 100.0
    density_m3 = math.spb_carCon(fermi_energy, mass, 0) * 1e6
    para_e = -np.sign(mass) * abs(mass) ** 1.5
    hall = math.spb_hall_vs_temp(temperatures, fermi_energy, np.sign(mass), para_e)
    hall_factor = np.abs(hall * density_m3 * math.e)
    assert np.all(hall_factor >= 1 - 1e-6)
    assert np.all(hall_factor <= 3 * np.pi / 8 + 1e-6)
    assert np.all(np.sign(hall) == -np.sign(mass))


@pytest.mark.parametrize("mass", [-1.5, 1.5])
@pytest.mark.parametrize("fermi_over_temperature", [0.01, 1.0, 100.0])
def test_hall_matches_independent_quadrature(mass: float, fermi_over_temperature: float) -> None:
    from scipy.integrate import quad
    from scipy.optimize import brentq
    from scipy.special import expit

    # Unnormalised F_j(x), integrating epsilon=u^2 to remove the endpoint singularity.
    def integral(order: float, reduced_mu: float) -> float:
        return quad(
            lambda u: 2 * u ** (2 * order + 1) * expit(reduced_mu - u * u),
            0,
            np.inf,
            epsabs=1e-11,
        )[0]

    reduced_mu = brentq(
        lambda x: integral(0.5, x) - (2 / 3) * fermi_over_temperature**1.5, -40, 110
    )
    reference_factor = (
        0.75
        * integral(-0.5, reduced_mu)
        * integral(0.5, reduced_mu)
        / np.logaddexp(0, reduced_mu) ** 2
    )
    temperature = np.array([100.0])
    fermi_energy = np.sign(mass) * fermi_over_temperature * temperature[0]
    density_m3 = math.spb_carCon(fermi_energy, mass, 0) * 1e6
    hall = math.spb_hall_vs_temp(
        temperature, fermi_energy, np.sign(mass), -np.sign(mass) * abs(mass) ** 1.5
    )
    np.testing.assert_allclose(abs(hall * density_m3 * math.e), reference_factor, rtol=2e-6)
    if fermi_over_temperature == 0.01:
        assert reference_factor == pytest.approx(3 * np.pi / 8, rel=1e-3)
    if fermi_over_temperature == 100:
        assert reference_factor == pytest.approx(1, rel=1e-3)


@pytest.mark.parametrize("mass", [-1.5, 1.5])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("crossing_bounds", [False, True])
def test_synthetic_hall_fit_recovers_physical_parameters(
    mass: float, scattering: str, crossing_bounds: bool
) -> None:
    import copy

    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement
    from seeband_core.model_scales import default_start

    model = registry.get("spb")
    mode = model.describe().fit_mode("spb_s_rho_rh")
    known = default_start(mode) | {
        "band_mass": mass,
        "fermi_energy": np.sign(mass) * 250.0,
        "A": 3000.0,
        "C": 0.7,
        "F": 2.0,
    }
    curve = model.calculate(CurveRequest(mode.id, known, 100, 800, 12, scattering))
    measurements = {
        quantity: Measurement(curve.temperature_k.copy(), curve.curves[column].copy())
        for quantity, column in [
            ("seebeck", "seebeck_v_per_k"),
            ("resistivity", "resistivity_ohm_m"),
            ("hall", "hall_m3_per_c"),
        ]
    }
    start = known | {
        "band_mass": mass * 0.8,
        "fermi_energy": known["fermi_energy"] * 0.7,
        "A": 2500.0,
        "C": 0.4,
        "F": 1.5,
    }
    mass_bounds = Bounds(0.5, 2.5) if mass > 0 else Bounds(-2.5, -0.5)
    if crossing_bounds:
        mass_bounds = Bounds(-3.0, 3.0)
    request = FitRequest(mode.id, measurements, start, {"band_mass": mass_bounds}, scattering)
    before = copy.deepcopy(request)
    result = model.fit(request)
    assert result.status == "converged", result.message
    golden = json.loads((Path(__file__).parent / "fixtures" / "physics" / "p4.json").read_text())
    reference = golden["synthetic"][f"{mass}:{scattering}"]
    assert reference["known_parameters"] == known
    assert result.parameters == pytest.approx(reference["fitted_parameters"], rel=2e-5)
    for column, values in curve.curves.items():
        np.testing.assert_allclose(values, reference["curves"][column], rtol=1e-9, atol=0)
    fitted = ["band_mass", "fermi_energy"] + {"acPh": ["A"], "dis": ["F"], "acPhDis": ["A", "C"]}[
        scattering
    ]
    for name in fitted:
        assert result.parameters[name] == pytest.approx(known[name], rel=2e-5)
    fitted_curve = model.calculate(
        CurveRequest(mode.id, result.parameters, 100, 800, 12, scattering)
    )
    for column, values in curve.curves.items():
        np.testing.assert_allclose(fitted_curve.curves[column], values, rtol=2e-5, atol=0)
    assert request.start == before.start
    assert request.bounds == before.bounds
    assert known["C"] == 0.7
    for quantity in measurements:
        np.testing.assert_array_equal(
            request.measurements[quantity].temperature_k,
            before.measurements[quantity].temperature_k,
        )
        np.testing.assert_array_equal(
            request.measurements[quantity].values, before.measurements[quantity].values
        )
