import dataclasses
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
    data = {"seebeck": synthetic_seebeck()}
    exact = curve_rmse(model, "dpb_s", DPB_TRUE, data)["seebeck"]
    assert exact.unit == "uV/K"
    assert exact.value is not None
    assert exact.value < 0.05
    wrong = curve_rmse(model, "dpb_s", DPB_TRUE | {"fermi_energy": -300.0}, data)["seebeck"]
    assert wrong.value is not None
    assert wrong.value > 1


@pytest.mark.filterwarnings("ignore")
def test_curve_rmse_gives_each_quantity_from_one_curve(monkeypatch: pytest.MonkeyPatch) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    values = default_start(fit_mode)
    curve = model.calculate(CurveRequest("dpb_s_rho", values, 100, 700, 200, "acPh"))
    data: dict[Any, Measurement] = {
        "seebeck": Measurement(curve.temperature_k, curve.curves["seebeck_v_per_k"]),
        "resistivity": Measurement(curve.temperature_k, curve.curves["resistivity_ohm_m"]),
    }
    calls = []
    calculate = type(model).calculate

    def counted(self: Any, request: CurveRequest) -> Any:
        calls.append(request)
        return calculate(self, request)

    monkeypatch.setattr(type(model), "calculate", counted)
    result = curve_rmse(model, "dpb_s_rho", values, data, "acPh")
    assert len(calls) == 1
    assert result["seebeck"] == Rmse(pytest.approx(0.0, abs=1e-9), "uV/K")  # type: ignore[arg-type]
    assert result["resistivity"] == Rmse(pytest.approx(0.0, abs=1e-9), "%")  # type: ignore[arg-type]


@pytest.mark.filterwarnings("ignore")
def test_curve_rmse_passes_degeneracy_and_points_on() -> None:
    model = registry.get("dpb")
    curve = model.calculate(
        CurveRequest("dpb_s", DPB_TRUE, 100, 700, 50, band_1_degeneracy=2.0, band_2_degeneracy=3.0)
    )
    data = {"seebeck": Measurement(curve.temperature_k, curve.curves["seebeck_v_per_k"])}
    same = curve_rmse(
        model, "dpb_s", DPB_TRUE, data, band_1_degeneracy=2.0, band_2_degeneracy=3.0, points=50
    )
    assert same["seebeck"].value == pytest.approx(0.0, abs=1e-9)
    other = curve_rmse(model, "dpb_s", DPB_TRUE, data, points=50)["seebeck"].value
    assert other is not None
    assert other > 1


def test_percent_rmse_refuses_a_measured_zero_and_seebeck_does_not() -> None:
    with pytest.raises(ValueError, match="other than 0"):
        rmse("hall", np.array([1.0]), np.array([0.0]))
    assert rmse("seebeck", np.array([1e-6]), np.array([0.0])).value == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_rmse_of_values_that_are_not_finite(bad: float) -> None:
    assert rmse("seebeck", np.array([bad]), np.array([1.0])) == Rmse(None, "uV/K")
    with pytest.raises(ValueError, match="finite measured"):
        rmse("seebeck", np.array([1.0]), np.array([bad]))


def test_curve_rmse_refuses_what_it_cannot_compare() -> None:
    model = registry.get("dpb")
    good = synthetic_seebeck()
    with pytest.raises(ValueError, match="at least one"):
        curve_rmse(model, "dpb_s", DPB_TRUE, {})
    with pytest.raises(ValueError, match="no curve for hall"):
        curve_rmse(model, "dpb_s", DPB_TRUE, {"hall": good})
    with pytest.raises(ValueError, match="above 0 K"):
        curve_rmse(
            model, "dpb_s", DPB_TRUE, {"seebeck": Measurement(np.array([0.0, 1.0]), np.ones(2))}
        )


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
    # C, D, F and G are at their bounds too, but do not apply to acPh, so they are not named.
    returned = [3.0, -3000.0, 500.0, 40000.0, 1.0, 2.0, 0.5, 100000.0, 2.0]
    result = run_staged(monkeypatch, "dpb", "dpb_s_rho", "acPh", {}, returned)
    assert result.at_bounds == ("m_eff", "band_gap")
    fixed = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0])
    assert fixed.at_bounds == ("fermi_energy",)


def test_bound_flags_stop_just_outside_the_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    # The tolerance of a bound of 3000 K is 0.003 K.
    near = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0 - 0.002])
    far = run_staged(monkeypatch, "spb", "spb_s", None, {}, [3000.0 - 0.004])
    assert near.at_bounds == ("fermi_energy",)
    assert far.at_bounds == ()


def test_bound_flags_leave_well_fitted_values_on_wide_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A of about 1e-5 matches the data in D19, on a range of 0 to 1e6, and 2.17 on 1 to 1e7.
    rest = [1.0, 1.0, 1.0, 1.0, 1.0]
    dpb = run_staged(monkeypatch, "dpb", "dpb_s_rho", "acPh", {}, [1.0, 500.0, 500.0, 2e-4, *rest])
    assert "A" not in dpb.at_bounds
    spb = run_staged(monkeypatch, "spb", "spb_s_rho", "acPh", {}, [500.0, 2.17, 1.0, 1.0])
    assert spb.at_bounds == ()


@pytest.mark.parametrize(
    ("bounds", "flagged"),
    [
        (Bounds(-5000.0, float("inf")), False),
        (Bounds(float("-inf"), 5000.0), False),
        (Bounds(-1e308, 1e308), False),
        (Bounds(99.9, float("inf")), True),
    ],
)
def test_bound_flags_handle_open_and_huge_ranges(
    monkeypatch: pytest.MonkeyPatch, bounds: Bounds, flagged: bool
) -> None:
    result = run_staged(
        monkeypatch, "spb", "spb_s", None, {}, [99.9], bounds={"fermi_energy": bounds}
    )
    assert bool(result.at_bounds) is flagged


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


def test_bound_flags_follow_the_undivided_c_of_spb_hall(monkeypatch: pytest.MonkeyPatch) -> None:
    # D6: this fit returns C still multiplied by 300, and C's upper bound is 1000.
    stages = {"hall": ([1.0], [1.0])}
    inside = run_staged(
        monkeypatch, "spb", "spb_s_rho_rh", "acPhDis", stages, [500.0, 2.0, 1500.0, 1.0, 1.0]
    )
    assert "C" not in inside.at_bounds
    at_bound = run_staged(
        monkeypatch, "spb", "spb_s_rho_rh", "acPhDis", stages, [500.0, 2.0, 300000.0, 1.0, 1.0]
    )
    assert "C" in at_bound.at_bounds


def test_exactly_zero_errors_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    stages = {"see": ([1.0, 1.0, 1.0], [0.0, 9.0, 16.0])}
    result = run_staged(monkeypatch, "dpb", "dpb_s", None, stages, [1.0, 1.0, 1.0])
    assert result.parameter_errors == pytest.approx({"band_gap": 3.0, "fermi_energy": 4.0})


def test_spb_hall_mass_error_handles_a_negative_e(monkeypatch: pytest.MonkeyPatch) -> None:
    stages = {"hall": ([-8.0], [9.0])}
    result = run_staged(monkeypatch, "spb", "spb_s_rho_rh", "acPh", stages, [1.0] * 5)
    assert result.parameter_errors == pytest.approx({"band_mass": 1.0})


DPB_STAGES = {"acPh": 2, "dis": 2, "acPhDis": 4}


def recorded_args(example: str, mode: str, function: str) -> list[Any]:
    document = json.loads((GOLDEN / f"{example}.json").read_text(encoding="utf-8"))
    calls = (call for run in document["runs"] if run["mode"] == mode for call in run["calls"])
    return next(c for c in calls if c["function"] == function and "error" not in c)["args"]


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
@pytest.mark.parametrize("fit_mode_id", ["dpb_s_rho", "dpb_s_rho_rh"])
def test_stages_of_a_real_loop_hold_their_last_run(fit_mode_id: str, scattering: str) -> None:
    model = model_at_limit(fit_mode_id)
    args = recorded_args("03_AWI32_SI", "dpb_s_rho_rh", "dpb_see_res_hall_fit")
    arrays = [np.array(value) for value in args[:6]]
    fit_mode = model.describe().fit_mode(fit_mode_id)
    data: dict[Any, Measurement] = {
        "seebeck": Measurement(arrays[0], arrays[1]),
        "resistivity": Measurement(arrays[2], arrays[3]),
        "hall": Measurement(arrays[4], arrays[5]),
    }
    selected = {quantity: data[quantity] for quantity in fit_mode.quantities}
    captured: list[fit_module.FitProgress] = []
    original = fit_module.FitProgress

    class Capturing(original):  # type: ignore[valid-type, misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            captured.append(self)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fit_module, "FitProgress", Capturing)
        result = model.fit(
            FitRequest(
                fit_mode_id,
                selected,
                default_start(fit_mode),
                scattering=scattering,
                band_2_degeneracy=2.0,
            )
        )
    assert result.status == "iteration_limit"
    stages = captured[0].stage_fits
    # The result comes from the last run of each stage: m_eff from the extra Seebeck run.
    assert len(stages["see"][0]) == 3
    assert stages["see"][0][0] * 2.0 == result.parameters["m_eff"]
    assert stages["see"][0][1] == result.parameters["band_gap"]
    assert len(stages["res"][0]) == DPB_STAGES[scattering]
    first = "F" if scattering == "dis" else "A"
    assert stages["res"][0][0] == result.parameters[first]
    if fit_mode_id == "dpb_s_rho_rh":
        assert len(stages["hall"][0]) == 1
        assert stages["hall"][0][0] ** (2 / 3) == pytest.approx(result.parameters["m1"])
    else:
        assert "hall" not in stages


def model_at_limit(fit_mode_id: str) -> band_models.DpbModel:
    model = band_models.DpbModel()
    description = model.describe()
    modes = tuple(
        dataclasses.replace(mode, threshold=1e-300, max_iterations=2)
        if mode.id == fit_mode_id
        else mode
        for mode in description.fit_modes
    )
    model._description = dataclasses.replace(description, fit_modes=modes)
    return model


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("fit_mode_id", "scattering", "lengths"),
    [
        ("spb_s", None, {"see": 1}),
        ("spb_s_rho", "acPh", {"see": 1, "res": 1}),
        ("spb_s_rho", "dis", {"see": 1, "res": 1}),
        ("spb_s_rho", "acPhDis", {"see": 1, "res": 2}),
        ("spb_s_rho_rh", "acPh", {"see": 1, "res": 1, "hall": 1}),
        ("spb_s_rho_rh", "dis", {"see": 1, "res": 1, "hall": 1}),
        ("spb_s_rho_rh", "acPhDis", {"see": 1, "res": 2, "hall": 1}),
    ],
)
def test_stages_of_real_spb_fits_are_labelled(
    fit_mode_id: str, scattering: str | None, lengths: dict[str, int]
) -> None:
    args = recorded_args("03_AWI32_SI", "dpb_s_rho_rh", "dpb_see_res_hall_fit")
    a = [np.array(value) for value in args[:6]]
    progress = fit_module.FitProgress()
    core = fit_module.PB_fit()
    fermi: list[Any] = [[-100], [[-3000], [3000]]]
    res: list[Any] = [[40000, 100, 4000], [[1, 0.001, 1], [1e7, 1000.0, 1e7]]]
    if fit_mode_id == "spb_s":
        core.spb_see_fit(a[0], a[1], -1.0, *fermi, progress=progress)
    elif fit_mode_id == "spb_s_rho":
        core.spb_see_res_fit(*a[:4], -1.0, *fermi, *res, scatter_type=scattering, progress=progress)
    else:
        core.spb_see_res_hall_fit(
            *a, *fermi, *res, [-1], ([0], [10]), scattering, progress=progress
        )
    assert {stage: len(fit[0]) for stage, fit in progress.stage_fits.items()} == lengths


@pytest.mark.filterwarnings("ignore")
def test_a_stopped_hall_fit_does_not_flag_m1_it_never_fitted() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho_rh")
    args = recorded_args("03_AWI32_SI", "dpb_s_rho_rh", "dpb_see_res_hall_fit")
    a = [np.array(value) for value in args[:6]]
    data: dict[Any, Measurement] = {
        "seebeck": Measurement(a[0], a[1]),
        "resistivity": Measurement(a[2], a[3]),
        "hall": Measurement(a[4], a[5]),
    }

    def stop(update: IterationUpdate) -> None:
        raise FitStopped

    start = default_start(fit_mode) | {"m1": 10.0}
    result = model.fit(FitRequest("dpb_s_rho_rh", data, start, scattering="acPh"), stop)
    assert result.status == "stopped"
    assert "m1" not in result.at_bounds
    assert "m1" not in result.parameter_errors


@pytest.mark.filterwarnings("ignore")
def test_a_stopped_fit_flags_what_it_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    class AtBound:
        def __getattr__(self, name: str) -> Any:
            def run(*args: Any, progress: fit_module.FitProgress, **kwargs: Any) -> Any:
                progress.iterations = 1
                progress.on_iteration(1, [3.0, 500.0, 500.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
                raise AssertionError("The callback should have stopped this")

            return run

    def stop(update: IterationUpdate) -> None:
        raise FitStopped

    monkeypatch.setattr(band_models, "_CORE", AtBound())
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    result = model.fit(
        FitRequest(
            "dpb_s_rho",
            {q: synthetic_seebeck() for q in fit_mode.quantities},
            default_start(fit_mode),
            scattering="acPh",
        ),
        stop,
    )
    assert result.status == "stopped"
    assert result.at_bounds == ("m_eff",)


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
