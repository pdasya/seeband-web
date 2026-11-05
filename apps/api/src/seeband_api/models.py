"""`GET /api/models`: what clients build their forms from, generated from the model registry.

Fields that do not apply are left out of the response, rather than sent as null. FastAPI drops null
from examples in the contract, so this way the mock's example equals the real response.
"""

from collections.abc import Iterable
from functools import cache
from hashlib import sha256
from typing import Annotated, Any

from fastapi import Header, Response
from pydantic import BaseModel
from seeband_core.known_issues import disabled_issue_ids
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    ALL_CURVE_KINDS,
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
from seeband_core.model_scales import core_range, display_range

from seeband_api.routing import api_router

# Clients revalidate, as a client holding old descriptions could offer a mode that is now disabled.
CACHE_CONTROL = "no-cache"

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

    `display_range` is the control's range as a user sees it, and `core_range` is the same range in
    the core units of requests and results. Use these two, and do not calculate core values from the
    scales: `display_scale` and `fit_scale`, from control units in `value_range`, are there for
    information, as the desktop divides where a multiplication would change the last bit.

    In each range, `step` is the desktop's keyboard increment, not a grid: values between steps are
    valid, and the default or maximum need not lie on a step.

    `scattering` lists the types the parameter applies to, and empty means all of them. A mode with
    no choice of scattering uses all its parameters, whatever they list. A `fixed` parameter is set
    by the user, and a fit does not change it. Requests hold every parameter of a mode, including
    those of other scattering types.

    `unit` is the unit of the displayed value, and can be `dimensionless` or `unknown`. `fit_bounds`
    is in core units, and is left out for a parameter that a fit does not change. `meaning` is
    English text, for a client with no translation.
    """

    name: str
    meaning: str
    unit: str
    role: ParameterRole
    scattering: list[str]
    value_range: ValueRangeResponse
    display_range: ValueRangeResponse
    core_range: ValueRangeResponse
    display_scale: float
    fit_scale: float
    fit_bounds: BoundsResponse | None = None
    bounds_editable: bool


class DegeneracyResponse(BaseModel):
    band_1_default: float
    band_2_default: float


class KnownIssueResponse(BaseModel):
    """A known error of the calculations in this mode. Clients show `message_key` through i18n.

    Empty `scattering` means every type. `curve_kinds` lists the curves it applies to, and empty
    means none. Empty `columns` means every curve of those kinds. `condition`, if present, limits it
    to some inputs. `fixed_by` is the issue in this repository that removes it.
    """

    id: str
    severity: IssueSeverity
    message_key: str
    fixed_by: str
    scattering: list[str]
    curve_kinds: list[CurveKind]
    columns: list[str]
    affects_fit: bool
    condition: IssueCondition | None = None


class CurveAvailabilityResponse(BaseModel):
    """Whether a mode offers a kind of curve for `POST /api/calc`.

    `reason` is a code for one it does not offer, and a client shows `curve_unavailable.<reason>`
    through i18n. `relative` means that the size of the curve rests on an assumed value, not on
    data: carrier concentrations with no Hall data use m1 = 1.
    """

    kind: CurveKind
    available: bool
    reason: str | None = None
    relative: bool


class FitModeResponse(BaseModel):
    """One way of fitting a model.

    A client must not offer a mode with `disabled`. `disabled_by` names the `known_issues` that say
    why. `iterative` tells whether an iteration count means anything. `threshold`, a relative
    change, and `max_iterations` are what an iterative fit uses, and a request cannot change them.
    `scattering` is empty when a mode has no choice of scattering.
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
    curves: list[CurveAvailabilityResponse]
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
        core_range=_value_range(core_range(spec)),
        display_scale=spec.display_scale,
        fit_scale=spec.fit_scale,
        fit_bounds=BoundsResponse(lower=bounds.lower, upper=bounds.upper) if bounds else None,
        bounds_editable=spec.bounds_editable,
    )


def _known_issue(issue: KnownIssue) -> KnownIssueResponse:
    return KnownIssueResponse(
        id=issue.id,
        severity=issue.severity,
        message_key=issue.message_key,
        fixed_by=issue.fixed_by,
        scattering=list(issue.scattering),
        curve_kinds=list(issue.curve_kinds),
        columns=list(issue.columns),
        affects_fit=issue.affects_fit,
        condition=issue.condition,
    )


def _curve_availability(fit_mode: FitMode, kind: CurveKind) -> CurveAvailabilityResponse:
    reason = fit_mode.unavailable_reason(kind)
    return CurveAvailabilityResponse(
        kind=kind,
        available=reason is None,
        reason=reason,
        relative=kind in fit_mode.relative_curve_kinds,
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
        curves=[_curve_availability(fit_mode, kind) for kind in ALL_CURVE_KINDS],
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


def _registry_etag() -> str:
    body = _registry_response().model_dump_json(exclude_none=True)
    return f'"{sha256(body.encode()).hexdigest()[:32]}"'


def _registry_example() -> dict[str, Any]:
    """The real descriptions, so that the mock can drive a client's forms."""
    return _registry_response().model_dump(mode="json", exclude_none=True)


@router.get(
    "/models",
    response_model=ModelsResponse,
    response_model_exclude_none=True,
    responses={
        200: {
            "headers": {
                "Cache-Control": {"schema": {"type": "string"}, "example": CACHE_CONTROL},
                "ETag": {"schema": {"type": "string"}, "example": _registry_etag()},
            },
            "content": {
                "application/json": {"examples": {"registry": {"value": _registry_example()}}}
            },
        },
        304: {"description": "The descriptions have not changed since the given `If-None-Match`"},
    },
)
async def get_models(
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> ModelsResponse | Response:
    etag = _registry_etag()
    headers = {"Cache-Control": CACHE_CONTROL, "ETag": etag}
    if if_none_match is not None and (if_none_match.strip() == "*" or etag in if_none_match):
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return _registry_response()
