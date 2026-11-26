"""P18 synthetic fits exercise the same public curves and stages as a researcher's fit."""

from dataclasses import replace

import numpy as np
import pytest
from seeband_core.fit_quality import CURVE_NAMES
from seeband_core.model_catalog import registry
from seeband_core.model_descriptions import explicit_dpb_description, load_desktop_descriptions
from seeband_core.model_interface import (
    Bounds,
    CurveRequest,
    ExplicitBands,
    FitRequest,
    Measurement,
)
from seeband_core.model_scales import default_start


@pytest.mark.parametrize(
    "configuration,density", [("cb_cb", 2e25), ("vb_vb", -2e25), ("vb_cb", 2e25)]
)
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis", "ionized"])
@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"])
def test_explicit_fit_returns_consistent_curves(configuration, density, scattering, mode_id):
    model = registry.get("dpb")
    mode = explicit_dpb_description().fit_mode(mode_id)
    target = default_start(mode) | {"m1": 1.2, "mass_ratio": 1.7, "band_offset_k": 140.0}
    settings = ExplicitBands(configuration, density)
    request = CurveRequest(
        mode_id,
        target,
        180,
        510,
        4,
        scattering,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        explicit_bands=settings,
    )
    synthetic = model.calculate(request)
    data = {
        q: Measurement(synthetic.temperature_k, synthetic.curves[CURVE_NAMES[q]])
        for q in mode.quantities
    }
    active = {p.name for p in mode.parameters_for(scattering) if p.role == "fitted"}
    # The ratio moves in all modes. In Hall mode both single-valley masses change.
    free = {"mass_ratio"}
    if mode_id == "dpb_s_rho":
        free.add("F" if scattering == "dis" else "A")
    elif mode_id == "dpb_s_rho_rh":
        free.add("m1")
    start = target | {name: target[name] * (0.99 if name == "m1" else 1.04) for name in free}
    result = model.fit(
        FitRequest(
            mode.id,
            data,
            start,
            {name: Bounds(target[name] * 0.8, target[name] * 1.2) for name in free},
            scattering,
            2,
            3,
            held=frozenset(active - free),
            explicit_bands=settings,
        )
    )
    assert result.status == "converged", (result.message, result.diagnostics)
    assert result.diagnostics and result.diagnostics.stage_consistent
    retained = model.calculate(replace(request, parameters=result.parameters))
    for q, measured in data.items():
        np.testing.assert_allclose(retained.curves[CURVE_NAMES[q]], measured.values, rtol=2e-6)
    for name in free:
        assert result.parameters[name] == pytest.approx(target[name], rel=2e-5)


def test_relative_weight_and_band_shape_change_together_in_s_rho_fit():
    """A rho-only weight update used to trap the mixed pair at a poorer S and rho."""
    model = registry.get("dpb")
    mode = explicit_dpb_description().fit_mode("dpb_s_rho")
    settings = ExplicitBands("vb_cb", 2e25)
    target = default_start(mode) | {"m1": 1.2, "mass_ratio": 1.7, "band_offset_k": 140.0}
    request = CurveRequest(
        mode.id,
        target,
        180,
        510,
        7,
        "acPh",
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        explicit_bands=settings,
    )
    curve = model.calculate(request)
    data = {
        q: Measurement(curve.temperature_k, curve.curves[CURVE_NAMES[q]]) for q in mode.quantities
    }
    free = ["mass_ratio", "band_offset_k", "A", "B"]
    bounds = {n: Bounds(target[n] * 0.75, target[n] * 1.25) for n in free}
    start = target | {n: target[n] * (0.98 if i % 2 == 0 else 1.03) for i, n in enumerate(free)}
    result = model.fit(
        FitRequest(mode.id, data, start, bounds, "acPh", 2, 3, explicit_bands=settings)
    )
    assert result.status == "converged"
    retained = model.calculate(replace(request, parameters=result.parameters))
    for q in mode.quantities:
        np.testing.assert_allclose(retained.curves[CURVE_NAMES[q]], data[q].values, rtol=1e-6)


def test_free_zero_resistivity_amplitude_is_profiled_before_first_prediction():
    model = registry.get("dpb")
    mode = explicit_dpb_description().fit_mode("dpb_s_rho")
    settings = ExplicitBands("cb_cb", 2e25)
    target = default_start(mode)
    request = CurveRequest(mode.id, target, 200, 450, 3, "acPh", explicit_bands=settings)
    curve = model.calculate(request)
    data = {
        q: Measurement(curve.temperature_k, curve.curves[CURVE_NAMES[q]]) for q in mode.quantities
    }
    result = model.fit(
        FitRequest(
            mode.id,
            data,
            target | {"A": 0.0},
            {"A": Bounds(0, target["A"] * 2)},
            "acPh",
            held=frozenset({"B", "mass_ratio", "band_offset_k"}),
            explicit_bands=settings,
        )
    )
    assert result.status == "converged"
    assert result.parameters["A"] == pytest.approx(target["A"], rel=1e-10)


@pytest.mark.parametrize(
    "configuration,carrier,offset,ef,signs",
    [
        ("cb_cb", "n", 140, 215, (1, 1)),
        ("vb_vb", "p", 140, -75, (-1, -1)),
        ("vb_cb", "n", -140, -10, (-1, 1)),
        ("vb_cb", "p", -140, -130, (-1, 1)),
    ],
)
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis", "ionized"])
@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"])
def test_fermi_energy_fit_and_independent_pocket_population(
    configuration, carrier, offset, ef, signs, scattering, mode_id
):
    """An energy trial determines carrier excess, including EF<0 on an n branch."""
    from seeband_core import math_module as mm

    model = registry.get("dpb")
    mode = explicit_dpb_description(True).fit_mode(mode_id)
    point = default_start(mode) | dict(
        m1=1.2, mass_ratio=1.7, band_offset_k=offset, fermi_energy=ef
    )
    settings = ExplicitBands(configuration, carrier_type=carrier)
    req = CurveRequest(
        mode_id,
        point,
        160,
        550,
        4,
        scattering,
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        explicit_bands=settings,
    )
    curve = model.calculate(req)
    # Count occupied k-space states per volume (spin included), using the kernel's constants.
    density = 0.0
    for sign, edge, mass, valleys in zip(signs, (0, offset), (1.2, 1.2 * 1.7), (2, 3), strict=True):
        fermi_k = np.sqrt(2 * mass * mm.me * mm.kB * max(0, sign * (ef - edge))) / mm.hbar
        density += sign * valleys * fermi_k**3 / (3 * np.pi**2)
    assert np.sign(density) == (1 if carrier == "n" else -1)
    density_point = {name: value for name, value in point.items() if name != "fermi_energy"}
    expected = model.calculate(
        replace(req, parameters=density_point, explicit_bands=ExplicitBands(configuration, density))
    )
    for key, values in expected.curves.items():
        np.testing.assert_allclose(curve.curves[key], values, rtol=1e-10, atol=0)

    measured = {
        q: Measurement(curve.temperature_k, curve.curves[CURVE_NAMES[q]]) for q in mode.quantities
    }
    held = frozenset(
        p.name
        for p in mode.parameters_for(scattering)
        if p.role == "fitted" and p.name != "fermi_energy"
    )
    result = model.fit(
        FitRequest(
            mode_id,
            measured,
            point | {"fermi_energy": ef + 3},
            {"fermi_energy": Bounds(ef - 8, ef + 8)},
            scattering,
            2,
            3,
            held=held,
            explicit_bands=settings,
        )
    )
    assert result.status == "converged", result.message
    assert result.parameters["fermi_energy"] == pytest.approx(ef, abs=2e-5)


@pytest.mark.parametrize("carrier,target", [("p", -100), ("n", 700), (None, -100), (None, 700)])
def test_fit_from_intrinsic_start_can_reach_selected_carrier_branch(carrier, target):
    model = registry.get("dpb")
    mode = explicit_dpb_description(True).fit_mode("dpb_s")
    p = default_start(mode) | dict(m1=1, mass_ratio=1.3, band_offset_k=600, fermi_energy=target)
    cfg = ExplicitBands("vb_cb", carrier_type=carrier)
    curve = model.calculate(CurveRequest(mode.id, p, 200, 500, 6, "acPh", explicit_bands=cfg))
    intrinsic = model.calculate(
        CurveRequest(mode.id, p | {"fermi_energy": 100}, 200, 500, 6, "acPh", explicit_bands=cfg)
    )
    assert "fermi_energy_in_gap" in intrinsic.known_issues
    assert "fermi_energy_in_gap" not in curve.known_issues
    measured = {"seebeck": Measurement(curve.temperature_k, curve.curves[CURVE_NAMES["seebeck"]])}
    result = model.fit(
        FitRequest(
            mode.id,
            measured,
            p | {"fermi_energy": 100},
            {"fermi_energy": Bounds(-200, 800)},
            "acPh",
            held=frozenset({"mass_ratio", "band_offset_k"}),
            explicit_bands=cfg,
        )
    )
    assert result.parameters["fermi_energy"] == pytest.approx(target, abs=2e-5)


def test_joint_hall_fit_can_start_at_compensated_overlap():
    model = registry.get("dpb")
    mode = explicit_dpb_description(True).fit_mode("dpb_s_rho_rh")
    p = default_start(mode) | dict(m1=1.2, mass_ratio=1, band_offset_k=-140, fermi_energy=-65)
    cfg = ExplicitBands("vb_cb", carrier_type="n")
    curve = model.calculate(CurveRequest(mode.id, p, 200, 500, 6, "acPh", explicit_bands=cfg))
    measured = {
        q: Measurement(curve.temperature_k, curve.curves[CURVE_NAMES[q]]) for q in mode.quantities
    }
    free = {"fermi_energy", "m1"}
    held = frozenset(
        k.name for k in mode.parameters_for("acPh") if k.role == "fitted" and k.name not in free
    )
    fit = model.fit(
        FitRequest(
            mode.id,
            measured,
            p | {"fermi_energy": -70, "m1": 1},
            {"fermi_energy": Bounds(-90, -40), "m1": Bounds(0.8, 1.5)},
            "acPh",
            held=held,
            explicit_bands=cfg,
        )
    )
    assert fit.status == "converged", fit.message
    assert fit.parameters["fermi_energy"] == pytest.approx(-65, abs=2e-5)
    assert fit.parameters["m1"] == pytest.approx(1.2, rel=2e-5)


def test_the_hall_mass_comes_from_the_hall_mode_whatever_the_order():
    desktop = load_desktop_descriptions()["dpb"]
    hall = next(p for p in desktop.fit_mode("dpb_s_rho_rh").parameters if p.name == "m1")
    for mode in explicit_dpb_description().fit_modes:
        mass = next(p for p in mode.parameters if p.name == "m1")
        assert mass.value_range == hall.value_range, mode.id


@pytest.mark.parametrize("uses_fermi_energy", [False, True])
def test_explicit_controls_start_where_curves_exist(uses_fermi_energy):
    """No explicit curve has a zero amplitude or mass ratio, so no slider offers one."""
    for mode in explicit_dpb_description(uses_fermi_energy).fit_modes:
        for p in mode.parameters:
            if p.name in ("A", "F"):
                assert p.value_range.minimum == p.value_range.step > 0, (mode.id, p.name)
                # The fit keeps 0, where it profiles the amplitude before its first prediction.
                assert p.fit_bounds is not None and p.fit_bounds.lower == 0
            if p.name == "mass_ratio":
                assert p.value_range.minimum > 0
                assert p.fit_bounds is not None and p.fit_bounds.lower > 0


@pytest.mark.parametrize("uses_fermi_energy", [False, True])
def test_a_failing_joint_start_search_resumes_from_the_valid_start(monkeypatch, uses_fermi_energy):
    """The coupled start is optional: a solver failure inside it must not fail the whole fit."""
    from seeband_core import math_module, verified_fit

    model = registry.get("dpb")
    mode = explicit_dpb_description(uses_fermi_energy).fit_mode("dpb_s_rho_rh")
    p = default_start(mode) | dict(m1=1.2, mass_ratio=1.7, band_offset_k=140.0)
    cfg = (
        ExplicitBands("vb_cb", carrier_type="p")
        if uses_fermi_energy
        else ExplicitBands("vb_cb", -2e25)
    )
    if uses_fermi_energy:
        p["fermi_energy"] = -75.0
    curve = model.calculate(CurveRequest(mode.id, p, 200, 500, 6, "acPh", explicit_bands=cfg))
    measured = {
        q: Measurement(curve.temperature_k, curve.curves[CURVE_NAMES[q]]) for q in mode.quantities
    }
    free = {"m1", "B"}
    held = frozenset(
        k.name for k in mode.parameters_for("acPh") if k.role == "fitted" and k.name not in free
    )
    request = FitRequest(
        mode.id,
        measured,
        p | {"m1": 1.1, "B": p["B"] * 1.03},
        {"m1": Bounds(0.8, 1.5), "B": Bounds(p["B"] * 0.9, p["B"] * 1.1)},
        "acPh",
        held=held,
        explicit_bands=cfg,
    )
    original = verified_fit.least_squares
    calls = []

    def failing_first(*args, **kwargs):
        calls.append(kwargs.get("max_nfev"))
        if len(calls) == 1:
            raise math_module.ChemicalPotentialError(None, "explicit density bracket failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(verified_fit, "least_squares", failing_first)
    fit = model.fit(request)
    assert calls[0] == 30  # the joint start search, which failed
    assert fit.status == "converged", fit.message
    assert fit.parameters["m1"] == pytest.approx(1.2, rel=2e-5)
