import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import band_models, fit_module, math_module
from seeband_core.fit_quality import Rmse, curve_rmse, rmse
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    Bounds,
    CurveRequest,
    FitRequest,
    FitStopped,
    IterationUpdate,
    Measurement,
)
from seeband_core.model_scales import default_start

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
DPB_TRUE = {"m_eff": 1.2, "band_gap": 900.0, "fermi_energy": -120.0}
# Temperatures that lie between the points of the grid curve_rmse reads from.
TEMPERATURE_K = np.array([103.7, 151.3, 222.9, 307.1, 411.3, 523.9, 641.7, 788.1])


def synthetic_seebeck() -> Measurement:
    """Synthetic data, calculated at the measured temperatures directly from the model."""
    values = math_module.dpb_see_vs_temp(
        TEMPERATURE_K, DPB_TRUE["m_eff"], DPB_TRUE["band_gap"], DPB_TRUE["fermi_energy"], 1.0
    )
    return Measurement(TEMPERATURE_K, values)


def test_seebeck_rmse_is_in_microvolts() -> None:
    result = rmse("seebeck", np.array([1e-6, 3e-6]), np.array([0.0, 0.0]))
    assert result.unit == "uV/K"
    assert result.value == pytest.approx(np.sqrt(5.0))


@pytest.mark.parametrize("quantity", ["resistivity", "hall"])
def test_other_rmse_is_a_percent_of_the_data(quantity: Any) -> None:
    result = rmse(quantity, np.array([1.1, 1.8]), np.array([1.0, 2.0]))
    assert result == Rmse(pytest.approx(10.0), "%")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("model_values", "measured"),
    [(np.array([]), np.array([])), (np.ones(2), np.ones(3))],
)
def test_rmse_needs_matching_values(model_values: np.ndarray, measured: np.ndarray) -> None:
    with pytest.raises(ValueError, match="same number"):
        rmse("seebeck", model_values, measured)


@pytest.mark.filterwarnings("ignore")
def test_curve_rmse_works_for_manual_parameters_between_grid_points() -> None:
    model = registry.get("dpb")
    data = synthetic_seebeck()
    exact = curve_rmse(model, CurveRequest("dpb_s", DPB_TRUE, 0, 0, 0), "seebeck", data)
    assert exact.unit == "uV/K"
    assert exact.value < 0.05
    wrong = DPB_TRUE | {"fermi_energy": -300.0}
    assert curve_rmse(model, CurveRequest("dpb_s", wrong, 0, 0, 0), "seebeck", data).value > 1


@pytest.mark.filterwarnings("ignore")
def test_curve_rmse_reads_the_named_quantity() -> None:
    model = registry.get("spb")
    fit_mode = model.describe().fit_mode("spb_s_rho")
    values = default_start(fit_mode)
    request = CurveRequest("spb_s_rho", values, 100, 700, 200, "acPh")
    curve = model.calculate(request)
    data = Measurement(curve.temperature_k, curve.curves["resistivity_ohm_m"])
    assert curve_rmse(model, request, "resistivity", data).value < 1e-6
    assert curve_rmse(model, request, "resistivity", data).unit == "%"


@pytest.mark.filterwarnings("ignore")
def test_a_fit_recovers_known_parameters_with_small_errors() -> None:
    model = registry.get("dpb")
    generator = np.random.default_rng(11)
    data = synthetic_seebeck()
    noisy = Measurement(
        data.temperature_k, data.values + generator.normal(0, 1e-6, data.values.size)
    )
    start = {"m_eff": 1.0, "band_gap": 800.0, "fermi_energy": -100.0}
    result = model.fit(FitRequest("dpb_s", {"seebeck": noisy}, start))
    assert result.status == "converged"
    assert result.at_bounds == ()
    assert set(result.parameter_errors) == set(DPB_TRUE)
    for name, value in DPB_TRUE.items():
        assert result.parameter_errors[name] > 0
        assert abs(result.parameters[name] - value) < 5 * result.parameter_errors[name]


class StagedCore:
    """Stands in for the core: sets the solver results of each stage, and returns given values."""

    def __init__(self, stages: dict[str, tuple[list[float], list[float]]], returned: Any) -> None:
        self.stages = stages
        self.returned = returned

    def __getattr__(self, name: str) -> Any:
        def run(*args: Any, progress: fit_module.FitProgress, **kwargs: Any) -> Any:
            for stage, (values, variances) in self.stages.items():
                progress.stage_fits[stage] = (np.array(values), np.diag(variances))
            return self.returned

        return run


def run_staged(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    fit_mode_id: str,
    scattering: str | None,
    stages: dict[str, tuple[list[float], list[float]]],
    returned: list[float],
    **request: Any,
) -> Any:
    monkeypatch.setattr(band_models, "_CORE", StagedCore(stages, returned))
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    data = {quantity: synthetic_seebeck() for quantity in fit_mode.quantities}
    return model.fit(
        FitRequest(fit_mode_id, data, default_start(fit_mode), scattering=scattering, **request)
    )


@pytest.mark.parametrize(
    ("model_id", "fit_mode_id", "scattering", "stages", "ratio", "expected"),
    [
        ("spb", "spb_s", None, {"see": ([1.0], [4.0])}, 1.0, {"fermi_energy": 2.0}),
        (
            "spb",
            "spb_s_rho",
            "acPh",
            {"see": ([1.0], [4.0]), "res": ([1.0], [9.0])},
            1.0,
            {"fermi_energy": 2.0, "A": 3.0},
        ),
        (
            "spb",
            "spb_s_rho",
            "dis",
            {"see": ([1.0], [4.0]), "res": ([1.0], [9.0])},
            1.0,
            {"fermi_energy": 2.0, "F": 3.0},
        ),
        (
            "spb",
            "spb_s_rho",
            "acPhDis",
            {"see": ([1.0], [4.0]), "res": ([1.0, 1.0], [9.0, 90000.0])},
            1.0,
            {"fermi_energy": 2.0, "A": 3.0, "C": 1.0},
        ),
        (
            "dpb",
            "dpb_s",
            None,
            {"see": ([1.0, 1.0, 1.0], [4.0, 9.0, 16.0])},
            2.0,
            {"m_eff": 2.0, "band_gap": 3.0, "fermi_energy": 4.0},
        ),
        (
            "dpb",
            "dpb_s_rho",
            "acPh",
            {"see": ([1.0, 1.0, 1.0], [4.0, 9.0, 16.0]), "res": ([1.0, 1.0], [25.0, 36.0])},
            2.0,
            {"m_eff": 4.0, "band_gap": 3.0, "fermi_energy": 4.0, "A": 5.0, "B": 6.0},
        ),
        (
            "dpb",
            "dpb_s_rho",
            "dis",
            {"see": ([1.0, 1.0, 1.0], [4.0, 9.0, 16.0]), "res": ([1.0, 1.0], [25.0, 36.0])},
            1.0,
            {"m_eff": 2.0, "band_gap": 3.0, "fermi_energy": 4.0, "F": 5.0, "G": 6.0},
        ),
        (
            "dpb",
            "dpb_s_rho",
            "acPhDis",
            {
                "see": ([1.0, 1.0, 1.0], [4.0, 9.0, 16.0]),
                "res": ([1.0, 1.0, 1.0, 1.0], [25.0, 36.0, 90000.0, 360000.0]),
            },
            1.0,
            {
                "m_eff": 2.0,
                "band_gap": 3.0,
                "fermi_energy": 4.0,
                "A": 5.0,
                "B": 6.0,
                "C": 1.0,
                "D": 2.0,
            },
        ),
    ],
)
def test_standard_errors_land_on_the_right_names_and_scales(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    fit_mode_id: str,
    scattering: str | None,
    stages: dict[str, tuple[list[float], list[float]]],
    ratio: float,
    expected: dict[str, float],
) -> None:
    fit_mode = registry.get(model_id).describe().fit_mode(fit_mode_id)
    names = {
        "spb_s": 1,
        "spb_s_rho": 4,
        "dpb_s": 3,
        "dpb_s_rho": 9,
    }[fit_mode_id]
    keywords = {"band_2_degeneracy": ratio} if fit_mode.degeneracy else {}
    result = run_staged(
        monkeypatch, model_id, fit_mode_id, scattering, stages, [1.0] * names, **keywords
    )
    assert result.parameter_errors == pytest.approx(expected)


def test_the_hall_stage_error_is_carried_over_to_the_mass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stages = {"hall": ([8.0], [9.0])}
    result = run_staged(
        monkeypatch, "dpb", "dpb_s_rho_rh", "acPh", stages, [1.0] * 10, band_2_degeneracy=1.0
    )
    # m = E^(2/3), so dm = (2/3) * 8^(-1/3) * 3 = 1.
    assert result.parameter_errors == pytest.approx({"m1": 1.0})


def test_spb_hall_keeps_c_undivided_as_its_result_does(monkeypatch: pytest.MonkeyPatch) -> None:
    stages = {"res": ([1.0, 1.0], [9.0, 16.0])}
    result = run_staged(monkeypatch, "spb", "spb_s_rho_rh", "acPhDis", stages, [1.0] * 5)
    assert result.parameter_errors == pytest.approx({"A": 3.0, "C": 4.0})


@pytest.mark.parametrize("variance", [np.inf, np.nan, -1.0])
def test_errors_that_are_not_finite_are_left_out(
    monkeypatch: pytest.MonkeyPatch, variance: float
) -> None:
    stages = {"see": ([1.0, 1.0, 1.0], [variance, 9.0, 16.0])}
    result = run_staged(monkeypatch, "dpb", "dpb_s", None, stages, [1.0, 1.0, 1.0])
    assert result.parameter_errors == pytest.approx({"band_gap": 3.0, "fermi_energy": 4.0})
    assert result.status == "converged"


def test_bound_flags_cover_both_ends_and_only_fitted_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returned = [3.0, -3000.0, 500.0, 40000.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    result = run_staged(monkeypatch, "dpb", "dpb_s_rho", "acPh", {}, returned)
    # m_eff at its upper bound, and the gap at its lower. C, D, F and G do not apply to acPh.
    assert result.at_bounds == ("m_eff", "band_gap")
    fixed = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0])
    assert fixed.at_bounds == ("fermi_energy",)


def test_bound_flags_stop_just_outside_the_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    # The range of E_F is 6000 K, so the tolerance is 0.006 K.
    near = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0 - 0.005])
    far = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0 - 0.007])
    assert near.at_bounds == ("fermi_energy",)
    assert far.at_bounds == ()


def test_bound_flags_use_the_bounds_of_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_staged(
        monkeypatch,
        "spb",
        "spb_s",
        None,
        {},
        [100.0],
        bounds={"fermi_energy": Bounds(100.0, 110.0)},
    )
    assert result.at_bounds == ("fermi_energy",)


def test_bound_flags_divide_m_eff_by_n_in_the_loop_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # The upper bound of m_eff is 3. The loop returns m_eff * N, and its bounds apply before that.
    rest = [500.0, 500.0, 40000.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    inside = run_staged(
        monkeypatch, "dpb", "dpb_s_rho", "acPh", {}, [3.0, *rest], band_2_degeneracy=2.0
    )
    assert inside.at_bounds == ()
    at_bound = run_staged(
        monkeypatch, "dpb", "dpb_s_rho", "acPh", {}, [6.0, *rest], band_2_degeneracy=2.0
    )
    assert at_bound.at_bounds == ("m_eff",)
    # A single-pass fit returns the value it fitted.
    single = run_staged(
        monkeypatch, "dpb", "dpb_s", None, {}, [3.0, 500.0, 500.0], band_2_degeneracy=2.0
    )
    assert single.at_bounds == ("m_eff",)


def test_a_failed_fit_has_no_errors_or_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    class Failing:
        def __getattr__(self, name: str) -> Any:
            def fail(*args: Any, **kwargs: Any) -> Any:
                raise ValueError("Residuals are not finite")

            return fail

    monkeypatch.setattr(band_models, "_CORE", Failing())
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    result = model.fit(
        FitRequest("dpb_s", {"seebeck": synthetic_seebeck()}, default_start(fit_mode))
    )
    assert (result.status, result.parameter_errors, result.at_bounds) == ("failed", {}, ())


def recorded_seebeck(call: dict[str, Any], count: int) -> dict[Any, Measurement]:
    names = ("seebeck", "resistivity", "hall")
    return {
        names[index]: Measurement(
            np.array(call["args"][2 * index]), np.array(call["args"][2 * index + 1])
        )
        for index in range(count)
    }


@pytest.mark.filterwarnings("ignore")
def test_the_recorded_case_of_e_f_at_its_bound_is_flagged() -> None:
    # golden-results.md: SPB S + rho on 01 stops E_F at its lower bound of -3000 K.
    document = json.loads((GOLDEN / "01_Fe2VAl09Si01.json").read_text(encoding="utf-8"))
    run = next(
        r for r in document["runs"] if r["mode"] == "spb_s_rho" and r["scattering"] == "acPh"
    )
    model = registry.get("spb")
    fit_mode = model.describe().fit_mode("spb_s_rho")
    result = model.fit(
        FitRequest(
            "spb_s_rho",
            recorded_seebeck(run["calls"][0], 2),
            default_start(fit_mode),
            scattering="acPh",
        )
    )
    assert "fermi_energy" in result.at_bounds


@pytest.mark.filterwarnings("ignore")
def test_a_stopped_fit_keeps_its_errors() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    document = json.loads((GOLDEN / "03_AWI32_SI.json").read_text(encoding="utf-8"))
    call = next(r for r in document["runs"] if r["mode"] == "dpb_s_rho")["calls"][0]

    def stop(update: IterationUpdate) -> None:
        raise FitStopped

    result = model.fit(
        FitRequest(
            "dpb_s_rho", recorded_seebeck(call, 2), default_start(fit_mode), scattering="acPh"
        ),
        stop,
    )
    assert result.status == "stopped"
    assert "A" in result.parameter_errors or "B" in result.parameter_errors
