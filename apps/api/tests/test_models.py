import json
import re
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_api.models import _registry_response, build_models_response
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    BandDiagramRequest,
    BandDiagramResult,
    Bounds,
    CurveRequest,
    CurveResult,
    Degeneracy,
    FitMode,
    FitRequest,
    FitResult,
    IterationCallback,
    KnownIssue,
    ModelDescription,
    ParameterSpec,
    ValueRange,
)
from seeband_core.model_registry import ModelRegistry
from seeband_core.model_scales import core_range, display_range

CONTRACT = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"


@pytest.fixture(scope="module")
def response() -> Any:
    return TestClient(create_app()).get("/api/models")


@pytest.fixture(scope="module")
def modes(response: Any) -> dict[str, dict[str, Any]]:
    return {mode["id"]: mode for model in response.json()["models"] for mode in model["fit_modes"]}


def _parameter(mode: dict[str, Any], name: str) -> dict[str, Any]:
    return next(spec for spec in mode["parameters"] if spec["name"] == name)


def test_lists_both_models_and_all_modes(response: Any) -> None:
    assert response.status_code == 200
    models = response.json()["models"]

    assert [(model["id"], model["name"]) for model in models] == [
        ("spb", "Single parabolic band"),
        ("dpb", "Double parabolic band"),
    ]
    assert [[mode["id"] for mode in model["fit_modes"]] for model in models] == [
        ["spb_s", "spb_s_rho", "spb_s_rho_rh"],
        ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"],
    ]
    assert models[0]["default_min_temperature_k"] == 50
    assert models[0]["default_max_temperature_k"] == 800
    assert models[0]["default_curve_points"] == 50


def test_spb_hall_mode_is_disabled_with_its_reason(modes: dict[str, dict[str, Any]]) -> None:
    mode = modes["spb_s_rho_rh"]

    assert mode["disabled"] is True
    assert mode["disabled_by"] == ["spb_hall_mode_disabled"]
    reason = next(issue for issue in mode["known_issues"] if issue["id"] == mode["disabled_by"][0])
    assert reason["severity"] == "disabled"
    assert reason["message_key"] == "known_issue.spb_hall_mode_disabled"
    assert reason["fixed_by"] == "#83"


def test_only_that_mode_is_disabled(modes: dict[str, dict[str, Any]]) -> None:
    assert [name for name, mode in modes.items() if mode["disabled"]] == ["spb_s_rho_rh"]
    assert all(mode["disabled_by"] == [] for mode in modes.values() if not mode["disabled"])


@pytest.mark.parametrize(
    ("name", "iterative", "threshold", "max_iterations"),
    [
        ("spb_s", False, None, None),
        ("spb_s_rho", False, None, None),
        ("dpb_s", False, None, None),
        ("dpb_s_rho", True, 0.1, 1000),
        ("dpb_s_rho_rh", True, 0.1, 20),
    ],
)
def test_single_pass_and_iterative_modes(
    modes: dict[str, dict[str, Any]],
    name: str,
    iterative: bool,
    threshold: float | None,
    max_iterations: int | None,
) -> None:
    mode = modes[name]

    assert mode["iterative"] is iterative
    assert mode.get("threshold") == threshold
    assert mode.get("max_iterations") == max_iterations


def test_fields_that_do_not_apply_are_left_out(modes: dict[str, dict[str, Any]]) -> None:
    mode = modes["spb_s"]

    assert mode["scattering"] == []
    for field in ("default_scattering", "threshold", "max_iterations", "degeneracy"):
        assert field not in mode
    assert modes["dpb_s_rho"]["degeneracy"] == {"band_1_default": 1, "band_2_default": 1}


def test_ranges_of_a_parameter_shown_at_another_scale(modes: dict[str, dict[str, Any]]) -> None:
    # From seeband.py: C in SPB S + rho shows as slider / 100, and enters a fit as the slider value.
    spec = _parameter(modes["spb_s_rho"], "C")

    assert spec["display_scale"] == 0.01
    assert spec["fit_scale"] == 1
    assert spec["value_range"]["default"] == 100
    assert spec["core_range"]["default"] == 100
    assert spec["display_range"]["default"] == 1
    assert spec["role"] == "fitted"
    assert spec["scattering"] == ["acPhDis"]


def test_core_range_divides_as_the_desktop_does() -> None:
    # 57 / 100 and 57 * 0.01 differ in the last bit, so this tells them apart.
    assert 57 / 100 != 57 * 0.01
    spec = ParameterSpec(
        name="p",
        meaning="A test parameter",
        unit="K",
        role="fitted",
        scattering=(),
        value_range=ValueRange(57, 57, 1, 57),
        display_scale=1,
        fit_scale=0.01,
        calc_scale=1,
    )
    description = ModelDescription(
        id="test",
        name="Test model",
        fit_modes=(FitMode(id="m", quantities=("seebeck",), parameters=(spec,)),),
        default_min_temperature_k=10,
        default_max_temperature_k=20,
        default_curve_points=5,
    )

    [model] = build_models_response([description]).models
    limits = model.fit_modes[0].parameters[0].core_range

    assert limits.default == 57 / 100
    assert limits.minimum == 57 / 100


def test_bounds_are_given_or_left_out(modes: dict[str, dict[str, Any]]) -> None:
    assert _parameter(modes["dpb_s_rho_rh"], "A")["fit_bounds"] == {"lower": 0, "upper": 1000000}

    fixed = _parameter(modes["spb_s"], "band_mass")
    assert fixed["role"] == "fixed"
    assert "fit_bounds" not in fixed


def test_desktop_only_scale_is_not_exposed(response: Any) -> None:
    assert "calc_scale" not in response.text


def test_known_issue_conditions_and_scope_reach_the_client(
    modes: dict[str, dict[str, Any]],
) -> None:
    issues = {issue["id"]: issue for issue in modes["dpb_s_rho_rh"]["known_issues"]}

    assert issues["dpb_hall_prefactor"]["columns"][0] == "hall_m3_per_c"
    assert issues["dpb_hall_prefactor"]["severity"] == "unreliable"
    assert issues["acphdis_early_stop"]["scattering"] == ["acPhDis"]
    assert issues["collapsed_m_eff"]["condition"] == "collapsed_m_eff"
    assert "condition" not in issues["dpb_hall_prefactor"]


def test_every_field_matches_the_registry(response: Any) -> None:
    """The values are checked in the core, so this checks that the route carries all of them."""
    models = response.json()["models"]
    descriptions = registry.descriptions()

    assert [model["id"] for model in models] == [description.id for description in descriptions]
    for model, description in zip(models, descriptions, strict=True):
        assert model["name"] == description.name
        assert model["default_min_temperature_k"] == description.default_min_temperature_k
        assert model["default_max_temperature_k"] == description.default_max_temperature_k
        assert model["default_curve_points"] == description.default_curve_points
        assert [mode["id"] for mode in model["fit_modes"]] == [
            fit_mode.id for fit_mode in description.fit_modes
        ]
        for mode, fit_mode in zip(model["fit_modes"], description.fit_modes, strict=True):
            _check_mode(mode, fit_mode)


def _check_mode(mode: dict[str, Any], fit_mode: FitMode) -> None:
    assert mode["quantities"] == list(fit_mode.quantities)
    assert mode["scattering"] == list(fit_mode.scattering)
    assert mode.get("default_scattering") == fit_mode.default_scattering
    assert mode.get("threshold") == fit_mode.threshold
    assert mode.get("max_iterations") == fit_mode.max_iterations
    assert mode["curve_kinds"] == list(fit_mode.curve_kinds)
    if fit_mode.degeneracy is None:
        assert "degeneracy" not in mode
    else:
        assert mode["degeneracy"] == asdict(fit_mode.degeneracy)
    assert [issue["id"] for issue in mode["known_issues"]] == [i.id for i in fit_mode.known_issues]
    for issue, known in zip(mode["known_issues"], fit_mode.known_issues, strict=True):
        assert issue["severity"] == known.severity
        assert issue["message_key"] == known.message_key
        assert issue["fixed_by"] == known.fixed_by
        assert issue["scattering"] == list(known.scattering)
        assert issue["curve_kinds"] == list(known.curve_kinds)
        assert issue["columns"] == list(known.columns)
        assert issue["affects_fit"] == known.affects_fit
        assert issue.get("condition") == known.condition
    assert [spec["name"] for spec in mode["parameters"]] == [p.name for p in fit_mode.parameters]
    assert mode["stages"] == [
        {
            "quantity": stage.quantity,
            "parameters": list(stage.parameters),
            "repeats": stage.repeats,
        }
        for stage in fit_mode.stages
    ]
    for spec, parameter in zip(mode["parameters"], fit_mode.parameters, strict=True):
        assert spec["meaning"] == parameter.meaning
        assert spec["unit"] == parameter.unit
        assert spec["role"] == parameter.role
        assert spec["scattering"] == list(parameter.scattering)
        assert spec["value_range"] == asdict(parameter.value_range)
        assert spec["display_range"] == asdict(display_range(parameter))
        assert spec["core_range"] == asdict(core_range(parameter))
        assert spec["display_scale"] == parameter.display_scale
        assert spec["fit_scale"] == parameter.fit_scale
        assert spec["bounds_editable"] == parameter.bounds_editable
        if parameter.fit_bounds is None:
            assert "fit_bounds" not in spec
        else:
            assert spec["fit_bounds"] == asdict(parameter.fit_bounds)


def test_explanation_for_developers_does_not_reach_clients(response: Any) -> None:
    assert '"explanation"' not in response.text
    assert "fails on the desktop" not in response.text


def test_clients_must_revalidate(response: Any) -> None:
    assert response.headers["cache-control"] == "no-cache"
    assert re.fullmatch(r'"[0-9a-f]{32}"', response.headers["etag"])


@pytest.mark.parametrize("header", ["{etag}", 'W/{etag}, "other"', "*"])
def test_unchanged_descriptions_answer_304(response: Any, header: str) -> None:
    etag = response.headers["etag"]

    answer = TestClient(create_app()).get(
        "/api/models", headers={"If-None-Match": header.format(etag=etag)}
    )

    assert answer.status_code == 304
    assert answer.content == b""
    assert answer.headers["etag"] == etag
    assert answer.headers["cache-control"] == "no-cache"


def test_changed_descriptions_answer_in_full() -> None:
    answer = TestClient(create_app()).get("/api/models", headers={"If-None-Match": '"old"'})

    assert answer.status_code == 200
    assert answer.json()["models"]


def test_values_that_the_real_models_share_are_not_assumed() -> None:
    """All real modes have the same temperatures and degeneracies, so these use other values."""
    made_up = _made_up_description()
    fit_mode = replace(
        made_up.fit_modes[0],
        iterative=True,
        threshold=0.25,
        max_iterations=7,
        degeneracy=Degeneracy(2, 3),
    )

    [model] = build_models_response([replace(made_up, fit_modes=(fit_mode,))]).models

    assert model.default_min_temperature_k == 10
    assert model.default_max_temperature_k == 20
    assert model.default_curve_points == 5
    [mode] = model.fit_modes
    assert mode.threshold == 0.25
    assert mode.max_iterations == 7
    assert mode.degeneracy is not None
    assert (mode.degeneracy.band_1_default, mode.degeneracy.band_2_default) == (2, 3)


class _FakeModel:
    def __init__(self, description: ModelDescription) -> None:
        self._description = description

    def describe(self) -> ModelDescription:
        return self._description

    def band_diagram(self, request: BandDiagramRequest) -> BandDiagramResult:
        raise NotImplementedError

    def calculate(self, request: CurveRequest) -> CurveResult:
        raise NotImplementedError

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        raise NotImplementedError


def test_route_serves_a_model_registered_with_no_change_in_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = ModelRegistry()
    local.register(_FakeModel(_made_up_description()))
    monkeypatch.setattr("seeband_api.models.registry", local)
    _registry_response.cache_clear()
    try:
        body = TestClient(create_app()).get("/api/models").json()
    finally:
        _registry_response.cache_clear()

    assert [model["id"] for model in body["models"]] == ["test"]
    assert body["models"][0]["fit_modes"][0]["disabled_by"] == ["made_up"]


def test_response_matches_the_contract_snapshot(response: Any) -> None:
    """A change to a description shows in the diff of `openapi.json`, and needs regenerating."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    media = contract["paths"]["/api/models"]["get"]["responses"]["200"]["content"]

    assert response.json() == media["application/json"]["examples"]["registry"]["value"]


def _made_up_description() -> ModelDescription:
    issue = KnownIssue(
        id="made_up", severity="disabled", fixed_by="#1", fit_modes=("m",), explanation="Test"
    )
    spec = ParameterSpec(
        name="p",
        meaning="A test parameter",
        unit="K",
        role="fitted",
        scattering=(),
        value_range=ValueRange(0, 200, 1, 100),
        display_scale=1,
        fit_scale=0.01,
        calc_scale=1,
        fit_bounds=Bounds(0.0, 2.0),
    )
    return ModelDescription(
        id="test",
        name="Test model",
        fit_modes=(
            FitMode(id="m", quantities=("seebeck",), parameters=(spec,), known_issues=(issue,)),
        ),
        default_min_temperature_k=10,
        default_max_temperature_k=20,
        default_curve_points=5,
    )


def test_stages_say_what_each_solver_run_finds(modes: dict[str, dict[str, Any]]) -> None:
    rh = modes["dpb_s_rho_rh"]["stages"]
    assert [(stage["quantity"], stage["repeats"]) for stage in rh] == [
        ("seebeck", True),
        ("resistivity", True),
        ("hall", False),
    ]
    assert rh[2]["parameters"] == ["m1"]
    assert modes["spb_s_rho"]["stages"][1] == {
        "quantity": "resistivity",
        "parameters": ["A", "C", "F"],
        "repeats": False,
    }


def test_energies_are_shown_in_ev(response: Any, modes: dict[str, dict[str, Any]]) -> None:
    assert response.json()["energy_display"] == {
        "unit": "eV",
        "per_kelvin": pytest.approx(8.617333262e-5),
    }
    gap = next(p for p in modes["dpb_s_rho"]["parameters"] if p["name"] == "band_gap")
    assert (gap["unit"], gap["display_unit"]) == ("K", "eV")
    assert gap["display_factor"] == pytest.approx(8.617333262e-5)
    assert gap["display_range"]["step"] == 0.01
    assert gap["display_range"]["maximum"] == pytest.approx(3000 * 8.617333262e-5)
    # Its core range, which requests use, stays in K.
    assert gap["core_range"]["maximum"] == 3000.0
    ratio = next(p for p in modes["dpb_s_rho"]["parameters"] if p["name"] == "m_eff")
    assert (ratio["display_unit"], ratio["display_factor"]) == ("dimensionless", 1.0)
