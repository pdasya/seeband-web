"""`GET /api/models`: what clients build their forms from, generated from the model registry.

Fields that do not apply are left out of the response, rather than sent as null. FastAPI drops null
from examples in the contract, so this way the mock's example equals the real response.
"""

from collections.abc import Iterable
from functools import cache
from typing import Any

from fastapi import Response
from pydantic import BaseModel
from seeband_core.known_issues import disabled_issue_ids
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    CurveKind,
    FitMode,
    IssueCondition,
    IssueSeverity,
    KnownIssue,
    ModelDescription,
    ParameterRole,
    ParameterSpec,
    Quantity,
    ValueRange,
)
from seeband_core.model_scales import default_start_value, display_range

from seeband_api.routing import api_router

# Descriptions change only with a release, so an hour limits how long a client can hold old ones.
CACHE_CONTROL = "public, max-age=3600"

router = api_router("models")


class ValueRangeResponse(BaseModel):
    minimum: float
    maximum: float
    step: float
    default: float


class BoundsResponse(BaseModel):
    lower: float
    upper: float


class ParameterResponse(BaseModel):
    """One parameter of a fit mode.

    `value_range` is in control units, and `display_range` is the same range as a user sees it.
    `display_scale` converts control units to displayed values, and `fit_scale` to core units.
    `unit` is the unit of the displayed value. `fit_bounds` is in core units, and is left out for a
    parameter that a fit does not change. `meaning` is English text, for a client to fall back on.
    """

    name: str
    meaning: str
    unit: str
    role: ParameterRole
    scattering: list[str]
    value_range: ValueRangeResponse
    display_range: ValueRangeResponse
    display_scale: float
    fit_scale: float
    default_core_value: float
    fit_bounds: BoundsResponse | None = None
    bounds_editable: bool


class DegeneracyResponse(BaseModel):
    band_1_default: float
    band_2_default: float


class KnownIssueResponse(BaseModel):
    """A known error of the calculations in this mode.

    Clients show `message_key` through i18n. `explanation` is English text for developers. Empty
    `scattering` means every type, and empty `columns` every curve of a kind. `condition`, if
    present, limits the issue to some inputs. `fixed_by` is the issue in this repository that
    removes it.
    """

    id: str
    severity: IssueSeverity
    message_key: str
    explanation: str
    fixed_by: str
    scattering: list[str]
    curve_kinds: list[CurveKind]
    columns: list[str]
    affects_fit: bool
    condition: IssueCondition | None = None


class FitModeResponse(BaseModel):
    """One way of fitting a model.

    A client must not offer a mode with `disabled`. `disabled_by` names the `known_issues` that say
    why. `iterative` tells whether an iteration count means anything, and `threshold` and
    `max_iterations` apply only to an iterative mode. `scattering` is empty when a mode has no
    choice of scattering.
    """

    id: str
    quantities: list[Quantity]
    parameters: list[ParameterResponse]
    scattering: list[str]
    default_scattering: str | None = None
    iterative: bool
    threshold: float | None = None
    max_iterations: int | None = None
    degeneracy: DegeneracyResponse | None = None
    curve_kinds: list[CurveKind]
    disabled: bool
    disabled_by: list[str]
    known_issues: list[KnownIssueResponse]


class ModelResponse(BaseModel):
    """A model. `name` is English text, for a client to fall back on."""

    id: str
    name: str
    default_min_temperature_k: float
    default_max_temperature_k: float
    default_curve_points: int
    fit_modes: list[FitModeResponse]


class ModelsResponse(BaseModel):
    models: list[ModelResponse]


def _value_range(limits: ValueRange) -> ValueRangeResponse:
    return ValueRangeResponse(
        minimum=limits.minimum, maximum=limits.maximum, step=limits.step, default=limits.default
    )


def _parameter(spec: ParameterSpec) -> ParameterResponse:
    # `calc_scale` stays out: it only reproduces a desktop path, which clients must not use.
    bounds = spec.fit_bounds
    return ParameterResponse(
        name=spec.name,
        meaning=spec.meaning,
        unit=spec.unit,
        role=spec.role,
        scattering=list(spec.scattering),
        value_range=_value_range(spec.value_range),
        display_range=_value_range(display_range(spec)),
        display_scale=spec.display_scale,
        fit_scale=spec.fit_scale,
        default_core_value=default_start_value(spec),
        fit_bounds=BoundsResponse(lower=bounds.lower, upper=bounds.upper) if bounds else None,
        bounds_editable=spec.bounds_editable,
    )


def _known_issue(issue: KnownIssue) -> KnownIssueResponse:
    return KnownIssueResponse(
        id=issue.id,
        severity=issue.severity,
        message_key=issue.message_key,
        explanation=issue.explanation,
        fixed_by=issue.fixed_by,
        scattering=list(issue.scattering),
        curve_kinds=list(issue.curve_kinds),
        columns=list(issue.columns),
        affects_fit=issue.affects_fit,
        condition=issue.condition,
    )


def _fit_mode(fit_mode: FitMode) -> FitModeResponse:
    degeneracy = fit_mode.degeneracy
    return FitModeResponse(
        id=fit_mode.id,
        quantities=list(fit_mode.quantities),
        parameters=[_parameter(spec) for spec in fit_mode.parameters],
        scattering=list(fit_mode.scattering),
        default_scattering=fit_mode.default_scattering,
        iterative=fit_mode.iterative,
        threshold=fit_mode.threshold,
        max_iterations=fit_mode.max_iterations,
        degeneracy=(
            DegeneracyResponse(
                band_1_default=degeneracy.band_1_default,
                band_2_default=degeneracy.band_2_default,
            )
            if degeneracy
            else None
        ),
        curve_kinds=list(fit_mode.curve_kinds),
        disabled=fit_mode.disabled,
        disabled_by=list(disabled_issue_ids(fit_mode)),
        known_issues=[_known_issue(issue) for issue in fit_mode.known_issues],
    )


def build_models_response(descriptions: Iterable[ModelDescription]) -> ModelsResponse:
    return ModelsResponse(
        models=[
            ModelResponse(
                id=description.id,
                name=description.name,
                default_min_temperature_k=description.default_min_temperature_k,
                default_max_temperature_k=description.default_max_temperature_k,
                default_curve_points=description.default_curve_points,
                fit_modes=[_fit_mode(fit_mode) for fit_mode in description.fit_modes],
            )
            for description in descriptions
        ]
    )


@cache
def _registry_response() -> ModelsResponse:
    return build_models_response(registry.descriptions())


def _registry_example() -> dict[str, Any]:
    """The real descriptions, so that the mock can drive a client's forms."""
    return _registry_response().model_dump(mode="json", exclude_none=True)


@router.get(
    "/models",
    response_model_exclude_none=True,
    responses={
        200: {
            "content": {
                "application/json": {"examples": {"registry": {"value": _registry_example()}}}
            }
        }
    },
)
async def get_models(response: Response) -> ModelsResponse:
    response.headers["Cache-Control"] = CACHE_CONTROL
    return _registry_response()
