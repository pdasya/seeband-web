import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_api.models import build_models_response
from seeband_core.model_interface import (
    Bounds,
    FitMode,
    KnownIssue,
    ModelDescription,
    ParameterSpec,
    ValueRange,
)

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
    assert "fails on the desktop" in reason["explanation"]


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


def test_scales_and_values_of_a_parameter_shown_at_another_scale(
    modes: dict[str, dict[str, Any]],
) -> None:
    # From seeband.py: C in SPB S + rho shows as slider / 100, and enters a fit as the slider value.
    spec = _parameter(modes["spb_s_rho"], "C")

    assert spec["display_scale"] == 0.01
    assert spec["fit_scale"] == 1
    assert spec["default_core_value"] == spec["value_range"]["default"]
    assert spec["display_range"]["default"] == spec["value_range"]["default"] / 100
    assert spec["display_range"]["maximum"] == spec["value_range"]["maximum"] / 100
    assert spec["role"] == "fitted"
    assert spec["scattering"] == ["acPhDis"]


def test_core_value_divides_as_the_desktop_does(modes: dict[str, dict[str, Any]]) -> None:
    spec = _parameter(modes["dpb_s"], "m_eff")

    assert spec["fit_scale"] == 0.01
    assert spec["default_core_value"] == spec["value_range"]["default"] / 100


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


def test_response_is_strict_json(response: Any) -> None:
    json.dumps(response.json(), allow_nan=False)


def test_response_can_be_cached(response: Any) -> None:
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_response_matches_the_contract_snapshot(response: Any) -> None:
    """A change to a description shows in the diff of `openapi.json`, and needs regenerating."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    media = contract["paths"]["/api/models"]["get"]["responses"]["200"]["content"]

    assert response.json() == media["application/json"]["examples"]["registry"]["value"]


def test_response_comes_from_the_descriptions_given() -> None:
    """A new model needs no change in the API."""
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
    description = ModelDescription(
        id="test",
        name="Test model",
        fit_modes=(
            FitMode(id="m", quantities=("seebeck",), parameters=(spec,), known_issues=(issue,)),
        ),
        default_min_temperature_k=10,
        default_max_temperature_k=20,
        default_curve_points=5,
    )

    [model] = build_models_response([description]).model_dump()["models"]

    assert model["id"] == "test"
    [mode] = model["fit_modes"]
    assert mode["disabled"] is True
    assert mode["disabled_by"] == ["made_up"]
    assert mode["parameters"][0]["default_core_value"] == 1.0
    assert mode["parameters"][0]["display_range"]["maximum"] == 200
