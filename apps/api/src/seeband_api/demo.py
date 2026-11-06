"""`GET /api/demo`: the synthetic dataset, for visitors without data.

It goes through the parser, so that it has the form and meaning of a user's parsed file, and a
client needs no second path for it.
"""

from functools import cache
from typing import Literal

from pydantic import BaseModel
from seeband_core.data_parser import parse_table
from seeband_core.demo_dataset import demo_table_text, load_demo_dataset

from seeband_api.parse import ParseResponse, to_parse_response
from seeband_api.parse_worker import ParseOutcome
from seeband_api.routing import api_router

router = api_router("demo")


class DemoNoise(BaseModel):
    """The noise added to the model's curves: V/K for S, and a relative size for rho and R_H."""

    seed: int
    seebeck_v_per_k: float
    resistivity_relative: float
    hall_relative: float


class DemoResponse(ParseResponse):
    """A parsed file, as from `POST /api/parse`, that is not a measurement of any material.

    A client must say so, by showing `message_key` through i18n wherever the data appear.
    `known_issues` names the errors of the model that the data carry. `model`, `fit_mode` and
    `scattering` say what generated them. `true_parameters` holds values of that model, in core
    units, and its other parameters were at the defaults of `GET /api/models`.
    """

    synthetic: Literal[True]
    message_key: str
    known_issues: list[str]
    model: str
    fit_mode: str
    scattering: str
    true_parameters: dict[str, float]
    noise: DemoNoise


@cache
def _demo_response() -> DemoResponse:
    dataset = load_demo_dataset()
    table = parse_table(demo_table_text(dataset))
    parsed = to_parse_response(ParseOutcome(table, {}, ()))
    return DemoResponse(
        **parsed.model_dump(),
        synthetic=dataset.synthetic,
        message_key=dataset.message_key,
        known_issues=list(dataset.known_issues),
        model=dataset.model,
        fit_mode=dataset.fit_mode,
        scattering=dataset.scattering,
        true_parameters=dict(dataset.true_parameters),
        noise=DemoNoise.model_validate(dict(dataset.noise)),
    )


@router.get(
    "/demo",
    response_model_exclude_none=True,
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "demo": {"value": _demo_response().model_dump(exclude_none=True)},
                    }
                }
            }
        }
    },
)
async def get_demo() -> DemoResponse:
    return _demo_response()
