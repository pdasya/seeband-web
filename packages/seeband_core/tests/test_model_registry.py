import dataclasses
import json
import pickle
from typing import Any

import numpy as np
import pytest
from seeband_core.model_descriptions import load_desktop_descriptions
from seeband_core.model_interface import (
    ALL_CURVE_KINDS,
    Bounds,
    CurveRequest,
    CurveResult,
    Degeneracy,
    FitMode,
    FitRequest,
    FitResult,
    IterationCallback,
    Measurement,
    Model,
    ModelDescription,
    ParameterSpec,
    UnavailableCurve,
    ValueRange,
)
from seeband_core.model_registry import ModelRegistry
from seeband_core.model_scales import (
    core_range,
    core_to_display,
    default_start,
    default_start_value,
    display_range,
    display_to_core,
    scale_value,
)

SLOPE = ParameterSpec(
    name="slope",
    meaning="change of S with temperature",
    unit="V/K^2",
    role="fitted",
    scattering=(),
    value_range=ValueRange(-100, 100, 1, 1),
    display_scale=1e-9,
    fit_scale=1e-9,
    calc_scale=1e-9,
    fit_bounds=Bounds(-1e-6, 1e-6),
)
LINEAR_MODE = FitMode(id="linear_s", quantities=("seebeck",), parameters=(SLOPE,))


def description(*fit_modes: FitMode, model_id: str = "linear") -> ModelDescription:
    return ModelDescription(model_id, "Linear", fit_modes, 50.0, 800.0, 50)


class LinearModel:
    """S = slope * T. It exists only to show that a new model needs no other code."""

    def describe(self) -> ModelDescription:
        return description(LINEAR_MODE)

    def calculate(self, request: CurveRequest) -> CurveResult:
        temperature_k = np.linspace(
            request.min_temperature_k, request.max_temperature_k, request.points
        )
        return CurveResult(
            temperature_k, {"seebeck_v_per_k": request.parameters["slope"] * temperature_k}
        )

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        data = request.measurements["seebeck"]
        slope = np.dot(data.temperature_k, data.values) / np.dot(
            data.temperature_k, data.temperature_k
        )
        return FitResult({"slope": float(slope)}, "converged")


class Described(LinearModel):
    def __init__(self, model_description: ModelDescription) -> None:
        self.model_description = model_description

    def describe(self) -> ModelDescription:
        return self.model_description


def test_a_new_model_works_through_the_registry_alone() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())

    found = registry.descriptions()[0]
    assert found.id == "linear"
    fit_mode = found.fit_mode("linear_s")
    start = default_start(fit_mode)

    model = registry.get("linear")
    curve = model.calculate(CurveRequest("linear_s", {"slope": 2e-9}, 100.0, 300.0, 3))
    assert curve.temperature_k.tolist() == [100.0, 200.0, 300.0]
    measurement = Measurement(curve.temperature_k, curve.curves["seebeck_v_per_k"])
    fitted = model.fit(FitRequest("linear_s", {"seebeck": measurement}, start))
    assert fitted.parameters["slope"] == pytest.approx(2e-9)
    assert fitted.status == "converged"


def test_get_returns_the_requested_model_and_order_is_kept() -> None:
    registry = ModelRegistry()
    first, second = Described(description(LINEAR_MODE, model_id="b")), LinearModel()
    registry.register(first)
    registry.register(second)
    assert registry.get("b") is first
    assert registry.get("linear") is second
    assert [item.id for item in registry.descriptions()] == ["b", "linear"]


def test_registering_a_model_twice_is_an_error() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(LinearModel())


def test_an_object_that_is_not_a_model_is_an_error() -> None:
    with pytest.raises(TypeError, match="does not implement"):
        ModelRegistry().register(object())  # type: ignore[arg-type]


def replaced(spec: ParameterSpec = SLOPE, **changes: Any) -> ParameterSpec:
    return dataclasses.replace(spec, **changes)


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (description(), "no fit modes"),
        (description(LINEAR_MODE, model_id=""), "needs an id"),
        (description(LINEAR_MODE, LINEAR_MODE), "repeats a fit mode"),
        (
            description(FitMode("m", ("seebeck",), (SLOPE, SLOPE))),
            "repeats a parameter",
        ),
        (
            description(FitMode("m", ("seebeck",), (SLOPE,), default_scattering="acPh")),
            "unknown scattering",
        ),
        (
            description(
                FitMode("m", ("seebeck",), (replaced(value_range=ValueRange(0, 10, 1, 11)),))
            ),
            "invalid range",
        ),
        (
            description(
                FitMode("m", ("seebeck",), (replaced(value_range=ValueRange(0, 10, 0, 5)),))
            ),
            "invalid range",
        ),
        (
            description(FitMode("m", ("seebeck",), (replaced(fit_bounds=Bounds(2, 1)),))),
            "inverted bounds",
        ),
    ],
)
def test_invalid_descriptions_are_refused_and_leave_nothing_behind(
    bad: ModelDescription, message: str
) -> None:
    registry = ModelRegistry()
    with pytest.raises(ValueError, match=message):
        registry.register(Described(bad))
    assert registry.descriptions() == ()


def test_unknown_names_are_errors() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())
    with pytest.raises(KeyError, match="Unknown model: nothing"):
        registry.get("nothing")
    with pytest.raises(KeyError, match="no fit mode nothing"):
        registry.descriptions()[0].fit_mode("nothing")


def test_registries_are_separate() -> None:
    first, second = ModelRegistry(), ModelRegistry()
    first.register(LinearModel())
    assert second.descriptions() == ()


def test_requests_and_descriptions_can_go_to_a_worker_process() -> None:
    measurement = Measurement(np.array([1.0]), np.array([2.0]))
    request = FitRequest("linear_s", {"seebeck": measurement}, {"slope": 1.0})
    assert pickle.loads(pickle.dumps(request)).start == {"slope": 1.0}
    original = load_desktop_descriptions()["dpb"]
    assert pickle.loads(pickle.dumps(original)) == original


def test_descriptions_serialise_to_json() -> None:
    for item in load_desktop_descriptions().values():
        text = json.dumps(dataclasses.asdict(item), allow_nan=False)
        assert json.loads(text)["id"] == item.id


# Written here so that a change to the table fails. name: unit, role, control minimum, maximum,
# step and default, display scale, fit scale, calc scale, fit bounds, editable bounds.
K_FULL = ("K", "fitted", -3000, 3000)
EXPECTED_PARAMETERS: dict[str, list[tuple[Any, ...]]] = {
    "spb_s": [
        ("band_mass", "m_e", "fixed", -300, 300, 1, 101, 0.01, 0.01, 0.01, None, False),
        ("fermi_energy", *K_FULL, 1, 100, 1, 1, 1, (-3000, 3000), True),
    ],
    "spb_s_rho": [
        ("band_mass", "m_e", "fixed", -300, 300, 1, -100, 0.01, 0.01, 0.01, None, False),
        ("fermi_energy", *K_FULL, 1, -100, 1, 1, 1, (-3000, 3000), True),
        ("A", "unknown", "fitted", 0, 1000000, 1000, 40000, 1, 1, 1, (1, 1e7), False),
        ("C", "dimensionless", "fitted", 0, 300, 1, 100, 0.01, 1, 1, (0.001, 1000), False),
        ("F", "unknown", "fitted", 0, 100000, 100, 4000, 1, 1, 1, (1, 1e7), False),
    ],
    "spb_s_rho_rh": [
        ("band_mass", "m_e", "fitted", -300, 300, 1, 100, 0.01, 1, 0.01, (-300, 300), True),
        ("fermi_energy", *K_FULL, 1, 100, 1, 1, 1, (-3000, 3000), True),
        ("A", "unknown", "fitted", 0, 1000000, 1000, 40000, 1, 1, 1, (1, 1e7), False),
        ("C", "dimensionless", "fitted", 0, 300, 1, 100, 0.01, 1, 300, (0.001, 1000), False),
        ("F", "unknown", "fitted", 0, 100000, 100, 4000, 1, 1, 1, (1, 1e7), False),
    ],
    "dpb_s": [
        ("m_eff", "dimensionless", "fitted", -300, 300, 1, 101, 0.01, 0.01, 0.01, (-3, 3), True),
        ("band_gap", *K_FULL, 10, 1000, 1, 1, 1, (-3000, 3000), True),
        ("fermi_energy", *K_FULL, 1, -100, 1, 1, 1, (-3000, 3000), True),
    ],
}
DPB_SCATTERING = [
    ("A", "unknown", "fitted", 0, 1000000, 1000, 40000, 1, 1, 1, (0, 1e6), True),
    ("B", "dimensionless", "fitted", 90, 110, 1, 100, 0.01, 0.01, 0.01, (0.9, 1.1), True),
    ("C", "dimensionless", "fitted", 50, 200, 1, 100, 0.01, 0.01, 0.01, (0.5, 2), True),
    ("D", "dimensionless", "fitted", 50, 200, 1, 100, 0.01, 0.01, 0.01, (0.5, 2), True),
]
EXPECTED_PARAMETERS["dpb_s_rho"] = [
    *EXPECTED_PARAMETERS["dpb_s"],
    *DPB_SCATTERING,
    ("F", "unknown", "fitted", 0, 100000, 100, 1000, 1, 1, 1, (0, 1e5), True),
    ("G", "dimensionless", "fitted", 50, 200, 1, 100, 0.01, 0.01, 0.01, (0.5, 2), True),
]
EXPECTED_PARAMETERS["dpb_s_rho_rh"] = [
    *EXPECTED_PARAMETERS["dpb_s"],
    *DPB_SCATTERING,
    ("F", "unknown", "fitted", 0, 100000, 1000, 1000, 1, 1, 1, (0, 1e5), True),
    # The web bounds of D1. The desktop's are 50 to 200.
    ("G", "dimensionless", "fitted", 50, 200, 100, 100, 0.01, 0.01, 0.01, (0.5, 2), True),
    ("m1", "m_e", "fitted", 10, 1000, 1, 100, 0.01, 0.01, 0.01, (0.1, 10), True),
]


def fit_mode_named(fit_mode_id: str) -> FitMode:
    model_id = fit_mode_id.partition("_")[0]
    return load_desktop_descriptions()[model_id].fit_mode(fit_mode_id)


def parameter_named(fit_mode_id: str, name: str) -> ParameterSpec:
    return next(spec for spec in fit_mode_named(fit_mode_id).parameters if spec.name == name)


def test_descriptions_hold_exactly_the_expected_models_and_modes() -> None:
    descriptions = load_desktop_descriptions()
    assert [(item.id, item.name) for item in descriptions.values()] == [
        ("spb", "Single parabolic band"),
        ("dpb", "Double parabolic band"),
    ]
    assert list(descriptions) == ["spb", "dpb"]
    found = [mode.id for item in descriptions.values() for mode in item.fit_modes]
    assert found == list(EXPECTED_PARAMETERS)
    for item in descriptions.values():
        assert item.default_min_temperature_k == 50
        assert item.default_max_temperature_k == 800
        assert item.default_curve_points == 50


@pytest.mark.parametrize("fit_mode_id", EXPECTED_PARAMETERS)
def test_parameters_match_the_values_written_here(fit_mode_id: str) -> None:
    found = []
    for spec in fit_mode_named(fit_mode_id).parameters:
        limits = spec.value_range
        bounds = spec.fit_bounds
        found.append(
            (
                spec.name,
                spec.unit,
                spec.role,
                limits.minimum,
                limits.maximum,
                limits.step,
                limits.default,
                spec.display_scale,
                spec.fit_scale,
                spec.calc_scale,
                (bounds.lower, bounds.upper) if bounds else None,
                spec.bounds_editable,
            )
        )
    assert found == EXPECTED_PARAMETERS[fit_mode_id]


def test_meanings_come_from_the_table() -> None:
    assert parameter_named("dpb_s", "band_gap").meaning == "position of band 2"
    for fit_mode_id in EXPECTED_PARAMETERS:
        for spec in fit_mode_named(fit_mode_id).parameters:
            assert spec.meaning and spec.meaning != spec.name


@pytest.mark.parametrize(
    ("fit_mode_id", "quantities", "iterative", "threshold", "max_iterations", "degeneracy"),
    [
        ("spb_s", ("seebeck",), False, None, None, None),
        ("spb_s_rho", ("seebeck", "resistivity"), False, None, None, None),
        ("spb_s_rho_rh", ("seebeck", "resistivity", "hall"), False, None, None, None),
        ("dpb_s", ("seebeck",), False, None, None, Degeneracy(1, 1)),
        ("dpb_s_rho", ("seebeck", "resistivity"), True, 0.1, 1000, Degeneracy(1, 1)),
        ("dpb_s_rho_rh", ("seebeck", "resistivity", "hall"), True, 0.1, 20, Degeneracy(1, 1)),
    ],
)
def test_fit_modes_are_as_written_here(
    fit_mode_id: str,
    quantities: tuple[str, ...],
    iterative: bool,
    threshold: float | None,
    max_iterations: int | None,
    degeneracy: Degeneracy | None,
) -> None:
    fit_mode = fit_mode_named(fit_mode_id)
    assert fit_mode.quantities == quantities
    assert fit_mode.iterative is iterative
    assert fit_mode.threshold == threshold
    assert fit_mode.max_iterations == max_iterations
    assert fit_mode.degeneracy == degeneracy


@pytest.mark.parametrize("fit_mode_id", ["spb_s_rho", "spb_s_rho_rh", "dpb_s_rho", "dpb_s_rho_rh"])
def test_scattering_options_are_kept(fit_mode_id: str) -> None:
    fit_mode = fit_mode_named(fit_mode_id)
    assert fit_mode.scattering == ("acPh", "dis", "acPhDis")
    assert fit_mode.default_scattering == "acPh"


@pytest.mark.parametrize("fit_mode_id", ["spb_s", "dpb_s"])
def test_modes_without_a_choice_have_no_scattering(fit_mode_id: str) -> None:
    fit_mode = fit_mode_named(fit_mode_id)
    assert (fit_mode.scattering, fit_mode.default_scattering) == ((), None)
    with pytest.raises(ValueError, match="no scattering type"):
        fit_mode.parameters_for("acPh")


def test_parameters_are_filtered_by_scattering() -> None:
    fit_mode = fit_mode_named("dpb_s_rho")
    names = [spec.name for spec in fit_mode.parameters_for("dis")]
    assert names == ["m_eff", "band_gap", "fermi_energy", "F", "G"]
    names = [spec.name for spec in fit_mode.parameters_for("acPhDis")]
    assert names == ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D"]
    assert fit_mode.parameters_for(None) == fit_mode.parameters
    with pytest.raises(ValueError, match="no scattering type bogus"):
        fit_mode.parameters_for("bogus")


def test_a_parameter_without_scattering_applies_to_every_type() -> None:
    fit_mode = FitMode("m", ("seebeck",), (SLOPE,), scattering=("acPh",))
    assert fit_mode.parameters_for("acPh") == (SLOPE,)


def test_curve_kinds_follow_the_desktop_graphs() -> None:
    assert fit_mode_named("spb_s").curve_kinds == ("measured", "chemical_potential")
    assert "thermal_conductivity" in fit_mode_named("spb_s_rho").curve_kinds
    assert "carrier_concentration_by_band" in fit_mode_named("dpb_s").curve_kinds
    assert "electrical_conductivity" not in fit_mode_named("dpb_s").curve_kinds
    assert "electrical_conductivity_by_band" in fit_mode_named("dpb_s_rho_rh").curve_kinds


@pytest.mark.parametrize("control", range(-300, 301))
def test_a_scale_of_one_hundredth_divides_as_the_desktop_does(control: int) -> None:
    assert scale_value(control, 0.01) == control / 100


def test_whole_scales_multiply() -> None:
    assert scale_value(7, 1) == 7
    assert scale_value(7, 300) == 2100


def test_default_starts_match_the_recorded_desktop_calls() -> None:
    assert default_start_value(parameter_named("spb_s", "band_mass")) == 1.01
    assert default_start(fit_mode_named("dpb_s")) == {
        "m_eff": 1.01,
        "band_gap": 1000,
        "fermi_energy": -100,
    }
    assert default_start(fit_mode_named("spb_s_rho")) == {
        "band_mass": -1.0,
        "fermi_energy": -100,
        "A": 40000,
        "C": 100,
        "F": 4000,
    }


def test_a_default_start_holds_fixed_and_inactive_parameters() -> None:
    assert set(default_start(fit_mode_named("dpb_s_rho"))) == {
        "m_eff",
        "band_gap",
        "fermi_energy",
        "A",
        "B",
        "C",
        "D",
        "F",
        "G",
    }


def test_display_and_core_values_convert_both_ways() -> None:
    spb_c = parameter_named("spb_s_rho", "C")
    assert core_to_display(spb_c, 100) == 1.0
    assert display_to_core(spb_c, 1.0) == 100
    dpb_c = parameter_named("dpb_s_rho", "C")
    assert core_to_display(dpb_c, 1.5) == 1.5
    assert display_to_core(dpb_c, 1.5) == 1.5


def test_display_range_uses_the_display_scale() -> None:
    assert display_range(parameter_named("dpb_s", "m_eff")) == ValueRange(-3.0, 3.0, 0.01, 1.01)
    assert display_range(parameter_named("spb_s_rho", "A")) == ValueRange(0, 1000000, 1000, 40000)


def test_the_linear_model_is_a_model() -> None:
    model: Model = LinearModel()
    assert isinstance(model, Model)


def _with_spec_changes(**changes: Any) -> ModelDescription:
    spec = dataclasses.replace(LINEAR_MODE.parameters[0], **changes)
    return description(dataclasses.replace(LINEAR_MODE, parameters=(spec,)))


@pytest.mark.parametrize("scale", [0.0, -1.0, 0.3, 0.7])
@pytest.mark.parametrize("field", ["display_scale", "fit_scale"])
def test_scale_that_scale_value_cannot_honour_is_refused(field: str, scale: float) -> None:
    model = Described(_with_spec_changes(**{field: scale}))

    with pytest.raises(ValueError, match="scale"):
        ModelRegistry().register(model)


@pytest.mark.parametrize("scale", [0.01, 0.5, 1.0, 300.0, 1e-3])
def test_usual_scales_are_accepted(scale: float) -> None:
    ModelRegistry().register(Described(_with_spec_changes(fit_scale=scale)))


def test_core_range_uses_the_division_of_the_desktop() -> None:
    spec = dataclasses.replace(
        LINEAR_MODE.parameters[0], value_range=ValueRange(57, 70, 7, 57), fit_scale=0.01
    )

    assert core_range(spec) == ValueRange(57 / 100, 70 / 100, 7 / 100, 57 / 100)


SPB_UNAVAILABLE = {
    "seebeck": "same_as_measured",
    "seebeck_by_band": "single_band",
    "electrical_conductivity_by_band": "single_band",
    "carrier_concentration_by_band": "not_on_desktop",
}
# By the buttons of AddGraphsWin* in seeband.py, from which curve_kinds follow.
EXPECTED_UNAVAILABLE: dict[str, dict[str, str]] = {
    "spb_s": {
        **SPB_UNAVAILABLE,
        "electrical_conductivity": "needs_resistivity",
        "thermal_conductivity": "needs_resistivity",
    },
    "spb_s_rho": SPB_UNAVAILABLE,
    "spb_s_rho_rh": SPB_UNAVAILABLE,
    "dpb_s": {
        "seebeck": "same_as_measured",
        "electrical_conductivity": "needs_resistivity",
        "electrical_conductivity_by_band": "needs_resistivity",
        "thermal_conductivity": "needs_resistivity",
    },
    "dpb_s_rho": {},
    "dpb_s_rho_rh": {},
}


@pytest.mark.parametrize("name", EXPECTED_UNAVAILABLE)
def test_every_kind_of_curve_is_offered_or_has_a_reason(name: str) -> None:
    mode = fit_mode_named(name)

    reasons = {kind: mode.unavailable_reason(kind) for kind in ALL_CURVE_KINDS}

    assert {kind: reason for kind, reason in reasons.items() if reason} == EXPECTED_UNAVAILABLE[
        name
    ]
    assert set(mode.curve_kinds) == {kind for kind, reason in reasons.items() if reason is None}


def test_only_carrier_concentration_without_hall_data_is_relative() -> None:
    relative = {name: fit_mode_named(name).relative_curve_kinds for name in EXPECTED_UNAVAILABLE}

    assert relative == {
        "spb_s": (),
        "spb_s_rho": (),
        "spb_s_rho_rh": (),
        "dpb_s": ("carrier_concentration_by_band",),
        "dpb_s_rho": ("carrier_concentration_by_band",),
        "dpb_s_rho_rh": (),
    }


def test_a_new_model_need_not_list_its_missing_curves() -> None:
    assert LINEAR_MODE.unavailable_reason("chemical_potential") == "not_provided"
    assert LINEAR_MODE.unavailable_reason("measured") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"unavailable_curves": (UnavailableCurve("measured", "because"),)},
        {"relative_curve_kinds": ("chemical_potential",)},
        {"unavailable_curves": (UnavailableCurve("seebeck", ""),)},
        {
            "unavailable_curves": (
                UnavailableCurve("seebeck", "a"),
                UnavailableCurve("seebeck", "b"),
            )
        },
    ],
)
def test_contradictory_curve_descriptions_are_refused(changes: dict[str, Any]) -> None:
    model = Described(description(dataclasses.replace(LINEAR_MODE, **changes)))

    with pytest.raises(ValueError, match="Fit mode"):
        ModelRegistry().register(model)
