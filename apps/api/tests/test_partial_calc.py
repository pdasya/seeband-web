"""Partial forward failures must not discard independent observables."""

import numpy as np
import pytest
from seeband_api.calc import _to_response
from seeband_api.calc_worker import calculate
from seeband_core import math_module
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest, Measurement
from seeband_core.model_scales import default_start


def request() -> CurveRequest:
    mode = registry.get("dpb").describe().fit_mode("dpb_s_rho_rh")
    return CurveRequest(mode.id, default_start(mode), 100, 300, 3, "acPh")


def test_hall_exception_preserves_other_quantities_and_temperatures(monkeypatch):
    original = math_module.dpb_hall_vs_temp_acPh

    def fails_at_200(temperatures, *args, **kwargs):
        if 200 in temperatures:
            raise FloatingPointError("synthetic isolated Hall failure")
        return original(temperatures, *args, **kwargs)

    healthy = _to_response(calculate("dpb", request(), {}, 50))
    monkeypatch.setattr(math_module, "dpb_hall_vs_temp_acPh", fails_at_200)
    answer = _to_response(calculate("dpb", request(), {}, 50))
    assert answer.curves["seebeck_v_per_k"] == healthy.curves["seebeck_v_per_k"]
    assert answer.curves["resistivity_ohm_m"] == healthy.curves["resistivity_ohm_m"]
    assert answer.curves["hall_m3_per_c"] == [
        healthy.curves["hall_m3_per_c"][0],
        None,
        healthy.curves["hall_m3_per_c"][2],
    ]
    assert [issue.model_dump() for issue in answer.issues] == [
        {
            "scope": "curve",
            "quantity": "hall_m3_per_c",
            "temperature_k": [200.0],
            "code": "calculation_failed",
        }
    ]


def test_zero_observation_only_invalidates_its_rmse():
    measurements = {
        "resistivity": Measurement(np.array([200.0]), np.array([0.0])),
        "seebeck": Measurement(np.array([200.0]), np.array([0.0])),
    }
    answer = _to_response(calculate("dpb", request(), measurements, 50))
    assert answer.rmse["resistivity"].value is None
    assert answer.rmse["seebeck"].value is not None
    assert [issue.model_dump() for issue in answer.issues] == [
        {
            "scope": "rmse",
            "quantity": "resistivity",
            "temperature_k": [200.0],
            "code": "zero_measured_value",
        }
    ]


@pytest.mark.parametrize("failure", ["nonfinite", "throw"])
def test_rmse_failure_is_separate_from_curves(monkeypatch, failure):
    from seeband_core import verified_fit

    original = verified_fit.evaluate

    def fail_only_measured_hall(*args, **kwargs):
        if kwargs.get("quantities") == ("hall",):
            if failure == "throw":
                raise FloatingPointError("synthetic RMSE failure")
            return {"hall": np.full_like(args[3], np.nan)}
        return original(*args, **kwargs)

    healthy = _to_response(calculate("dpb", request(), {}, 50))
    monkeypatch.setattr(verified_fit, "evaluate", fail_only_measured_hall)
    measurements = {
        "hall": Measurement(np.array([150.0, 250.0]), np.array([1e-9, 1e-9])),
        "seebeck": Measurement(np.array([200.0]), np.array([0.0])),
    }
    answer = _to_response(calculate("dpb", request(), measurements, 50))
    assert answer.curves == healthy.curves
    assert answer.rmse["hall"].value is None
    assert answer.rmse["seebeck"].value is not None
    assert [issue.model_dump() for issue in answer.issues] == [
        {
            "scope": "rmse",
            "quantity": "hall",
            "temperature_k": [150.0, 250.0],
            "code": "calculation_failed" if failure == "throw" else "non_finite_result",
        }
    ]


def test_nonfinite_hall_reports_only_affected_temperature(monkeypatch):
    from dataclasses import replace

    model = registry.get("dpb")
    original = model.calculate

    def nonfinite_at_200(req):
        result = original(req)
        curves = dict(result.curves)
        curves["hall_m3_per_c"] = curves["hall_m3_per_c"].copy()
        curves["hall_m3_per_c"][result.temperature_k == 200] = np.inf
        return replace(result, curves=curves)

    monkeypatch.setattr(model, "calculate", nonfinite_at_200)
    answer = _to_response(calculate("dpb", request(), {}, 50))
    assert answer.curves["hall_m3_per_c"][1] is None
    assert all(v is not None for v in answer.curves["seebeck_v_per_k"])
    assert [issue.model_dump() for issue in answer.issues] == [
        {
            "scope": "curve",
            "quantity": "hall_m3_per_c",
            "temperature_k": [200.0],
            "code": "non_finite_result",
        }
    ]


def test_derived_curve_exception_preserves_other_temperatures(monkeypatch):
    from dataclasses import replace

    from seeband_core import band_models

    original = band_models._CORE.dpb_thermCond_calc

    def fails_at_200(tmin, tmax, points, *args):
        if 200 in np.linspace(tmin, tmax, points):
            raise OverflowError("synthetic thermal failure")
        return original(tmin, tmax, points, *args)

    monkeypatch.setattr(band_models._CORE, "dpb_thermCond_calc", fails_at_200)
    answer = _to_response(calculate("dpb", replace(request(), kind="thermal_conductivity"), {}, 50))
    values = answer.curves["thermal_conductivity_w_per_m_k"]
    assert values[0] is not None and values[1] is None and values[2] is not None
    assert answer.issues[0].quantity == "thermal_conductivity_w_per_m_k"
    assert answer.issues[0].temperature_k == [200.0]


def test_natural_low_temperature_gaps_have_explicit_issues():
    from dataclasses import replace

    req = request()
    req = replace(
        req,
        parameters=req.parameters
        | {"m_eff": 1.2, "band_gap": 3000.0, "fermi_energy": 1500.0, "m1": 1.0},
        min_temperature_k=2,
        max_temperature_k=300,
        points=50,
    )
    answer = _to_response(calculate("dpb", req, {}, 50))
    for quantity in ("resistivity_ohm_m", "hall_m3_per_c"):
        assert answer.curves[quantity][0] is None
        assert any(
            issue.quantity == quantity and issue.temperature_k == [2.0] for issue in answer.issues
        )


def test_healthy_path_calculates_curves_once(monkeypatch):
    model = registry.get("dpb")
    original = model.calculate
    calls = []

    def count(req):
        calls.append(req)
        return original(req)

    monkeypatch.setattr(model, "calculate", count)
    req = request()
    answer = _to_response(calculate("dpb", req, {}, 50))
    assert calls == [req]
    assert answer.issues == []


def test_chemical_potential_failure_only_at_comparison_temperature(monkeypatch):
    from seeband_core import verified_fit
    from seeband_core.math_module import NoFiniteChemicalPotentialError

    original = verified_fit.evaluate

    def no_root_at_250(*args, **kwargs):
        if kwargs.get("quantities") == ("hall",) and 250 in args[3]:
            raise NoFiniteChemicalPotentialError(
                250.0,
                "synthetic comparison-only domain failure",
                code="chemical_potential_zero_mass",
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(verified_fit, "evaluate", no_root_at_250)
    measurements = {"hall": Measurement(np.array([150.0, 250.0]), np.array([1e-9, 1e-9]))}
    answer = _to_response(calculate("dpb", request(), measurements, 50))
    assert all(v is not None for v in answer.curves["hall_m3_per_c"])
    assert answer.rmse["hall"].value is None
    assert [issue.model_dump() for issue in answer.issues] == [
        {
            "scope": "rmse",
            "quantity": "hall",
            "temperature_k": [250.0],
            "code": "chemical_potential_zero_mass",
        }
    ]


def test_temperature_local_root_failure_retains_other_curve_points(monkeypatch):
    from seeband_core.math_module import ChemicalPotentialError

    model = registry.get("dpb")
    original = model.calculate

    def no_root_at_200(req):
        if 200 in np.linspace(req.min_temperature_k, req.max_temperature_k, req.points):
            raise ChemicalPotentialError(200.0, "synthetic local solver failure")
        return original(req)

    monkeypatch.setattr(model, "calculate", no_root_at_200)
    answer = _to_response(calculate("dpb", request(), {}, 50))
    # Independent measured kernels may recover all observables at this temperature.
    assert all(v is not None for values in answer.curves.values() for v in values)


def test_failed_calculation_preserves_code_across_process_transport():
    import pickle

    from seeband_api.calc_worker import CalculationFailed

    failure = pickle.loads(
        pickle.dumps(
            CalculationFailed("NoFiniteChemicalPotentialError", "chemical_potential_zero_mass")
        )
    )
    assert str(failure) == "NoFiniteChemicalPotentialError"
    assert failure.detail_code == "chemical_potential_zero_mass"


def test_custom_model_rmse_retains_shared_grid_fast_path():
    from seeband_core.fit_quality import curve_rmse
    from seeband_core.model_interface import CurveResult
    from seeband_core.partial_calculation import partial_rmse

    class CustomModel:
        def __init__(self):
            self.calls = 0

        def calculate(self, req):
            self.calls += 1
            temperatures = np.linspace(req.min_temperature_k, req.max_temperature_k, req.points)
            return CurveResult(
                temperatures,
                {
                    "seebeck_v_per_k": temperatures**2 * 1e-9,
                    "resistivity_ohm_m": temperatures**2 * 1e-9,
                },
            )

    measurements = {
        "seebeck": Measurement(np.array([150.0, 250.0]), np.array([1e-4, 1e-4])),
        "resistivity": Measurement(np.array([350.0, 450.0]), np.array([1e-4, 1e-4])),
    }
    model = CustomModel()
    req = request()
    expected = curve_rmse(model, req.fit_mode, req.parameters, measurements, "acPh", points=2)
    model.calls = 0
    actual, issues = partial_rmse(model, req, measurements, 2)
    assert actual == expected
    assert issues == ()
    assert model.calls == 1


@pytest.mark.parametrize("scattering", ["acPh", "dis"])
def test_seebeck_failure_preserves_public_dilute_hall_and_resistivity(monkeypatch, scattering):
    from dataclasses import replace

    req = request()
    req = replace(
        req,
        scattering=scattering,
        parameters=req.parameters
        | {
            "m_eff": 1.0,
            "band_gap": 3000.0,
            "fermi_energy": 1500.0,
            "m1": 1.0,
            "B": 1.0,
            "G": 1.0,
            "C": 0.0,
            "D": 0.0,
        },
        min_temperature_k=2,
        max_temperature_k=4,
        points=2,
    )
    healthy = _to_response(calculate("dpb", req, {}, 50))
    name = "dpb_see_vs_temp_single_scatter"
    original = getattr(math_module, name)

    def fail_at_2(temperatures, *args, **kwargs):
        if 2 in temperatures:
            raise FloatingPointError("synthetic Seebeck failure")
        return original(temperatures, *args, **kwargs)

    monkeypatch.setattr(math_module, name, fail_at_2)
    partial = _to_response(calculate("dpb", req, {}, 50))
    assert healthy.curves["hall_m3_per_c"] == [0.0, 0.0]
    assert partial.curves["hall_m3_per_c"] == healthy.curves["hall_m3_per_c"]
    assert partial.curves["resistivity_ohm_m"] == healthy.curves["resistivity_ohm_m"]
    assert partial.curves["seebeck_v_per_k"][0] is None


def test_explicit_bands_reach_the_rmse():
    from seeband_core.fit_quality import curve_rmse
    from seeband_core.model_descriptions import explicit_dpb_description
    from seeband_core.model_interface import ExplicitBands

    mode = explicit_dpb_description().fit_mode("dpb_s_rho")
    bands = ExplicitBands("vb_cb", 2e24)
    explicit = CurveRequest(mode.id, default_start(mode), 100, 500, 5, "acPh", explicit_bands=bands)
    data = {
        "seebeck": Measurement(np.array([200.0, 300.0]), np.array([1e-4, 1.2e-4])),
        "resistivity": Measurement(np.array([200.0, 300.0]), np.array([1e-5, 1.1e-5])),
    }
    answer = calculate("dpb", explicit, data, 50)
    expected = curve_rmse(
        registry.get("dpb"),
        mode.id,
        explicit.parameters,
        data,
        "acPh",
        explicit.band_1_degeneracy,
        explicit.band_2_degeneracy,
        50,
        explicit_bands=bands,
    )
    assert answer.rmse == expected
    assert all(value.value is not None for value in answer.rmse.values())


def test_a_single_scattering_request_needs_no_mixed_ratios():
    mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")
    parameters = {k: v for k, v in default_start(mode).items() if k not in ("C", "D")}
    answer = calculate("dpb", CurveRequest(mode.id, parameters, 100, 300, 3, "acPh"), {}, 50)
    assert np.isfinite(answer.curve.curves["seebeck_v_per_k"]).all()


@pytest.mark.parametrize(
    "kind,refused", [("seebeck", False), ("chemical_potential", False), ("measured", True)]
)
def test_a_negative_hall_mass_is_refused_only_where_it_enters(kind, refused):
    from dataclasses import replace

    from seeband_api.calc_worker import CalculationFailed

    negative = replace(request(), parameters=request().parameters | {"m1": -0.5}, kind=kind)
    if refused:
        with pytest.raises(CalculationFailed):
            calculate("dpb", negative, {}, 50)
    else:
        answer = calculate("dpb", negative, {}, 50)
        assert all(np.isfinite(v).all() for v in answer.curve.curves.values())


def test_invalid_measurements_refuse_the_request_rather_than_its_rmse():
    from seeband_api.calc_worker import CalculationFailed

    data = {"seebeck": Measurement(np.array([0.0, 200.0]), np.array([1e-4, 1e-4]))}
    with pytest.raises(CalculationFailed):
        calculate("dpb", request(), data, 50)
