"""P18 synthetic fits exercise the same public curves and stages as a researcher's fit."""

from dataclasses import replace

import numpy as np
import pytest
from seeband_core.fit_quality import CURVE_NAMES
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


@pytest.mark.parametrize(
    "configuration,density", [("cb_cb", 2e25), ("vb_vb", -2e25), ("vb_cb", 2e25)]
)
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
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
