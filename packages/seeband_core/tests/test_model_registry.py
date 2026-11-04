import json
from importlib import resources
from typing import Any

import numpy as np
import pytest
from seeband_core.model_descriptions import load_desktop_descriptions
from seeband_core.model_interface import (
    Bounds,
    CurveRequest,
    CurveResult,
    FitMode,
    FitRequest,
    FitResult,
    Measurement,
    Model,
    ModelDescription,
    ParameterSpec,
    ValueRange,
)
from seeband_core.model_registry import ModelRegistry
from seeband_core.model_registry import registry as default_registry

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


class LinearModel:
    """S = slope * T. It exists only to show that a new model needs no other code."""

    def describe(self) -> ModelDescription:
        fit_mode = FitMode(id="linear_s", quantities=("seebeck",), parameters=(SLOPE,))
        return ModelDescription(id="linear", name="Linear", fit_modes=(fit_mode,))

    def calculate(self, request: CurveRequest) -> CurveResult:
        temperature_k = np.linspace(
            request.min_temperature_k, request.max_temperature_k, request.points
        )
        return CurveResult(temperature_k, {"seebeck": request.parameters["slope"] * temperature_k})

    def fit(self, request: FitRequest) -> FitResult:
        data = request.measurements["seebeck"]
        slope = np.dot(data.temperature_k, data.values) / np.dot(
            data.temperature_k, data.temperature_k
        )
        return FitResult({"slope": float(slope)})


def table_modes() -> dict[str, dict[str, Any]]:
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    return {mode["id"]: mode for mode in json.loads(path.read_text("utf-8"))["modes"]}


def test_a_new_model_works_through_the_registry_alone() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())

    description = registry.descriptions()[0]
    assert description.id == "linear"
    fit_mode = description.fit_mode("linear_s")
    start = {spec.name: spec.value_range.default * spec.fit_scale for spec in fit_mode.parameters}

    model = registry.get("linear")
    curve = model.calculate(CurveRequest("linear_s", {"slope": 2e-9}, 100.0, 300.0, 3))
    assert curve.temperature_k.tolist() == [100.0, 200.0, 300.0]
    measurement = Measurement(curve.temperature_k, curve.curves["seebeck"])
    fitted = model.fit(FitRequest("linear_s", {"seebeck": measurement}, start))
    assert fitted.parameters["slope"] == pytest.approx(2e-9)


def test_linear_model_satisfies_the_protocol() -> None:
    assert isinstance(LinearModel(), Model)


def test_registering_a_model_twice_is_an_error() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(LinearModel())


def test_repeating_a_fit_mode_is_an_error() -> None:
    class Repeated(LinearModel):
        def describe(self) -> ModelDescription:
            fit_mode = super().describe().fit_modes[0]
            return ModelDescription("repeated", "Repeated", (fit_mode, fit_mode))

    with pytest.raises(ValueError, match="repeats a fit mode"):
        ModelRegistry().register(Repeated())


def test_unknown_names_are_errors() -> None:
    registry = ModelRegistry()
    registry.register(LinearModel())
    with pytest.raises(KeyError, match="Unknown model: nothing"):
        registry.get("nothing")
    with pytest.raises(KeyError, match="no fit mode nothing"):
        registry.descriptions()[0].fit_mode("nothing")


def test_registries_do_not_share_models() -> None:
    ModelRegistry().register(LinearModel())
    assert "linear" not in [description.id for description in default_registry.descriptions()]


def test_descriptions_hold_every_mode_of_the_table() -> None:
    descriptions = load_desktop_descriptions()
    assert list(descriptions) == ["spb", "dpb"]
    assert [fit_mode.id for fit_mode in descriptions["spb"].fit_modes] == [
        "spb_s",
        "spb_s_rho",
        "spb_s_rho_rh",
    ]
    assert [fit_mode.id for fit_mode in descriptions["dpb"].fit_modes] == [
        "dpb_s",
        "dpb_s_rho",
        "dpb_s_rho_rh",
    ]


def all_parameters() -> list[tuple[FitMode, ParameterSpec]]:
    return [
        (fit_mode, parameter)
        for description in load_desktop_descriptions().values()
        for fit_mode in description.fit_modes
        for parameter in fit_mode.parameters
    ]


@pytest.mark.parametrize(
    ("fit_mode", "parameter"),
    all_parameters(),
    ids=lambda value: value.id if isinstance(value, FitMode) else value.name,
)
def test_parameters_match_the_table(fit_mode: FitMode, parameter: ParameterSpec) -> None:
    entries = {entry["name"]: entry for entry in table_modes()[fit_mode.id]["parameters"]}
    entry = entries[parameter.name]
    assert parameter.unit == entry["unit"]
    assert parameter.role == entry["role"]
    assert parameter.scattering == tuple(entry["scattering"])
    assert parameter.value_range == ValueRange(
        entry["slider"]["min"],
        entry["slider"]["max"],
        entry["slider"]["step"],
        entry["slider"]["default"],
    )
    assert (parameter.display_scale, parameter.fit_scale, parameter.calc_scale) == (
        entry["display_scale"],
        entry["fit_scale"],
        entry["calc_scale"],
    )


def fit_mode_named(fit_mode_id: str) -> FitMode:
    model_id = fit_mode_id.partition("_")[0]
    return load_desktop_descriptions()[model_id].fit_mode(fit_mode_id)


def parameter_named(fit_mode_id: str, name: str) -> ParameterSpec:
    return next(spec for spec in fit_mode_named(fit_mode_id).parameters if spec.name == name)


def test_web_bounds_replace_the_desktop_bounds_of_the_recorded_deviation() -> None:
    assert parameter_named("dpb_s_rho_rh", "G").fit_bounds == Bounds(0.5, 2)
    assert parameter_named("dpb_s_rho", "G").fit_bounds == Bounds(0.5, 2)


def test_parameter_values_are_as_written_here() -> None:
    mass = parameter_named("spb_s", "band_mass")
    assert (mass.role, mass.unit, mass.fit_bounds) == ("fixed", "m_e", None)
    assert parameter_named("dpb_s", "m_eff").fit_bounds == Bounds(-3, 3)
    assert parameter_named("dpb_s", "m_eff").bounds_editable
    assert parameter_named("spb_s_rho", "C").display_scale == 0.01
    assert parameter_named("spb_s_rho", "C").fit_scale == 1
    assert not parameter_named("spb_s_rho", "C").bounds_editable


@pytest.mark.parametrize(
    ("fit_mode_id", "quantities", "iterative", "threshold", "max_iterations", "uses_degeneracy"),
    [
        ("spb_s", ("seebeck",), False, None, None, False),
        ("spb_s_rho", ("seebeck", "resistivity"), False, None, None, False),
        ("spb_s_rho_rh", ("seebeck", "resistivity", "hall"), False, None, None, False),
        ("dpb_s", ("seebeck",), False, None, None, True),
        ("dpb_s_rho", ("seebeck", "resistivity"), True, 0.1, 1000, True),
        ("dpb_s_rho_rh", ("seebeck", "resistivity", "hall"), True, 0.1, 20, True),
    ],
)
def test_fit_modes_are_as_written_here(
    fit_mode_id: str,
    quantities: tuple[str, ...],
    iterative: bool,
    threshold: float | None,
    max_iterations: int | None,
    uses_degeneracy: bool,
) -> None:
    fit_mode = fit_mode_named(fit_mode_id)
    assert fit_mode.quantities == quantities
    assert fit_mode.iterative is iterative
    assert fit_mode.threshold == threshold
    assert fit_mode.max_iterations == max_iterations
    assert fit_mode.uses_degeneracy is uses_degeneracy


def test_scattering_options_and_filtering() -> None:
    assert fit_mode_named("dpb_s").scattering == ()
    fit_mode = fit_mode_named("dpb_s_rho")
    assert fit_mode.scattering == ("acPh", "dis", "acPhDis")
    assert fit_mode.default_scattering == "acPh"
    names = [spec.name for spec in fit_mode.parameters_for("dis")]
    assert names == ["m_eff", "band_gap", "fermi_energy", "F", "G"]
    names = [spec.name for spec in fit_mode.parameters_for("acPhDis")]
    assert names == ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D"]
    assert fit_mode.parameters_for(None) == fit_mode.parameters
