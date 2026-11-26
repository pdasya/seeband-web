"""Independent Boltzmann reference checks for the unscreened power-law model."""

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import expit
from seeband_core import math_module as mm
from seeband_core.model_catalog import registry


def test_public_modes_offer_ionized_and_mixed_scattering():
    for name in ("spb", "dpb"):
        for mode in registry.get(name).describe().fit_modes:
            assert "ionized" in mode.scattering
            assert "acPhDis" in mode.scattering
            names = {p.name for p in mode.parameters_for("ionized")}
            assert not names.intersection({"C", "D", "F", "G"})


def reference(eta, order):
    return quad(
        lambda x: x**order * expit(eta - x), 0, max(eta, 0) + 100, epsabs=1e-12, epsrel=2e-12
    )[0]


@pytest.mark.parametrize("eta", [-12.0, 0.0, 8.0, 80.0, 1000.0])
def test_ionized_band_matches_independent_integrals(eta):
    from seeband_core.transport import band_transport

    t = np.array([300.0])
    sigma, seebeck, lorenz, hall = band_transport(t, np.array([eta]), 1.0, 2.0)
    f2, f3, f4, fh = [reference(eta, j) for j in (2, 3, 4, 3.5)]
    assert sigma[0] == pytest.approx(f2, rel=3e-10)
    assert seebeck[0] == pytest.approx(-mm.kB / mm.e * (4 * f3 / (3 * f2) - eta), rel=2e-8)
    assert lorenz[0] == pytest.approx(
        (mm.kB / mm.e) ** 2 * (5 * f4 / (3 * f2) - (4 * f3 / (3 * f2)) ** 2), rel=2e-7
    )
    prefactor = 3 * mm.hbar**3 * np.pi**2 / (mm.e * (2 * mm.kB * mm.me) ** 1.5)
    assert hall[0] == pytest.approx(-prefactor * 300**-1.5 * 0.5 * fh / f2**2, rel=3e-10)


@pytest.mark.parametrize(
    "model,mode,parameters,n",
    [
        ("spb", "spb_s_rho_rh", {"band_mass": 1.7, "fermi_energy": 500.0, "A": 2e4}, 1.0),
        (
            "dpb",
            "dpb_s_rho_rh",
            {
                "m_eff": 1.4,
                "fermi_energy": -400.0,
                "band_gap": 700.0,
                "A": 2e4,
                "B": 0.8,
                "m1": 1.2,
            },
            2.0,
        ),
        (
            "dpb",
            "dpb_s_rho_rh",
            {
                "m_eff": -1.4,
                "fermi_energy": -400.0,
                "band_gap": 700.0,
                "A": 2e4,
                "B": 0.8,
                "m1": 1.2,
            },
            2.0,
        ),
    ],
)
def test_fitter_measured_and_additional_curves_agree(model, mode, parameters, n):
    from seeband_core.model_interface import CurveRequest
    from seeband_core.transport import ionized_transport
    from seeband_core.verified_fit import _evaluate_quantity

    t = np.linspace(200.0, 700.0, 9)
    prediction = ionized_transport(t, parameters, mode, n)
    model_object = registry.get(model)

    def curve(kind):
        return model_object.calculate(
            CurveRequest(mode, parameters, 200.0, 700.0, 9, "ionized", kind, 1.0, n)
        ).curves

    measured = curve("measured")
    for quantity, column in [
        ("seebeck", "seebeck_v_per_k"),
        ("resistivity", "resistivity_ohm_m"),
        ("hall", "hall_m3_per_c"),
    ]:
        np.testing.assert_allclose(
            _evaluate_quantity(quantity, t, parameters, mode, "ionized", n),
            measured[column],
            rtol=1e-13,
        )
    sigma = curve("electrical_conductivity")["electrical_conductivity_s_per_m"]
    np.testing.assert_allclose(sigma * measured["resistivity_ohm_m"], 1.0, rtol=1e-13)
    assert np.all(curve("thermal_conductivity")["thermal_conductivity_w_per_m_k"] > 0)
    if model == "dpb":
        contributions = curve("seebeck_by_band")
        np.testing.assert_allclose(sum(contributions.values()), prediction["seebeck"], rtol=1e-13)
        np.testing.assert_allclose(sum(curve("electrical_conductivity_by_band").values()), sigma)


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_verified_fit_recovers_ionized_conductivity_amplitude(model_id):
    from seeband_core.model_interface import FitRequest, Measurement
    from seeband_core.model_scales import default_start
    from seeband_core.verified_fit import evaluate

    model = registry.get(model_id)
    mode = model.describe().fit_mode(model_id + "_s_rho")
    p = default_start(mode) | {"fermi_energy": -300.0, "A": 60000.0}
    if model_id == "dpb":
        p |= {"m_eff": 1.2, "band_gap": 800.0, "B": 1.0}
    t = np.linspace(150.0, 750.0, 9)
    data = evaluate(model_id, mode.id, p, t, "ionized")
    fitted = {spec.name for spec in mode.parameters_for("ionized") if spec.role == "fitted"}
    measurements = {q: Measurement(t, y) for q, y in data.items()}
    request = FitRequest(
        mode.id, measurements, p | {"A": 1e5}, scattering="ionized", held=frozenset(fitted - {"A"})
    )
    result = model.fit(request)
    assert result.status == "converged", result.message
    assert result.parameters["A"] == pytest.approx(p["A"], rel=1e-10)
    assert result.diagnostics.residuals["resistivity"].relative_l2 < 1e-10
    from dataclasses import replace

    with pytest.raises(ValueError, match="requires verified-sequential-v2"):
        model.fit(replace(request, algorithm="legacy-sequential-v1"))


def test_ionized_initial_estimate_uses_its_scattering_exponent():
    from seeband_core.initial_guess import single_band_guess
    from seeband_core.transport import ionized_transport

    t = np.linspace(100.0, 800.0, 12)
    p = {"band_mass": -1.0, "fermi_energy": -900.0}
    s = ionized_transport(t, p, "spb_s")["seebeck"]
    estimate = single_band_guess("spb", t, s, "ionized")
    assert estimate.start_values["fermi_energy"] == pytest.approx(-900.0, abs=1.0)
    assert estimate.rmse_v_per_k < 1e-8


def test_ionized_limits_and_immutable_scattering():
    from seeband_core.transport import SCATTERING_LAMBDA, band_transport, fermi_integral

    with pytest.raises(TypeError):
        SCATTERING_LAMBDA["ionized"] = 0.0
    t = np.array([300.0, 300.0, 300.0])
    eta = np.array([-40.0, 1e5, -700.0])
    f, s, lorenz, hall = band_transport(t, eta, 1.0, 2.0)
    assert np.all(np.isfinite([f, s, lorenz, hall]))
    assert s[0] / (-mm.kB / mm.e) == pytest.approx(44.0, rel=1e-12)
    assert lorenz[0] / (mm.kB / mm.e) ** 2 == pytest.approx(4.0, rel=1e-12)
    assert s[1] / (-mm.kB / mm.e) == pytest.approx(np.pi**2 / eta[1], rel=1e-7)
    assert lorenz[1] / (mm.kB / mm.e) ** 2 == pytest.approx(np.pi**2 / 3, rel=1e-7)
    assert fermi_integral(3.5, 1000.0) == pytest.approx(reference(1000.0, 3.5), rel=1e-10)


def test_empty_second_band_has_finite_single_band_hall_limit():
    from seeband_core.transport import ionized_transport

    t = np.array([1.0, 20.0])
    p = {
        "m_eff": 1.4,
        "band_gap": 3000.0,
        "fermi_energy": -400.0,
        "A": 20000.0,
        "B": 1.0,
        "m1": 1.2,
    }
    out = ionized_transport(t, p, "dpb_s_rho_rh", 2.0)
    single = ionized_transport(
        t, {"band_mass": -1.2, "fermi_energy": -400.0, "A": 20000.0}, "spb_s_rho_rh"
    )
    assert np.all(np.isfinite(out["hall"]))
    np.testing.assert_allclose(out["hall"], single["hall"], rtol=1e-10)
    no_second = ionized_transport(t, p | {"B": 0.0}, "dpb_s_rho_rh", 2.0)
    np.testing.assert_allclose(no_second["hall"], single["hall"], rtol=1e-10)


def test_two_boltzmann_channels_do_not_square_overflowing_inverse_density():
    from seeband_core.transport import ionized_transport

    p = {"m_eff": 1.4, "band_gap": 800.0, "fermi_energy": 400.0, "A": 20000.0, "B": 1.0, "m1": 1.2}
    result = ionized_transport(np.array([1.0]), p, "dpb_s_rho_rh", 2.0)
    assert np.isfinite(result["hall"][0])
    assert result["hall"][0] == pytest.approx(2.1664969e170, rel=1e-7)


@pytest.mark.parametrize(
    ("gap", "amplitude", "conductivities_underflow", "kappa"),
    [
        (2980.0, 1000.0, True, 0.0),
        (2960.0, 1e6, False, 5e-324),
    ],
)
def test_intrinsic_ionized_transport_keeps_boltzmann_band_weights(
    gap, amplitude, conductivities_underflow, kappa
):
    from seeband_core.model_interface import CurveRequest
    from seeband_core.transport import ionized_transport

    t = np.array([2.0])
    p = {
        "m_eff": 1.0,
        "band_gap": gap,
        "fermi_energy": 1500.0,
        "A": amplitude,
        "B": 1.1,
        "m1": 1.0,
    }
    with np.errstate(divide="ignore", invalid="ignore"):
        result = ionized_transport(t, p, "dpb_s_rho_rh")
        curve = registry.get("dpb").calculate(
            CurveRequest("dpb_s_rho_rh", p, 2.0, 3.0, 2, "ionized", "thermal_conductivity")
        )
    assert result["chemical_potential"][0] == pytest.approx(gap / 2.0)
    for band in (1, 2):
        sigma = result[f"electrical_conductivity_band_{band}"][0]
        assert (sigma == 0.0) == conductivities_underflow
    # The unrounded Boltzmann limits are 2.92e-329 and 4.28e-324 W/(m K).
    assert curve.curves["thermal_conductivity_w_per_m_k"][0] == kappa
    # For equal DOS masses, the Boltzmann mean transport energy is 4 k_B T
    # above each edge, and the relative conductivities are 1:B.
    s1 = mm.kB / mm.e * (4.0 + p["band_gap"] / (2.0 * t[0]))
    assert result["seebeck"][0] == pytest.approx(s1 * (1.0 - p["B"]) / (1.0 + p["B"]), rel=1e-12)
    expected_lorenz = 4.0 * (mm.kB / mm.e) ** 2 + p["B"] * (2.0 * s1 / (1.0 + p["B"])) ** 2
    assert result["lorenz_number"][0] == pytest.approx(expected_lorenz, rel=1e-12)
    assert np.isneginf(result["hall"][0])


def test_independent_ionized_reference_evidence():
    import json
    from pathlib import Path

    from seeband_core.transport import band_transport

    evidence = json.loads((Path(__file__).parent / "fixtures/physics/ionized.json").read_text())
    for case in evidence["cases"]:
        eta = case["eta"]
        _, s, lorenz, hall = band_transport(np.array([300.0]), np.array([eta]), 1.0, 2.0)
        # Independently integrate density; do not reuse the historical F_1/2 approximation.
        density = 4 * np.pi * (2 * mm.me * mm.kB * 300 / mm.h**2) ** 1.5 * reference(eta, 0.5)
        assert abs(s[0]) / (mm.kB / mm.e) == pytest.approx(case["abs_seebeck_over_kb_e"], rel=1e-10)
        assert lorenz[0] / (mm.kB / mm.e) ** 2 == pytest.approx(
            case["lorenz_over_kb_e_squared"], rel=1e-10
        )
        assert abs(hall[0]) * mm.e * density == pytest.approx(case["hall_factor"], rel=1e-10)


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_interleaved_mechanisms_keep_their_own_exponent(model_id):
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import FrozenInstanceError

    from seeband_core.model_interface import CurveRequest
    from seeband_core.model_scales import default_start
    from seeband_core.transport import SCATTERING_LAWS

    with pytest.raises(FrozenInstanceError):
        SCATTERING_LAWS["ionized"].energy_lambda = 0.0
    model = registry.get(model_id)
    mode = model.describe().fit_mode(model_id + "_s_rho_rh")
    parameters = default_start(mode)
    untouched = dict(parameters)

    def calculate(scattering):
        return model.calculate(
            CurveRequest(
                fit_mode=mode.id,
                parameters=parameters,
                scattering=scattering,
                min_temperature_k=200.0,
                max_temperature_k=600.0,
                points=7,
            )
        ).curves

    expected = {mechanism: calculate(mechanism) for mechanism in mode.scattering}
    order = ["acPh", "ionized", "dis", "ionized", "acPh", "dis"]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for mechanism, curves in zip(order, executor.map(calculate, order), strict=True):
            for column, values in curves.items():
                np.testing.assert_array_equal(values, expected[mechanism][column])
    assert parameters == untouched
    assert not np.array_equal(
        expected["acPh"]["seebeck_v_per_k"], expected["ionized"]["seebeck_v_per_k"]
    )
