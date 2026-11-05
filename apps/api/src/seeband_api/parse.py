"""`POST /api/parse`: read measured data from text, and optionally interpolate it.

The body is JSON holding the text, not a file upload. A multipart parser writes a large upload to a
temporary file, and measurements must not reach the disk. So nothing outlives the request.
"""

from http import HTTPStatus
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core.data_parser import ParseIssue, Role
from seeband_core.interpolation import InterpolatedData, interpolation_grid_k
from seeband_core.model_interface import Measurement, Quantity

from seeband_api.calc_pool import CalcPoolDep
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.json_values import finite_or_none
from seeband_api.parse_worker import FitRange, ParseOutcome, UnknownColumn, parse
from seeband_api.routing import api_router

router = api_router("parse")

# About 50000 rows, which takes about 0.2 s. The example files are under 2 KB.
MAX_TEXT_CHARACTERS = 2_000_000
PREVIEW_ROWS = 10
# The core limits errors. Warnings can have one per line of text before a table.
MAX_WARNINGS = 100

PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]


class ColumnRole(BaseModel):
    """What a column holds. Columns count from 0."""

    column: Annotated[int, Field(ge=0, strict=True)]
    role: Role


class InterpolationRange(BaseModel):
    min_temperature_k: PositiveFloat
    max_temperature_k: PositiveFloat

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        if self.min_temperature_k >= self.max_temperature_k:
            raise ValueError("min_temperature_k must be below max_temperature_k")
        return self


class ParseRequest(BaseModel):
    """A text to read, as the client read it from a file or table.

    `expected` names the quantity of a file meant to hold one. `mapping` replaces the suggested
    columns with a user's choice, and the text is sent again each time, as the API keeps nothing.
    `interpolate` asks for each quantity on a grid over this fit range.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "T (K)\tS (V/K)\n300\t1.0e-4\n100\t2.0e-5\n200\t6.0e-5\n",
                    "expected": "seebeck",
                }
            ]
        }
    )

    text: Annotated[str, Field(max_length=MAX_TEXT_CHARACTERS)]
    expected: Quantity | None = None
    mapping: list[ColumnRole] | None = None
    interpolate: InterpolationRange | None = None

    @model_validator(mode="after")
    def _columns_are_distinct(self) -> Self:
        columns = [item.column for item in self.mapping or ()]
        if len(set(columns)) != len(columns):
            raise ValueError("A mapping names each column once")
        return self


class IssueResponse(BaseModel):
    """A problem in the data, as a code a client translates, in `input-data.md` of the core.

    `line` counts every line of the text from 1, and `column` from 0.
    """

    code: str
    line: int | None = None
    column: int | None = None


class MeasurementResponse(BaseModel):
    """Measured data sorted by temperature, in V/K, ohm m or m^3/C, and its size and range."""

    temperature_k: list[float]
    values: list[float]
    points: int
    min_temperature_k: float
    max_temperature_k: float


class InterpolatedResponse(BaseModel):
    """A quantity on the interpolation grid. `null` marks a value that is not finite.

    `extrapolated` means that some of the grid lies outside the data, so those values are made up,
    and a fit from them should say so through `extrapolated` in its request.
    `measured_points_in_range` of 0 means that all the values are made up. `underdetermined` means
    that the data do not set the polynomial.
    """

    temperature_k: list[float]
    values: list[float | None]
    extrapolated: bool
    measured_points_in_range: int
    underdetermined: bool


class ParseResponse(BaseModel):
    """What the text holds. A file with problems is still a 200, with a preview and its `errors`.

    `measurements` is empty with any `errors`. `headers` is left out when no header matches the
    columns. `preview` holds the first rows that could be read, in the order of the text, and
    `row_count` all of them. `mapping` is the suggestion or the user's choice. `warnings` holds at
    most 100, and `warnings_omitted` counts the rest. `interpolation_failed` names quantities that
    could not be interpolated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "headers": ["T (K)", "S (V/K)"],
                    "column_count": 2,
                    "row_count": 3,
                    "preview": [[300.0, 1.0e-4], [100.0, 2.0e-5], [200.0, 6.0e-5]],
                    "mapping": [
                        {"column": 0, "role": "temperature"},
                        {"column": 1, "role": "seebeck"},
                    ],
                    "measurements": {
                        "seebeck": {
                            "temperature_k": [100.0, 200.0, 300.0],
                            "values": [2.0e-5, 6.0e-5, 1.0e-4],
                            "points": 3,
                            "min_temperature_k": 100.0,
                            "max_temperature_k": 300.0,
                        }
                    },
                    "errors": [],
                    "warnings": [
                        {"code": "few_rows"},
                        {"code": "unsorted_temperature", "column": 0},
                    ],
                    "warnings_omitted": 0,
                    "interpolated": {},
                    "interpolation_failed": [],
                }
            ]
        }
    )

    headers: list[str] | None = None
    column_count: int
    row_count: int
    preview: list[list[float]]
    mapping: list[ColumnRole]
    measurements: dict[Quantity, MeasurementResponse]
    errors: list[IssueResponse]
    warnings: list[IssueResponse]
    warnings_omitted: int
    interpolated: dict[Quantity, InterpolatedResponse]
    interpolation_failed: list[Quantity]


def _refuse(code: str, message: str, location: list[str | int]) -> ApiError:
    detail = ErrorDetail(location=["body", *location], code=code, message=message)
    return ApiError(
        HTTPStatus.UNPROCESSABLE_CONTENT, "invalid_parse_request", "Invalid request", [detail]
    )


def _issue(issue: ParseIssue) -> IssueResponse:
    return IssueResponse(code=issue.code, line=issue.line, column=issue.column)


def _measurement(measurement: Measurement) -> MeasurementResponse:
    temperature_k = measurement.temperature_k
    return MeasurementResponse(
        temperature_k=temperature_k.tolist(),
        values=measurement.values.tolist(),
        points=temperature_k.size,
        min_temperature_k=float(temperature_k.min()),
        max_temperature_k=float(temperature_k.max()),
    )


def _interpolated(data: InterpolatedData) -> InterpolatedResponse:
    return InterpolatedResponse(
        temperature_k=data.measurement.temperature_k.tolist(),
        values=finite_or_none(data.measurement.values),
        extrapolated=data.extrapolated,
        measured_points_in_range=data.measured_points_in_range,
        underdetermined=data.underdetermined,
    )


def _to_response(outcome: ParseOutcome) -> ParseResponse:
    table = outcome.table
    columns = table.columns
    row_count = len(table.lines)
    return ParseResponse(
        headers=list(table.headers) if table.headers is not None else None,
        column_count=len(columns),
        row_count=row_count,
        preview=[
            [float(column[row]) for column in columns]
            for row in range(min(row_count, PREVIEW_ROWS))
        ],
        mapping=[ColumnRole(column=column, role=role) for column, role in table.mapping.items()],
        measurements={
            quantity: _measurement(measurement)
            for quantity, measurement in table.measurements.items()
        },
        errors=[_issue(issue) for issue in table.errors],
        warnings=[_issue(issue) for issue in table.warnings[:MAX_WARNINGS]],
        warnings_omitted=max(len(table.warnings) - MAX_WARNINGS, 0),
        interpolated={
            quantity: _interpolated(data) for quantity, data in outcome.interpolated.items()
        },
        interpolation_failed=list(outcome.interpolation_failed),
    )


@router.post("/parse", response_model_exclude_none=True)
async def post_parse(body: ParseRequest, pool: CalcPoolDep) -> ParseResponse:
    fit_range = None
    if body.interpolate is not None:
        fit_range = FitRange(body.interpolate.min_temperature_k, body.interpolate.max_temperature_k)
        try:
            interpolation_grid_k(fit_range.min_temperature_k, fit_range.max_temperature_k)
        except ValueError as error:
            # The core's text here is fixed, and quotes no values.
            raise _refuse("invalid_interpolation_range", str(error), ["interpolate"]) from None
    mapping = None
    if body.mapping is not None:
        mapping = {item.column: item.role for item in body.mapping}
    try:
        outcome = await pool.run(parse, body.text, body.expected, mapping, fit_range)
    except UnknownColumn:
        raise _refuse("unknown_column", "The text has no such column", ["mapping"]) from None
    return _to_response(outcome)
