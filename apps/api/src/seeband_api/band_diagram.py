"""`POST /api/band-diagram`: the sketch of E(k) for given parameters. It keeps no state."""

import math

from pydantic import BaseModel, ConfigDict
from seeband_core.model_catalog import registry
from seeband_core.model_interface import BandDiagramRequest as CoreRequest

from seeband_api.errors import ApiError
from seeband_api.json_values import finite_or_none
from seeband_api.request_checks import (
    FiniteFloat,
    PositiveFloat,
    check_degeneracy,
    check_parameter_names,
    find_mode,
    invalid,
)
from seeband_api.routing import api_router, too_many_requests

router = api_router("band-diagram")

ERROR_CODE = "invalid_band_diagram"
ERROR_MESSAGE = "Invalid band diagram"


class BandDiagramRequest(BaseModel):
    """What to draw. `parameters` holds every parameter of the mode in core units, as in a curve."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "model": "spb",
                    "fit_mode": "spb_s",
                    "parameters": {"band_mass": 1.01, "fermi_energy": 100.0},
                }
            ]
        }
    )

    model: str
    fit_mode: str
    parameters: dict[str, FiniteFloat]
    band_1_degeneracy: PositiveFloat = 1.0
    band_2_degeneracy: PositiveFloat = 1.0


class BandDiagramResponse(BaseModel):
    """Curves over `wavevector`, by name, where null marks a value that is not finite.

    Each name ends in its unit. `wavevector` has none, as the formula states none, and the desktop
    draws this axis with no ticks. `known_issues` names known errors, as in `GET /api/models`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "wavevector": [-40.0, 0.0, 40.0],
                    "curves": {
                        "band_1_energy_k": [1954.5, 0.0, 1954.5],
                        "fermi_energy_k": [100.0, 100.0, 100.0],
                    },
                    "known_issues": ["band_diagram_formula"],
                }
            ]
        }
    )

    wavevector: list[float]
    curves: dict[str, list[float | None]]
    known_issues: list[str]


@router.post("/band-diagram", responses={429: too_many_requests()})
def post_band_diagram(body: BandDiagramRequest) -> BandDiagramResponse:
    description, fit_mode = find_mode(body.model, body.fit_mode, ERROR_CODE, ERROR_MESSAGE)
    details = [
        *check_degeneracy(body.band_1_degeneracy, body.band_2_degeneracy, fit_mode),
        *check_parameter_names(list(body.parameters), "parameters", fit_mode),
    ]
    # The mass of band 2 takes this ratio, which a float holds only within its range.
    ratio = body.band_1_degeneracy / body.band_2_degeneracy
    if not (math.isfinite(ratio) and ratio > 0):
        details.append(
            invalid(
                "degeneracy_ratio_out_of_range",
                "N1 / N2 must be a finite number above 0",
                ["band_2_degeneracy"],
            )
        )
    if details:
        raise ApiError(422, ERROR_CODE, ERROR_MESSAGE, details)
    result = registry.get(description.id).band_diagram(
        CoreRequest(
            fit_mode=fit_mode.id,
            parameters=body.parameters,
            band_1_degeneracy=body.band_1_degeneracy,
            band_2_degeneracy=body.band_2_degeneracy,
        )
    )
    return BandDiagramResponse(
        wavevector=result.wavevector.tolist(),
        curves={name: finite_or_none(values) for name, values in result.curves.items()},
        known_issues=list(result.known_issues),
    )
