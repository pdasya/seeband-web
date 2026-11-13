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
    np.testing.assert_allclose(
        abs(hall * density_m3 * math.e), reference_factor, rtol=CHAIN_TOLERANCE
    )
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


def _quadrature_hall_factor(fermi_over_temperature: float) -> float:
    """r_H at the chemical potential that keeps the T = 0 density, from quadrature alone."""
    from scipy.integrate import quad
    from scipy.optimize import brentq
    from scipy.special import expit

    def integral(order: float, reduced_mu: float) -> float:
        return quad(
            lambda u: 2 * u ** (2 * order + 1) * expit(reduced_mu - u * u),
            0,
            np.inf,
            epsabs=1e-11,
            limit=200,
        )[0]

    reduced_mu = brentq(
        lambda x: integral(0.5, x) - (2 / 3) * fermi_over_temperature**1.5, -40, 1000
    )
    return float(
        0.75
        * integral(-0.5, reduced_mu)
        * integral(0.5, reduced_mu)
        / np.logaddexp(0, reduced_mu) ** 2
    )


# The error budget of the core's Fermi integrals: the asymptote of F_1/2 above a reduced potential
# of 19.9 is off by about 1.3/eta^4 (8e-6 at 20), its approximation below -9.9 by up to 4e-6, and
# the table by about 1e-7. The worst measured, at eta = 19.96, is 8.5e-6.
CHAIN_TOLERANCE = 1.5e-5
# From E_F/T = 667 to 0.01, through the switch of F_1/2 at 19.9.
CHAIN_K = np.array([1.5, 10.0, 50.0, 50.25, 100.0, 300.0, 1000.0, 5000.0, 1e5])


@pytest.mark.parametrize("mass", [-1.5, 1.5])
@pytest.mark.parametrize(
    "order",
    [list(range(9)), list(range(9))[::-1], [4, 0, 8, 2, 6, 1, 7, 3, 5]],
    ids=["ascending", "descending", "shuffled"],
)
def test_hall_along_a_chain_of_temperatures_matches_quadrature_in_any_order(
    mass: float, order: list[int]
) -> None:
    temperatures = CHAIN_K[order]
    fermi_energy = np.sign(mass) * 1000.0
    density_m3 = math.spb_carCon(fermi_energy, mass, 0) * 1e6
    hall = math.spb_hall_vs_temp(
        temperatures, fermi_energy, np.sign(mass), -np.sign(mass) * abs(mass) ** 1.5
    )
    expected = [_quadrature_hall_factor(1000.0 / temperature) for temperature in temperatures]

    np.testing.assert_allclose(np.abs(hall * density_m3 * math.e), expected, rtol=CHAIN_TOLERANCE)
    assert np.all(np.sign(hall) == -np.sign(mass))


def test_a_step_down_in_temperature_gives_the_same_hall_as_a_step_up() -> None:
    # Before sorting, the solve from 650 K missed the root at 300 K, 3.7e4 times off.
    up = math.spb_hall_vs_temp(np.array([300.0, 650.0]), 3.76, 1, -1.0)
    down = math.spb_hall_vs_temp(np.array([650.0, 300.0]), 3.76, 1, -1.0)

    np.testing.assert_array_equal(down[::-1], up)


def test_points_beyond_the_reach_of_the_fermi_integrals_are_nan_and_the_rest_stay() -> None:
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest
    from seeband_core.model_scales import default_start

    # E_F / T = 1000 at 1 K overflows exp(eta); at 2 K, 500, it does not.
    hall = math.spb_hall_vs_temp(np.array([1.0, 2.0, 10.0]), 1000.0, 1, -1.0)
    assert np.isnan(hall[0])
    assert np.all(np.isfinite(hall[1:]))

    mode = registry.get("spb").describe().fit_mode("spb_s_rho_rh")
    start = default_start(mode) | {"band_mass": 1.0, "fermi_energy": 2000.0}
    curve = registry.get("spb").calculate(CurveRequest(mode.id, start, 2, 300, 20, "acPh"))
    hall_curve = curve.curves["hall_m3_per_c"]
    assert np.isnan(hall_curve[0])
    assert np.all(np.isfinite(hall_curve[curve.temperature_k > 3]))


def _synthetic_hole_data() -> tuple[dict[str, float], dict[str, object]]:
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import CurveRequest, Measurement
    from seeband_core.model_scales import default_start

    model = registry.get("spb")
    mode = model.describe().fit_mode("spb_s_rho_rh")
    known = default_start(mode) | {"band_mass": -1.5, "fermi_energy": -250.0, "A": 3000.0}
    curve = model.calculate(CurveRequest(mode.id, known, 100, 800, 12, "acPh"))
    measurements = {
        quantity: Measurement(curve.temperature_k.copy(), curve.curves[column].copy())
        for quantity, column in [
            ("seebeck", "seebeck_v_per_k"),
            ("resistivity", "resistivity_ohm_m"),
            ("hall", "hall_m3_per_c"),
        ]
    }
    return known, measurements


def test_a_fit_gives_the_same_result_for_points_in_any_order() -> None:
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import FitRequest, Measurement

    known, measurements = _synthetic_hole_data()
    start = known | {"band_mass": -1.0, "fermi_energy": -150.0, "A": 2500.0}
    shuffle = np.array([7, 2, 11, 0, 5, 9, 3, 10, 1, 6, 8, 4])
    shuffled = {
        quantity: Measurement(data.temperature_k[shuffle], data.values[shuffle])
        for quantity, data in measurements.items()
    }
    model = registry.get("spb")

    sorted_fit = model.fit(FitRequest("spb_s_rho_rh", measurements, start, scattering="acPh"))
    shuffled_fit = model.fit(FitRequest("spb_s_rho_rh", shuffled, start, scattering="acPh"))

    assert sorted_fit.status == "converged"
    assert shuffled_fit.parameters == sorted_fit.parameters
    assert sorted_fit.parameters["band_mass"] == pytest.approx(-1.5, rel=2e-5)
