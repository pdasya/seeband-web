"""Explicit ionized weights are empirical inputs, conditional on the selected mechanism."""

from dataclasses import replace

import numpy as np
import pytest
from seeband_core.model_catalog import registry
from seeband_core.model_descriptions import explicit_dpb_description
from seeband_core.model_interface import CurveRequest, ExplicitBands


def test_s_only_ionized_weight_matches_resistivity_mode_weighting():
    model = registry.get("dpb")
    request = CurveRequest(
        "dpb_s",
        dict(m1=1.2, mass_ratio=2, band_offset_k=140),
        180,
        510,
        4,
        "ionized",
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        explicit_bands=ExplicitBands("cb_cb", 2e25),
    )
    default = model.calculate(request).curves["seebeck_v_per_k"]
    explicit = model.calculate(replace(request, parameters=dict(request.parameters) | {"B": 1}))
    np.testing.assert_array_equal(default, explicit.curves["seebeck_v_per_k"])
    weighted = replace(request, parameters=dict(request.parameters) | {"B": 4})
    weighted_s = model.calculate(weighted).curves["seebeck_v_per_k"]
    rho = model.calculate(replace(weighted, fit_mode="dpb_s_rho"))
    np.testing.assert_array_equal(weighted_s, rho.curves["seebeck_v_per_k"])
    assert not np.allclose(default, weighted_s, rtol=1e-5, atol=0)
    for invalid in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="relative weight"):
            model.calculate(
                replace(weighted, parameters=dict(weighted.parameters) | {"B": invalid})
            )


def test_ionized_metadata_has_fixed_s_weight_and_broad_rho_bounds():
    for fermi in (False, True):
        description = explicit_dpb_description(fermi)
        for mode in description.fit_modes:
            active = {p.name: p for p in mode.parameters_for("ionized")}
            weight = active["B"]
            assert weight.value_range.default * weight.fit_scale == 1
            assert weight.scattering == ("ionized",)
            if mode.id == "dpb_s":
                assert weight.role == "fixed"
                assert weight.fit_bounds is None
            else:
                assert weight.role == "fitted" and weight.bounds_editable
                assert weight.fit_bounds.lower <= 1e-4
                assert weight.fit_bounds.upper >= 1e4
            other = {p.name: p for p in mode.parameters_for("acPh")}
            if mode.id == "dpb_s":
                assert "B" not in other
            else:
                assert other["B"].fit_bounds.upper == 1.1


def test_s_only_fit_keeps_nondefault_ionized_weight_fixed():
    from seeband_core.model_interface import Bounds, FitRequest, Measurement

    model = registry.get("dpb")
    settings = ExplicitBands("cb_cb", 2e25)
    target = dict(m1=1.2, mass_ratio=2, band_offset_k=140, B=4)
    curve = model.calculate(
        CurveRequest(
            "dpb_s",
            target,
            180,
            510,
            5,
            "ionized",
            band_1_degeneracy=2,
            band_2_degeneracy=3,
            explicit_bands=settings,
        )
    )
    result = model.fit(
        FitRequest(
            "dpb_s",
            {"seebeck": Measurement(curve.temperature_k, curve.curves["seebeck_v_per_k"])},
            target | {"band_offset_k": 145},
            {"band_offset_k": Bounds(100, 200)},
            "ionized",
            2,
            3,
            held=frozenset({"mass_ratio"}),
            explicit_bands=settings,
        )
    )
    assert result.status == "converged", result.message
    assert result.parameters["B"] == 4
    assert result.parameter_status["B"] == "fixed"
    assert result.parameters["band_offset_k"] == pytest.approx(140, rel=1e-5)


@pytest.mark.parametrize("mode_id", ["dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("initial_weight", [1, 2])
def test_ionized_fit_recovers_mass_squared_benchmark_with_metadata_bounds(mode_id, initial_weight):
    from seeband_core.fit_quality import CURVE_NAMES
    from seeband_core.model_interface import FitRequest, Measurement
    from seeband_core.model_scales import default_start

    model = registry.get("dpb")
    mode = explicit_dpb_description().fit_mode(mode_id)
    specs = {p.name: p for p in mode.parameters_for("ionized")}
    target = default_start(mode) | dict(m1=1.2, mass_ratio=2, band_offset_k=140, B=4)
    settings = ExplicitBands("cb_cb", 2e25)
    request = CurveRequest(
        mode_id,
        target,
        180,
        510,
        7,
        "ionized",
        band_1_degeneracy=2,
        band_2_degeneracy=3,
        explicit_bands=settings,
    )
    synthetic = model.calculate(request)
    data = {
        q: Measurement(synthetic.temperature_k, synthetic.curves[CURVE_NAMES[q]])
        for q in mode.quantities
    }
    fitted = {p.name for p in specs.values() if p.role == "fitted"}
    result = model.fit(
        FitRequest(
            mode_id,
            data,
            target | {"B": initial_weight},
            {"B": specs["B"].fit_bounds},
            "ionized",
            2,
            3,
            held=frozenset(fitted - {"B"}),
            explicit_bands=settings,
        )
    )
    assert result.status == "converged", (result.message, result.diagnostics)
    assert result.parameters["B"] == pytest.approx(4, rel=1e-5)
    assert "B" not in result.at_bounds
