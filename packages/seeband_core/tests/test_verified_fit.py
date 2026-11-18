"""P19 synthetic regressions for the public model fitting seam."""

import numpy as np
import pytest
from seeband_core import math_module as mm
from seeband_core.band_models import DpbModel, SpbModel
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement
from seeband_core.model_scales import default_start


@pytest.mark.parametrize("fermi_start_k", [0.0, 400.0, 800.0])
def test_verified_recovers_from_the_dpb_gap_and_both_edges(fermi_start_k):
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {
        "m_eff": 1.2,
        "band_gap": 800.0,
        "fermi_energy": fermi_start_k,
    }
    data = load_demo_dataset().measurements["seebeck"]
    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": data},
            start,
            scattering="acPh",
            held=frozenset({"m_eff", "band_gap"}),
        )
    )

    assert result.status == "converged"
    assert result.diagnostics.stage_consistent is True
    assert result.diagnostics.recoveries > 0
    assert result.parameters["m_eff"] == 1.2
    assert result.parameters["band_gap"] == 800.0
    assert result.parameters["fermi_energy"] == pytest.approx(-150.1194, abs=0.002)
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < 0.81


@pytest.mark.parametrize(
    ("truth_k", "energy_tolerance_k", "rmse_limit_uv_per_k"),
    [
        (-0.05, 5e-4, 0.01),
        (800.05, 5e-4, 0.01),
        (-0.0001, 2e-6, 3e-5),
        (800.0001, 2e-6, 3e-5),
    ],
)
@pytest.mark.parametrize("one_side_only", [False, True])
def test_verified_distinguishes_light_doping_just_outside_either_gap_edge(
    truth_k, energy_tolerance_k, rmse_limit_uv_per_k, one_side_only
):
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 400.0}
    temperature_k = np.linspace(50.0, 800.0, 31)
    values = mm.dpb_see_vs_temp(temperature_k, 1.2, 800.0, truth_k, 1.0)
    bounds = {}
    if one_side_only:
        bounds["fermi_energy"] = Bounds(min(0.0, truth_k), max(800.0, truth_k))

    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": Measurement(temperature_k, values)},
            start,
            bounds=bounds,
            scattering="acPh",
            held=frozenset({"m_eff", "band_gap"}),
        )
    )

    assert result.status == "converged"
    assert result.diagnostics.stage_consistent
    energy = result.parameters["fermi_energy"]
    assert energy == pytest.approx(truth_k, abs=energy_tolerance_k)
    if one_side_only:
        assert bounds["fermi_energy"].lower <= energy <= bounds["fermi_energy"].upper
        assert "fermi_energy" in result.at_bounds
    assert result.parameters["m_eff"] == 1.2
    assert result.parameters["band_gap"] == 800.0
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < rmse_limit_uv_per_k
    assert "fermi_energy" not in result.diagnostics.unidentified
    assert "fermi_energy_in_gap" not in result.known_issues


def test_verified_recovers_after_other_free_parameters_move_on_the_dpb_plateau():
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 0.0}
    data = load_demo_dataset().measurements["seebeck"]

    result = model.fit(FitRequest(mode.id, {"seebeck": data}, start, scattering="acPh"))

    assert result.status == "converged"
    assert result.diagnostics.stage_consistent
    assert result.diagnostics.recoveries > 0
    assert result.parameters["fermi_energy"] < 0.0
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < 1.0
    assert "fermi_energy_in_gap" not in result.known_issues
    for spec in mode.parameters:
        if spec.fit_bounds is not None:
            value = result.parameters[spec.name]
            assert spec.fit_bounds.lower <= value <= spec.fit_bounds.upper


@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho_rh"])
def test_verified_all_free_demo_escapes_the_conduction_onset(mode_id):
    model = DpbModel()
    mode = model.describe().fit_mode(mode_id)
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 800.0}
    data = load_demo_dataset().measurements

    result = model.fit(
        FitRequest(mode_id, {q: data[q] for q in mode.quantities}, start, scattering="acPh")
    )

    assert result.status == "converged"
    assert result.diagnostics is not None
    assert result.diagnostics.stage_consistent
    assert result.diagnostics.recoveries > 0
    assert result.parameters["fermi_energy"] < 0.0
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < 0.82
    for residual in result.diagnostics.residuals.values():
        assert residual.relative_l2 is not None and residual.relative_l2 < 0.01
    for spec in mode.parameters_for("acPh"):
        if spec.fit_bounds is not None:
            assert spec.fit_bounds.lower <= result.parameters[spec.name] <= spec.fit_bounds.upper


@pytest.mark.parametrize(("fermi_start_k", "lower_k"), [(400.0, 0.0), (800.0, 800.0)])
def test_verified_can_recover_to_the_conduction_side_when_the_valence_side_is_excluded(
    fermi_start_k, lower_k
):
    from seeband_core.verified_fit import evaluate

    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {
        "m_eff": 1.2,
        "band_gap": 800.0,
        "fermi_energy": fermi_start_k,
    }
    temperature_k = np.linspace(100.0, 800.0, 18)
    values = evaluate("dpb", mode.id, start | {"fermi_energy": 1000.0}, temperature_k, "acPh")[
        "seebeck"
    ]
    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": Measurement(temperature_k, values)},
            start,
            bounds={"fermi_energy": Bounds(lower_k, 1100.0)},
            scattering="acPh",
            held=frozenset({"m_eff", "band_gap"}),
        )
    )

    assert result.status == "converged"
    assert result.parameters["fermi_energy"] == pytest.approx(1000.0, abs=1e-4)
    assert result.diagnostics.residuals["seebeck"].rmse < 1e-10


@pytest.mark.parametrize(
    ("gap_upper_k", "fermi_lower_k", "expected_gap_k", "expected_fermi_k", "rmse_limit"),
    [
        (800.0, -3000.0, 799.8726, -150.1328, 0.81),
        (3000.0, -3000.0, 799.8726, -150.1328, 0.81),
        (800.0, 500.0, 800.0, 800.10156, 61.12),
    ],
)
def test_verified_recovers_with_the_gap_free_at_the_conduction_edge(
    gap_upper_k, fermi_lower_k, expected_gap_k, expected_fermi_k, rmse_limit, monkeypatch
):
    from seeband_core import verified_fit

    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 800.0}
    bounds = {"band_gap": Bounds(300.0, gap_upper_k), "fermi_energy": Bounds(fermi_lower_k, 3000.0)}
    original = verified_fit._evaluate_quantity

    def check_bounds(quantity, temperatures, parameters, *args, **kwargs):
        for name, limit in bounds.items():
            assert limit.lower <= parameters[name] <= limit.upper
        assert parameters["m_eff"] == 1.2
        return original(quantity, temperatures, parameters, *args, **kwargs)

    monkeypatch.setattr(verified_fit, "_evaluate_quantity", check_bounds)
    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": load_demo_dataset().measurements["seebeck"]},
            start,
            bounds=bounds,
            scattering="acPh",
            held=frozenset({"m_eff"}),
        )
    )

    assert result.status == "converged"
    assert result.diagnostics.stage_consistent is True
    assert result.diagnostics.recoveries > 0
    assert result.parameters["m_eff"] == 1.2
    assert 300.0 <= result.parameters["band_gap"] <= gap_upper_k
    assert result.parameters["band_gap"] == pytest.approx(expected_gap_k, abs=0.02)
    assert result.parameters["fermi_energy"] == pytest.approx(expected_fermi_k, abs=0.01)
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < rmse_limit


@pytest.mark.parametrize(
    ("true_gap_k", "true_fermi_k", "upper_fermi_k"),
    [(650.0, 1000.0, 1400.0), (900.0, 800.0, 800.0)],
)
def test_verified_can_find_a_free_gap_from_the_conduction_edge(
    true_gap_k, true_fermi_k, upper_fermi_k
):
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 800.0}
    temperature_k = np.linspace(100.0, 800.0, 18)
    values = mm.dpb_see_vs_temp(temperature_k, 1.2, true_gap_k, true_fermi_k, 1.0)
    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": Measurement(temperature_k, values)},
            start,
            bounds={"band_gap": Bounds(300.0, 1200.0), "fermi_energy": Bounds(0.0, upper_fermi_k)},
            scattering="acPh",
            held=frozenset({"m_eff"}),
        )
    )

    assert result.status == "converged"
    assert result.parameters["band_gap"] == pytest.approx(true_gap_k, abs=1e-4)
    assert result.diagnostics.residuals["seebeck"].rmse < 1e-10
    if true_fermi_k > true_gap_k:
        assert result.parameters["fermi_energy"] == pytest.approx(true_fermi_k, abs=1e-4)
        assert "fermi_energy_in_gap" not in result.known_issues
    else:
        assert "fermi_energy_in_gap" in result.known_issues


@pytest.mark.parametrize("hold_fermi", [False, True])
def test_verified_keeps_an_exact_fit_at_the_gap_upper_bound(hold_fermi):
    model = DpbModel()
    start = {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 800.0}
    temperature_k = np.linspace(100.0, 800.0, 18)
    values = mm.dpb_see_vs_temp(temperature_k, 1.2, 800.0, 800.0, 1.0)
    result = model.fit(
        FitRequest(
            "dpb_s",
            {"seebeck": Measurement(temperature_k, values)},
            start,
            bounds={"band_gap": Bounds(300.0, 800.0)},
            scattering="acPh",
            held=frozenset({"m_eff", "fermi_energy"} if hold_fermi else {"m_eff"}),
        )
    )

    assert result.status == "converged"
    assert result.parameters == start
    assert "band_gap" in result.at_bounds
    assert "fermi_energy_in_gap" in result.known_issues
    assert result.diagnostics.residuals["seebeck"].rmse == 0.0


def test_verified_recovers_with_fermi_energy_held_at_the_upper_gap_edge(monkeypatch):
    from seeband_core import verified_fit

    start = {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 800.0}
    bounds = {"band_gap": Bounds(300.0, 800.0), "fermi_energy": Bounds(800.0, 900.0)}
    original = verified_fit._evaluate_quantity

    def check_bounds(quantity, temperatures, parameters, *args, **kwargs):
        assert 300.0 <= parameters["band_gap"] <= 800.0
        assert parameters["fermi_energy"] == 800.0
        assert parameters["m_eff"] == 1.2
        return original(quantity, temperatures, parameters, *args, **kwargs)

    monkeypatch.setattr(verified_fit, "_evaluate_quantity", check_bounds)
    result = DpbModel().fit(
        FitRequest(
            "dpb_s",
            {"seebeck": load_demo_dataset().measurements["seebeck"]},
            start,
            bounds=bounds,
            scattering="acPh",
            held=frozenset({"m_eff", "fermi_energy"}),
        )
    )

    assert result.status == "converged"
    assert result.diagnostics.stage_consistent is True
    assert result.parameters["fermi_energy"] == 800.0
    assert result.parameter_status["fermi_energy"] == "held"
    assert 300.0 <= result.parameters["band_gap"] <= 800.0
    assert result.parameters["band_gap"] == pytest.approx(799.8984, abs=0.001)
    assert result.diagnostics.residuals["seebeck"].rmse * 1e6 < 61.13


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
def test_verified_profiles_tiny_reciprocal_amplitude(scattering, sign):
    t = np.linspace(100.0, 800.0, 16)
    f = mm.spb_fermiInt_vs_temp(0, t, sign, sign * 165.0)
    if scattering == "acPh":
        q = mm.spb_rho_vs_temp_acPh(t, f, 1.0)
    elif scattering == "dis":
        q = mm.spb_rho_vs_temp_dis(t, f, 1.0)
    else:
        from seeband_core.transport import ionized_transport

        q = ionized_transport(
            t, {"band_mass": sign, "fermi_energy": sign * 165.0, "A": 1.0}, "spb_s_rho"
        )["resistivity"]
    amplitude = np.linalg.norm(q * 1e8) / np.sqrt(len(t)) / 100.0
    start = dict(band_mass=sign, fermi_energy=sign * 165.0, A=1e7, F=1e7)
    name = "F" if scattering == "dis" else "A"
    held = {"fermi_energy"}
    result = SpbModel().fit(
        FitRequest(
            "spb_s_rho",
            {
                "seebeck": Measurement(
                    t,
                    (
                        ionized_transport(
                            t, {"band_mass": sign, "fermi_energy": sign * 165.0}, "spb_s"
                        )["seebeck"]
                        if scattering == "ionized"
                        else mm.spb_see_vs_temp(t, sign * 165.0, sign)
                    ),
                ),
                "resistivity": Measurement(t, q / amplitude),
            },
            start,
            {name: Bounds(0.0, 1e8)},
            scattering,
            held=frozenset(held),
        )
    )
    assert result.parameters[name] == pytest.approx(amplitude, rel=1e-10)
    assert result.algorithm == "verified-sequential-v2"
    assert result.diagnostics.residuals["resistivity"].relative_l2 < 1e-10
    assert result.parameter_errors == {}


@pytest.mark.parametrize("n", [1.0, 3.0])
@pytest.mark.parametrize("r", [1.2, -1.2, 1e-10, -1e-10])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_dpb_amplitude_keeps_public_mass_and_held_shapes(n, r, scattering):
    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s_rho")
    p = dict(
        default_start(mode),
        m_eff=r * n,
        band_gap=-500.0,
        fermi_energy=-165.0,
        A=1.0,
        B=200.0,
        F=1.0,
        G=200.0,
    )
    curves = model.calculate(
        CurveRequest(mode.id, p, 100.0, 800.0, 16, scattering, band_2_degeneracy=n)
    )
    q = curves.curves["resistivity_ohm_m"]
    amplitude = np.linalg.norm(q * 1e8) / 4 / 100.0
    name = "F" if scattering == "dis" else "A"
    fitted = {s.name for s in mode.parameters_for(scattering) if s.role == "fitted"}
    result = model.fit(
        FitRequest(
            mode.id,
            {
                "seebeck": Measurement(curves.temperature_k, curves.curves["seebeck_v_per_k"]),
                "resistivity": Measurement(curves.temperature_k, q / amplitude),
            },
            p | {name: 4.27200527},
            bounds={
                name: Bounds(0.0, 1e8),
                "m_eff": Bounds(-10.0, 10.0),
                "B": Bounds(0.0, 300.0),
                "G": Bounds(0.0, 300.0),
            },
            scattering=scattering,
            band_2_degeneracy=n,
            held=frozenset(fitted - {name}),
        )
    )
    assert result.status == "converged"
    assert result.parameters[name] == pytest.approx(amplitude, rel=2e-12)
    assert result.parameters["m_eff"] == r * n
    assert "dpb_loop_degeneracy" not in result.known_issues


def test_outer_loop_does_not_accept_stale_seebeck_optimum():
    t = np.linspace(100.0, 800.0, 16)
    truth = [1.2, 800.0, -150.0]
    s = mm.dpb_see_vs_temp_single_scatter(t, *truth, 1.0, 2.0)
    f1, f2 = mm.dpb_fermiInt_vs_temp(0, t, *truth, 1.0)
    rho = mm.dpb_rho_vs_temp_acPh(t, f1, f2, 1e5, 2.0, truth[0])
    p = dict(m_eff=1.0, band_gap=700.0, fermi_energy=-180.0, A=1e5, B=0.5, F=1.0, G=1.0)
    bounds = {
        "m_eff": Bounds(0.1, 3.0),
        "band_gap": Bounds(100.0, 2000.0),
        "fermi_energy": Bounds(-500.0, -10.0),
        "B": Bounds(0.0, 10.0),
    }
    request = FitRequest(
        "dpb_s_rho",
        {"seebeck": Measurement(t, s), "resistivity": Measurement(t, rho)},
        p,
        bounds,
        "acPh",
    )
    result = DpbModel().fit(request)
    assert result.status != "failed"
    # The reproduced old false convergence has SSE=1235.87, with a conditional optimum=.6102.
    assert result.status != "converged" or result.diagnostics.objectives["seebeck"] < 1.0
    assert result.diagnostics.stage_consistent == (result.status == "converged")


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("n", [1.0, 3.0])
def test_hall_inverse_amplitude_matches_curves(model_id, scattering, sign, n):
    model = DpbModel() if model_id == "dpb" else SpbModel()
    mode = model.describe().fit_mode(model_id + "_s_rho_rh")
    p = dict(
        default_start(mode),
        fermi_energy=-165.0,
        A=1e5,
        F=1e5,
    )
    if model_id == "dpb":
        p.update(m_eff=sign * 1.2 * n, band_gap=-500.0, B=2.0, G=2.0, m1=2.3)
        name = "m1"
    else:
        p.update(band_mass=sign * 2.3, fermi_energy=sign * 165.0)
        name = "band_mass"
    curves = model.calculate(
        CurveRequest(mode.id, p, 100.0, 800.0, 8, scattering, band_2_degeneracy=n)
    )
    data = {
        q: Measurement(curves.temperature_k, curves.curves[key])
        for q, key in [
            ("seebeck", "seebeck_v_per_k"),
            ("resistivity", "resistivity_ohm_m"),
            ("hall", "hall_m3_per_c"),
        ]
    }
    fitted = {s.name for s in mode.parameters_for(scattering) if s.role == "fitted"}
    result = model.fit(
        FitRequest(
            mode.id,
            data,
            p | {name: np.sign(p[name]) * 2.8},
            bounds=(
                {
                    "C": Bounds(0.0, 10.0),
                    "D": Bounds(0.0, 10.0),
                    "B": Bounds(0.0, 10.0),
                    "m_eff": Bounds(-10.0, 10.0),
                }
                if model_id == "dpb"
                else {"C": Bounds(0.0, 10.0)}
            ),
            scattering=scattering,
            band_2_degeneracy=n,
            held=frozenset(fitted - {name}),
        )
    )
    assert result.status == "converged"
    assert result.parameters[name] == pytest.approx(p[name], rel=2e-12)
    assert result.diagnostics.residuals["hall"].relative_l2 < 3e-12
    assert result.diagnostics.uncertainty == "not_assessed"
    assert result.parameter_errors == {}


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("n", [1.0, 3.0])
def test_seebeck_only_uses_public_coordinates_and_custom_bounds(model_id, sign, n):
    model = DpbModel() if model_id == "dpb" else SpbModel()
    mode = model.describe().fit_mode(model_id + "_s")
    p = dict(default_start(mode), fermi_energy=-165.0)
    if model_id == "dpb":
        p.update(m_eff=sign * 1.2 * n, band_gap=-500.0)
        held = frozenset({"m_eff", "band_gap"})
    else:
        p.update(band_mass=sign, fermi_energy=sign * 165.0)
        held = frozenset()
    curves = model.calculate(CurveRequest(mode.id, p, 100.0, 800.0, 8, band_2_degeneracy=n))
    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": Measurement(curves.temperature_k, curves.curves["seebeck_v_per_k"])},
            p | {"fermi_energy": p["fermi_energy"] * 1.1},
            (
                {"fermi_energy": Bounds(-1000.0, 1000.0), "m_eff": Bounds(-10.0, 10.0)}
                if model_id == "dpb"
                else {"fermi_energy": Bounds(-1000.0, 1000.0)}
            ),
            band_2_degeneracy=n,
            held=held,
        )
    )
    assert result.status == "converged"
    assert result.parameters["fermi_energy"] == pytest.approx(p["fermi_energy"], rel=1e-7)
    assert result.diagnostics.residuals["seebeck"].relative_l2 < 1e-8


def test_inverse_amplitude_respects_active_user_bound_and_measured_residuals():
    from seeband_core.verified_fit import evaluate

    t = np.array([101.0, 153.0, 251.0, 589.0, 799.0])
    p = dict(band_mass=-1.0, fermi_energy=-165.0, A=1e5, F=1.0)
    truth = evaluate("spb", "spb_s_rho", p, t, "acPh")
    request = FitRequest(
        "spb_s_rho",
        {q: Measurement(t, v) for q, v in truth.items()},
        p | {"A": 1e4},
        {"A": Bounds(1e3, 5e4)},
        "acPh",
        held=frozenset({"fermi_energy"}),
    )
    result = SpbModel().fit(request)
    assert result.parameters["A"] == pytest.approx(5e4)
    assert "A" in result.at_bounds
    final = evaluate("spb", "spb_s_rho", result.parameters, t, "acPh")
    for q in truth:
        expected = np.linalg.norm(final[q] - truth[q]) / np.sqrt(t.size)
        assert result.diagnostics.residuals[q].rmse == pytest.approx(expected, abs=1e-25)
    assert result.diagnostics.residual_adequacy == "not_assessed"


def test_valid_domain_numerical_failure_is_not_a_rejected_trial(monkeypatch):
    from seeband_core.math_module import ChemicalPotentialError

    t = np.array([100.0, 200.0])
    p = dict(band_mass=-1.0, fermi_energy=-165.0)

    def broken(*args, **kwargs):
        raise ChemicalPotentialError(None, "synthetic numerical failure")

    monkeypatch.setattr(mm, "spb_see_vs_temp", broken)
    result = SpbModel().fit(FitRequest("spb_s", {"seebeck": Measurement(t, t * 0.0)}, p))
    assert result.status == "failed"
    assert result.parameters == p
    assert result.diagnostics.termination == "numerical_failure"
    assert result.algorithm == "verified-sequential-v2"


@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho"])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
def test_nonunit_degeneracy_fits_mass_in_public_custom_interval(mode_id, sign):
    model = DpbModel()
    mode = model.describe().fit_mode(mode_id)
    p = dict(default_start(mode), m_eff=sign * 3.6, band_gap=-500.0, fermi_energy=-165.0)
    if mode_id.endswith("rho"):
        p.update(A=1e5, B=2.0)
    scattering = "acPh" if mode_id.endswith("rho") else None
    curves = model.calculate(
        CurveRequest(mode_id, p, 100.0, 800.0, 8, scattering, band_2_degeneracy=3.0)
    )
    data = {"seebeck": Measurement(curves.temperature_k, curves.curves["seebeck_v_per_k"])}
    if scattering:
        data["resistivity"] = Measurement(curves.temperature_k, curves.curves["resistivity_ohm_m"])
    fitted = {s.name for s in mode.parameters_for(scattering) if s.role == "fitted"}
    bounds = Bounds(3.0, 4.0) if sign > 0 else Bounds(-4.0, -3.0)
    result = model.fit(
        FitRequest(
            mode_id,
            data,
            p | {"m_eff": sign * 3.2},
            {"m_eff": bounds, **({"B": Bounds(0.0, 10.0)} if scattering else {})},
            scattering,
            band_2_degeneracy=3.0,
            held=frozenset(fitted - {"m_eff"}),
        )
    )
    assert result.status == "converged"
    assert result.parameters["m_eff"] == pytest.approx(p["m_eff"], rel=1e-7)
    assert "m_eff" not in result.at_bounds


def test_compensated_zero_hall_keeps_unidentified_mass_and_nullable_relative_residual():
    from seeband_core.verified_fit import evaluate

    model = DpbModel()
    mode = model.describe().fit_mode("dpb_s_rho_rh")
    p = dict(
        default_start(mode),
        m_eff=1.0,
        band_gap=0.0,
        fermi_energy=0.0,
        A=1e5,
        B=1.0,
        m1=2.0,
    )
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("dpb", mode.id, p, t, "ionized")
    assert np.all(data["hall"] == 0.0)
    fitted = {s.name for s in mode.parameters_for("ionized") if s.role == "fitted"}
    result = model.fit(
        FitRequest(
            mode.id,
            {q: Measurement(t, v) for q, v in data.items()},
            p,
            scattering="ionized",
            held=frozenset(fitted - {"m1"}),
        )
    )
    assert result.status == "converged"
    assert result.parameters["m1"] == 2.0
    assert "m1" in result.diagnostics.unidentified
    assert result.diagnostics.residuals["hall"].relative_l2 is None
    assert result.diagnostics.residuals["hall"].rmse == 0.0
    assert result.parameter_errors == {}


def test_zero_amplitude_remains_an_admissible_fit_start():
    from seeband_core.verified_fit import evaluate

    mode = SpbModel().describe().fit_mode("spb_s_rho")
    p = dict(default_start(mode), band_mass=-1.0, fermi_energy=-165.0, A=1e5)
    t = np.linspace(100.0, 800.0, 8)
    data = evaluate("spb", mode.id, p, t, "ionized")
    result = SpbModel().fit(
        FitRequest(
            mode.id,
            {q: Measurement(t, v) for q, v in data.items()},
            p | {"A": 0.0},
            {"A": Bounds(0.0, 1e7)},
            "ionized",
            held=frozenset({"fermi_energy"}),
        )
    )
    assert result.status == "converged"
    assert result.parameters["A"] == pytest.approx(1e5, rel=1e-7)


def test_invalid_density_start_fails_without_fallback():
    t = np.array([100.0, 200.0])
    result = SpbModel().fit(
        FitRequest(
            "spb_s",
            {"seebeck": Measurement(t, np.zeros(2))},
            {"band_mass": 1.0, "fermi_energy": 0.0},
        )
    )
    assert result.status == "failed"
    assert result.algorithm == "verified-sequential-v2"
    assert result.diagnostics.stage_consistent is False


def test_verified_derivative_reverses_real_density_domain_stencil(monkeypatch):
    def certified_model(t, r, gap, ef, n, *, potentials=None):
        mm.dpb_chemPot_vs_temp(t, gap, r, ef, n)
        return np.full(t.shape, ef * 1e-6)

    monkeypatch.setattr(mm, "dpb_see_vs_temp", certified_model)
    t = np.array([100.0, 200.0, 300.0])
    request = FitRequest(
        "dpb_s",
        {"seebeck": Measurement(t, np.full(3, 0.75e-6))},
        {"m_eff": -1.0, "band_gap": 1.0, "fermi_energy": 1.0 - 1e-12},
        {"fermi_energy": Bounds(0.0, 2.0)},
        held=frozenset({"m_eff", "band_gap"}),
    )
    result = DpbModel().fit(request)
    assert result.status == "converged"
    assert result.parameters["fermi_energy"] == pytest.approx(0.75, abs=1e-8)


def _callback_request():
    from seeband_core.verified_fit import evaluate

    p = dict(
        default_start(DpbModel().describe().fit_mode("dpb_s_rho")),
        m_eff=1.2,
        band_gap=-500.0,
        fermi_energy=-165.0,
        A=1e5,
        B=2.0,
    )
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("dpb", "dpb_s_rho", p, t, "acPh")
    request = FitRequest(
        "dpb_s_rho",
        {q: Measurement(t, v) for q, v in data.items()},
        p | {"A": 1e6},
        bounds={"B": Bounds(0.0, 10.0)},
        scattering="acPh",
        held=frozenset({"m_eff", "band_gap", "fermi_energy", "B"}),
    )
    return request, p


def test_verified_callback_stop_preserves_latest_endpoint_and_diagnostics():
    from seeband_core.model_interface import FitStopped

    request, p = _callback_request()
    updates = []

    def stop(update):
        updates.append(update)
        raise FitStopped

    result = DpbModel().fit(request, stop)
    assert result.status == "stopped"
    assert result.diagnostics.termination == "callback"
    assert len(updates) == 1
    assert result.parameters == updates[0].parameters
    assert result.parameters["A"] == pytest.approx(p["A"])
    assert result.diagnostics.residuals["resistivity"].relative_l2 < 1e-12


def test_verified_callback_exception_propagates():
    request, _ = _callback_request()

    def broken(update):
        raise LookupError("synthetic callback failure")

    with pytest.raises(LookupError, match="synthetic callback failure"):
        DpbModel().fit(request, broken)


def test_exhausted_shared_budget_keeps_usable_endpoint_and_residuals(monkeypatch):
    from dataclasses import replace

    from seeband_core import verified_fit

    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 4)
    request, p = _callback_request()
    # Require a new derivative stencil: the amplitude-only proof now fits wholly
    # inside the old budget because identical predictions are cached.
    request = replace(request, held=request.held - {"fermi_energy"})
    result = DpbModel().fit(request)
    assert result.status == "iteration_limit"
    assert result.diagnostics.termination == "evaluation_budget"
    assert result.diagnostics.stage_consistent is False
    assert result.parameters["A"] == pytest.approx(p["A"])
    assert result.diagnostics.residuals["resistivity"].relative_l2 < 1e-12


def test_solver_no_step_exit_cannot_certify_stage_optimality(monkeypatch):
    from scipy.optimize import OptimizeResult
    from seeband_core import verified_fit

    def no_step(fun, x, *, jac, **kwargs):
        return OptimizeResult(x=np.array(x), fun=fun(x), jac=jac(x), optimality=0.0, success=True)

    monkeypatch.setattr(verified_fit, "least_squares", no_step)
    t = np.array([100.0, 200.0, 500.0])
    s = mm.spb_see_vs_temp(t, -165.0, -1.0)
    result = SpbModel().fit(
        FitRequest(
            "spb_s", {"seebeck": Measurement(t, s)}, {"band_mass": -1.0, "fermi_energy": -100.0}
        )
    )
    assert result.status != "converged"
    assert result.diagnostics.stage_consistent is False
    assert result.diagnostics.optimality["seebeck"] > 1e-3


def test_held_value_outside_original_bounds_is_a_failed_start():
    request, _ = _callback_request()
    from dataclasses import replace

    result = DpbModel().fit(replace(request, bounds={"B": Bounds(0.9, 1.1)}))
    assert result.status == "failed"
    assert result.parameters == request.start
    assert result.diagnostics.termination == "numerical_failure"


def test_free_zero_amplitude_start_is_eliminated_without_a_mass_floor():
    from seeband_core.verified_fit import evaluate

    p = dict(band_mass=-1.0, fermi_energy=-165.0, A=1e5, F=1.0)
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("spb", "spb_s_rho", p, t, "acPh")
    result = SpbModel().fit(
        FitRequest(
            "spb_s_rho",
            {q: Measurement(t, v) for q, v in data.items()},
            p | {"A": 0.0},
            {"A": Bounds(0.0, 1e7)},
            "acPh",
            held=frozenset({"fermi_energy"}),
        )
    )
    assert result.status == "converged"
    assert result.parameters["A"] == pytest.approx(1e5, rel=1e-12)


def test_final_identifiability_drops_transient_compensated_hall_flag():
    from seeband_core.verified_fit import evaluate

    mode = DpbModel().describe().fit_mode("dpb_s_rho_rh")
    p = dict(default_start(mode), m_eff=1.0, band_gap=0.0, fermi_energy=0.0, A=1e5, B=2.0, m1=2.3)
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("dpb", mode.id, p, t, "acPh")
    fitted = {s.name for s in mode.parameters_for("acPh") if s.role == "fitted"}
    result = DpbModel().fit(
        FitRequest(
            mode.id,
            {q: Measurement(t, v) for q, v in data.items()},
            p | {"B": 1.0, "m1": 2.8},
            {"B": Bounds(0.0, 10.0)},
            "acPh",
            held=frozenset(fitted - {"B", "m1"}),
        )
    )
    assert result.status == "converged"
    assert result.parameters["B"] == pytest.approx(2.0, rel=1e-7)
    assert result.parameters["m1"] == pytest.approx(2.3, rel=1e-7)
    assert "m1" not in result.diagnostics.unidentified


def test_stationary_nonzero_residual_stage_does_not_restart():
    from seeband_core.verified_fit import evaluate

    p = dict(band_mass=-1.0, fermi_energy=-165.0)
    t = np.array([100.0, 200.0, 500.0])
    truth = evaluate("spb", "spb_s", p, t, None)["seebeck"]
    # A symmetric orthogonal perturbation leaves a nonzero residual at a stationary
    # scalar optimum. First fit it, then repeat from that returned optimum.
    data = truth + np.array([1.0, -2.0, 1.0]) * 1e-7
    request = FitRequest("spb_s", {"seebeck": Measurement(t, data)}, p)
    first = SpbModel().fit(request)
    from dataclasses import replace

    second = SpbModel().fit(replace(request, start=first.parameters))
    assert second.diagnostics.residuals["seebeck"].rmse > 0.0
    assert second.diagnostics.recoveries == 0


def test_budget_before_first_rho_stage_never_loses_singular_start_endpoint(monkeypatch):
    from seeband_core import verified_fit
    from seeband_core.verified_fit import evaluate

    p = dict(band_mass=-1.0, fermi_energy=-165.0, A=1e5, F=1.0)
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("spb", "spb_s_rho", p, t, "acPh")
    request = FitRequest(
        "spb_s_rho",
        {q: Measurement(t, v) for q, v in data.items()},
        p | {"A": 0.0, "fermi_energy": -100.0},
        {"A": Bounds(0.0, 1e7)},
        "acPh",
    )
    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 5)
    result = SpbModel().fit(request)
    assert result.status == "iteration_limit"
    assert result.parameters["A"] > 0.0
    assert np.isfinite(result.diagnostics.residuals["resistivity"].rmse)
    # Even a budget too small to certify a finite endpoint returns explicit failure.
    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 1)
    result = SpbModel().fit(request)
    assert result.status == "failed"
    assert result.parameters == request.start
    assert result.diagnostics.termination == "budget_before_valid_endpoint"


@pytest.mark.parametrize("mass,message", [(0.0, "bounds"), (1.0, "sign of the start band mass")])
def test_verified_hall_rejects_singular_or_wrong_carrier_start(mass, message):
    from seeband_core.verified_fit import evaluate

    mode = SpbModel().describe().fit_mode("spb_s_rho_rh")
    p = dict(default_start(mode), band_mass=-1.0, fermi_energy=-165.0, A=1e5)
    t = np.array([100.0, 200.0, 500.0])
    data = evaluate("spb", mode.id, p, t, "acPh")
    result = SpbModel().fit(
        FitRequest(
            mode.id,
            {q: Measurement(t, v) for q, v in data.items()},
            p | {"band_mass": mass},
            scattering="acPh",
        )
    )
    assert result.status == "failed"
    assert message in result.message


def test_budget_optimality_is_recomputed_at_returned_vector(monkeypatch):
    from seeband_core import verified_fit

    # A linear physical-model stand-in has exact normalized projected gradient 1
    # at this endpoint. The budget interrupts the first stage before any audit.
    monkeypatch.setattr(
        mm, "spb_see_vs_temp", lambda t, ef, mass, *, potentials=None: np.full(t.shape, ef * 1e-6)
    )
    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 5)
    t = np.array([100.0, 200.0, 500.0])
    result = SpbModel().fit(
        FitRequest(
            "spb_s",
            {"seebeck": Measurement(t, np.full(3, 1e-6))},
            {"band_mass": 1.0, "fermi_energy": 2.0},
        )
    )
    assert result.status == "iteration_limit"
    assert result.parameters["fermi_energy"] == 2.0
    assert result.diagnostics.optimality["seebeck"] == pytest.approx(1.0, rel=1e-7)


def _recorded_d1_request():
    import json
    from pathlib import Path

    from seeband_core.model_descriptions import DPB_BANDS, DPB_SCATTERING

    document = json.loads(
        (Path(__file__).parent / "fixtures/golden/01_Fe2VAl09Si01.json").read_text()
    )
    a = document["d1_with_g_minimum_1"]["calls"][0]["args"]
    names = (*DPB_BANDS, *DPB_SCATTERING, "m1")
    values = (*a[6], *a[8], a[10])
    low = (*a[7][0], *a[9][0], a[11][0][0])
    high = (*a[7][1], *a[9][1], a[11][1][0])
    return FitRequest(
        "dpb_s_rho_rh",
        {
            q: Measurement(np.asarray(a[i]), np.asarray(a[i + 1]))
            for q, i in [("seebeck", 0), ("resistivity", 2), ("hall", 4)]
        },
        dict(zip(names, values, strict=True)),
        {n: Bounds(lo, hi) for n, lo, hi in zip(names, low, high, strict=True)},
        a[13],
        band_2_degeneracy=a[12],
    )


def test_recorded_d1_small_mass_point_has_validated_nonzero_log_derivative():
    from seeband_core import verified_fit

    request = _recorded_d1_request()
    point = dict(
        request.start,
        m_eff=5.698306848172846e-6 * 1.2407726485946857,
        band_gap=-0.7952429398824362 * 655.3377724781157,
        fermi_energy=-0.12629120121199444 * 1296.2885635374228,
        F=4.272005067669233,
        G=199.99999999999997,
        m1=10.0,
    )
    mode = DpbModel().describe().fit_mode(request.fit_mode)
    engine = verified_fit._Engine(request, mode)
    coordinate = verified_fit._Coordinates(["m_eff"], point, engine.bound)

    def residual(z):
        return (
            engine.predict("seebeck", point | coordinate.decode(z)) * 1e6
            - engine.data["seebeck"][1] * 1e6
        )

    jac = verified_fit._validated_jacobian(
        residual, coordinate.point, coordinate.lower, coordinate.upper
    )
    assert np.all(np.isfinite(jac))
    assert np.linalg.norm(jac) > 0.0
    # Independent second-order log secant at a larger step; the production
    # fourth-order estimate must agree without assigning a zero gradient.
    h = 0.003
    independent = (residual(coordinate.point + h) - residual(coordinate.point - h)) / (2 * h)
    assert np.linalg.norm(jac[:, 0] - independent) / np.linalg.norm(independent) < 1e-3


def test_recorded_d1_full_route_crosses_old_derivative_failure_with_finite_budget(monkeypatch):
    from seeband_core import verified_fit

    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 1000)
    result = DpbModel().fit(_recorded_d1_request())
    assert result.status != "failed"
    assert result.diagnostics.termination in {
        "evaluation_budget",
        "conditional_stage_optima",
        "cycle_or_stall",
        "sweep_budget",
    }
    assert set(result.diagnostics.residuals) == {"seebeck", "resistivity", "hall"}
    assert all(np.isfinite(r.rmse) for r in result.diagnostics.residuals.values())


def test_terminal_derivative_failure_after_budget_keeps_its_own_reason(monkeypatch):
    from seeband_core import verified_fit
    from seeband_core.math_module import ChemicalPotentialError

    error = verified_fit.DerivativeValidationError("synthetic unresolved derivative")
    assert not isinstance(error, ChemicalPotentialError)

    def unresolved(*args, **kwargs):
        raise error

    monkeypatch.setattr(verified_fit, "_validated_jacobian", unresolved)
    monkeypatch.setattr(verified_fit, "_MAX_EVALUATIONS", 1)
    t = np.array([100.0, 200.0, 500.0])
    result = SpbModel().fit(
        FitRequest(
            "spb_s",
            {"seebeck": Measurement(t, np.zeros(3))},
            {"band_mass": -1.0, "fermi_energy": -165.0},
        )
    )
    assert result.status == "failed"
    assert result.diagnostics.termination == "derivative_validation_failure"
    assert "derivative" in result.message
    assert "chemical-potential" not in result.message


@pytest.mark.parametrize("points,calls", [(10, 1), (10001, 2)])
def test_exact_prediction_memo_reuses_only_bounded_complete_inputs(monkeypatch, points, calls):
    from seeband_core import verified_fit

    request, p = _callback_request()
    mode = DpbModel().describe().fit_mode(request.fit_mode)
    engine = verified_fit._Engine(request, mode)
    t = np.linspace(100.0, 800.0, points)
    engine.data["seebeck"] = (t, np.zeros(points))
    actual = []

    def physical(q, t, parameters, *args, **kwargs):
        actual.append((q, dict(parameters)))
        return np.full(t.shape, parameters["fermi_energy"])

    monkeypatch.setattr(verified_fit, "_evaluate_quantity", physical)
    first = engine.predict("seebeck", p)
    first[0] = np.nan
    second = engine.predict("seebeck", dict(reversed(list(p.items()))))
    assert np.all(second == p["fermi_energy"])
    assert len(actual) == calls
    assert engine.evaluations == calls
    # Even an adjacent representable input is a separate physical calculation.
    changed = p | {"fermi_energy": np.nextafter(p["fermi_energy"], 0.0)}
    third = engine.predict("seebeck", changed)
    assert np.all(third == changed["fermi_energy"])
    assert len(actual) == calls + 1


def test_prediction_memo_evicts_after_32_entries(monkeypatch):
    from seeband_core import verified_fit

    request, p = _callback_request()
    engine = verified_fit._Engine(request, DpbModel().describe().fit_mode(request.fit_mode))

    def physical(q, t, parameters, *args, **kwargs):
        return np.full(t.shape, parameters["fermi_energy"])

    monkeypatch.setattr(verified_fit, "_evaluate_quantity", physical)
    for i in range(33):
        engine.predict("seebeck", p | {"fermi_energy": -100.0 - i})
    assert engine.evaluations == 33
    engine.predict("seebeck", p | {"fermi_energy": -100.0})
    assert engine.evaluations == 34
    engine.predict("seebeck", p | {"fermi_energy": -132.0})
    assert engine.evaluations == 34
