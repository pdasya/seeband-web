"""`POST /api/parse`: read measured data from text, and optionally interpolate it.

The body is JSON holding the text, not a file upload. A multipart parser writes a large upload to a
temporary file, and measurements must not reach the disk. So nothing outlives the request.
"""

from http import HTTPStatus
from typing import Annotated, Any, Self

from pydantic import BaseModel, Field, model_validator
from seeband_core.data_parser import (
    IssueCode,
    LoadedQuantity,
    ParsedTable,
    ParseIssue,
    Role,
    Unit,
    si_column,
)
from seeband_core.interpolation import (
    InterpolatedData,
    InterpolationFailure,
    interpolation_grid_k,
)
from seeband_core.model_interface import Measurement, Quantity

from seeband_api.calc_pool import CalcPoolDep
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.json_values import finite_or_none
from seeband_api.parse_worker import FitRange, ParseOutcome, UnknownColumn, parse
from seeband_api.request_checks import MaxPointsDep
from seeband_api.request_logging import log_calculation_failure
from seeband_api.routing import api_router, too_many_requests

router = api_router("parse")

# About 50000 rows of 40 characters, which take about 0.2 s, or 500000 very short rows, about 1.4 s.
# The example files are under 2 KB.
MAX_TEXT_CHARACTERS = 2_000_000
PREVIEW_ROWS = 10
# The core gives a warning per line of text before a table, and limits the other kinds.
MAX_PREAMBLE_WARNINGS = 100

PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]


class ColumnRole(BaseModel):
    """What a column holds, and the unit its values are written in. Columns count from 0.

    In a request, `unit` is a user's choice, and without it the column's header unit, or SI,
    applies. In an answer it is the unit the column was read in. `input-data.md` of the core lists
    the units of each quantity.
    """

    column: Annotated[int, Field(ge=0, strict=True)]
    role: Role
    unit: Unit | None = None


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

    `expected` names the quantity of a file meant to hold one, and `conductivity` reads its values
    as sigma, which comes back as the resistivity 1/sigma. `mapping` replaces the suggested columns
    with a user's choice, and the text is sent again each time, as the API keeps nothing.
    `interpolate` asks for each quantity on a grid within this range and its measured range.
    """

    text: Annotated[str, Field(max_length=MAX_TEXT_CHARACTERS)]
    expected: LoadedQuantity | None = None
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

    code: IssueCode
    line: int | None = None
    column: int | None = None


class MeasurementResponse(BaseModel):
    """Measured data sorted by temperature, in V/K, ohm m or m^3/C, and its size and range.

    `loaded_as` is what the text held: the quantity itself, or `conductivity` for a resistivity
    that the core computed as 1/sigma from a column of sigma. Its interpolation, fits and RMSE all
    use that resistivity.
    """

    temperature_k: list[float]
    values: list[float]
    points: int
    min_temperature_k: float
    max_temperature_k: float
    loaded_as: LoadedQuantity


class InterpolatedResponse(BaseModel):
    """A quantity on the interpolation grid. `null` marks a value that is not finite.

    `range_limited` means the requested range extends beyond this quantity's measured range.
    `extrapolated` is retained for compatibility and is false for new server results.
    `measured_points_in_range` counts source points in the requested range; zero can occur between
    sparse measurements. `underdetermined` means that the data do not set the polynomial.
    """

    temperature_k: list[float]
    values: list[float | None]
    extrapolated: bool
    range_limited: bool
    measured_points_in_range: int
    underdetermined: bool


class ParseResponse(BaseModel):
    """What the text holds. A file with problems is still a 200, with a preview and its `errors`.

    `measurements` is empty with any `errors`. `headers` is left out when no header matches the
    columns. `column_count` is 0 when neither a row nor a header sets it. `preview` holds the first
    rows that could be read, in the order of the text and as written, and `row_count` all of them.
    `preview_si` holds the same rows in SI, with `null` for a column with no role or no unit:
    with `errors`, only a unit the request chose is kept. `mapping` is the
    suggestion or the user's choice, and with no readable rows, always the suggestion. `warnings`
    holds every kind, with at most 100 `preamble_skipped`, and `warnings_omitted` counts the rest.
    `interpolation_failed` names quantities that could not be interpolated, and
    `interpolation_failure_reasons` says why for each: `no_overlap` (the fit range and the measured
    range do not overlap), `overlap_too_short` (under 20 K, or under 40 K where the data narrow the
    range, which would give one grid point) or `fit_failed` (the polynomial could not be fitted).
    """

    headers: list[str] | None = None
    column_count: int
    row_count: int
    preview: list[list[float]]
    preview_si: list[list[float | None]]
    mapping: list[ColumnRole]
    measurements: dict[Quantity, MeasurementResponse]
    errors: list[IssueResponse]
    warnings: list[IssueResponse]
    warnings_omitted: int
    interpolated: dict[Quantity, InterpolatedResponse]
    interpolation_failed: list[Quantity]
    interpolation_failure_reasons: dict[Quantity, InterpolationFailure]


def _refuse(code: str, message: str, location: list[str | int]) -> ApiError:
    detail = ErrorDetail(location=["body", *location], code=code, message=message)
    return ApiError(
        HTTPStatus.UNPROCESSABLE_CONTENT, "invalid_parse_request", "Invalid request", [detail]
    )


def _issue(issue: ParseIssue) -> IssueResponse:
    return IssueResponse(code=issue.code, line=issue.line, column=issue.column)


def _measurement(measurement: Measurement, loaded_as: LoadedQuantity) -> MeasurementResponse:
    temperature_k = measurement.temperature_k
    return MeasurementResponse(
        temperature_k=temperature_k.tolist(),
        values=measurement.values.tolist(),
        points=temperature_k.size,
        min_temperature_k=float(temperature_k.min()),
        max_temperature_k=float(temperature_k.max()),
        loaded_as=loaded_as,
    )


def _interpolated(data: InterpolatedData) -> InterpolatedResponse:
    return InterpolatedResponse(
        temperature_k=data.measurement.temperature_k.tolist(),
        values=finite_or_none(data.measurement.values),
        extrapolated=data.extrapolated,
        range_limited=data.range_limited,
        measured_points_in_range=data.measured_points_in_range,
        underdetermined=data.underdetermined,
    )


def _preview_si(table: ParsedTable, rows: int) -> list[list[float | None]]:
    """The first rows in SI, through the core, as only it holds the units."""
    converted: list[list[float] | None] = []
    for index in range(len(table.columns)):
        column = si_column(table, index, rows)
        converted.append(None if column is None else column.tolist())
    return [
        [None if values is None else values[row] for values in converted] for row in range(rows)
    ]


def to_parse_response(outcome: ParseOutcome) -> ParseResponse:
    table = outcome.table
    columns = table.columns
    row_count = len(table.lines)
    preview_rows = min(row_count, PREVIEW_ROWS)
    preamble = [issue for issue in table.warnings if issue.code == "preamble_skipped"]
    others = [issue for issue in table.warnings if issue.code != "preamble_skipped"]
    return ParseResponse(
        headers=list(table.headers) if table.headers is not None else None,
        column_count=table.column_count or len(table.headers or ()),
        row_count=row_count,
        preview=[[float(column[row]) for column in columns] for row in range(preview_rows)],
        preview_si=_preview_si(table, preview_rows),
        mapping=[
            ColumnRole(column=column, role=role, unit=table.units.get(column))
            for column, role in table.mapping.items()
        ],
        measurements={
            quantity: _measurement(measurement, table.loaded_as[quantity])
            for quantity, measurement in table.measurements.items()
        },
        errors=[_issue(issue) for issue in table.errors],
        warnings=[_issue(issue) for issue in (*others, *preamble[:MAX_PREAMBLE_WARNINGS])],
        warnings_omitted=max(len(preamble) - MAX_PREAMBLE_WARNINGS, 0),
        interpolated={
            quantity: _interpolated(data) for quantity, data in outcome.interpolated.items()
        },
        interpolation_failed=list(outcome.interpolation_failed),
        interpolation_failure_reasons=dict(outcome.failure_reasons),
    )


def _example(body: dict[str, Any]) -> dict[str, Any]:
    return {"value": body}


# The request for each example is in `PARSE_EXAMPLE_REQUESTS`, and a test compares them. The first
# is what the mock serves unless asked for another, with `Prefer: example=<name>`.
PARSE_EXAMPLE_REQUESTS: dict[str, dict[str, Any]] = {
    "clean": {
        "text": "T (K)\tS (V/K)\n300\t1.0e-4\n100\t2.0e-5\n200\t6.0e-5\n",
        "expected": "seebeck",
    },
    "with_errors": {"text": "T S\n100 1.0e-6\n200 x\n", "expected": "seebeck"},
    "interpolated": {
        "text": "T S\n100 1.0e-6\n130 2.0e-6\n160 3.0e-6\n",
        "interpolate": {"min_temperature_k": 100.0, "max_temperature_k": 160.0},
    },
}
_NO_INTERPOLATION: dict[str, Any] = {
    "interpolated": {},
    "interpolation_failed": [],
    "interpolation_failure_reasons": {},
}
_T_S_MAPPING = [
    {"column": 0, "role": "temperature", "unit": "K"},
    {"column": 1, "role": "seebeck", "unit": "V/K"},
]
PARSE_EXAMPLE_RESPONSES: dict[str, dict[str, Any]] = {
    "clean": {
        "headers": ["T (K)", "S (V/K)"],
        "column_count": 2,
        "row_count": 3,
        "preview": [[300.0, 1.0e-4], [100.0, 2.0e-5], [200.0, 6.0e-5]],
        "preview_si": [[300.0, 1.0e-4], [100.0, 2.0e-5], [200.0, 6.0e-5]],
        "mapping": _T_S_MAPPING,
        "measurements": {
            "seebeck": {
                "temperature_k": [100.0, 200.0, 300.0],
                "values": [2.0e-5, 6.0e-5, 1.0e-4],
                "points": 3,
                "min_temperature_k": 100.0,
                "max_temperature_k": 300.0,
                "loaded_as": "seebeck",
            }
        },
        "errors": [],
        "warnings": [{"code": "few_rows"}, {"code": "unsorted_temperature", "column": 0}],
        "warnings_omitted": 0,
        **_NO_INTERPOLATION,
    },
    "with_errors": {
        "headers": ["T", "S"],
        "column_count": 2,
        "row_count": 1,
        "preview": [[100.0, 1.0e-6]],
        "preview_si": [[None, None]],
        "mapping": [{"column": 0, "role": "temperature"}, {"column": 1, "role": "seebeck"}],
        "measurements": {},
        "errors": [{"code": "not_numeric", "line": 3, "column": 1}],
        "warnings": [],
        "warnings_omitted": 0,
        **_NO_INTERPOLATION,
    },
    "interpolated": {
        "headers": ["T", "S"],
        "column_count": 2,
        "row_count": 3,
        "preview": [[100.0, 1.0e-6], [130.0, 2.0e-6], [160.0, 3.0e-6]],
        "preview_si": [[100.0, 1.0e-6], [130.0, 2.0e-6], [160.0, 3.0e-6]],
        "mapping": _T_S_MAPPING,
        "measurements": {
            "seebeck": {
                "temperature_k": [100.0, 130.0, 160.0],
                "values": [1.0e-6, 2.0e-6, 3.0e-6],
                "points": 3,
                "min_temperature_k": 100.0,
                "max_temperature_k": 160.0,
                "loaded_as": "seebeck",
            }
        },
        "errors": [],
        "warnings": [{"code": "few_rows"}],
        "warnings_omitted": 0,
        "interpolated": {
            "seebeck": {
                "temperature_k": [100.0, 130.0, 160.0],
                "values": [1.0e-6, 2.0e-6, 3.0e-6],
                "extrapolated": False,
                "range_limited": False,
                "measured_points_in_range": 3,
                "underdetermined": True,
            }
        },
        "interpolation_failed": [],
        "interpolation_failure_reasons": {},
    },
}


@router.post(
    "/parse",
    response_model_exclude_none=True,
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        name: _example(body) for name, body in PARSE_EXAMPLE_RESPONSES.items()
                    }
                }
            }
        },
        429: too_many_requests(),
    },
)
async def post_parse(
    body: ParseRequest, pool: CalcPoolDep, max_points: MaxPointsDep
) -> ParseResponse:
    fit_range = None
    if body.interpolate is not None:
        fit_range = FitRange(body.interpolate.min_temperature_k, body.interpolate.max_temperature_k)
        try:
            interpolation_grid_k(fit_range.min_temperature_k, fit_range.max_temperature_k)
        except ValueError as error:
            # The core's text here is fixed, and quotes no values.
            raise _refuse("invalid_interpolation_range", str(error), ["interpolate"]) from None
    mapping = None
    units = None
    if body.mapping is not None:
        mapping = {item.column: item.role for item in body.mapping}
        units = {item.column: item.unit for item in body.mapping if item.unit is not None}
    try:
        outcome = await pool.run(parse, body.text, body.expected, mapping, fit_range, units)
    except UnknownColumn:
        raise _refuse("unknown_column", "The text has no such column", ["mapping"]) from None
    # Only reading the text can say how many rows it holds, and its size limits that work.
    if len(outcome.table.lines) > max_points:
        raise _refuse("too_many_rows", f"At most {max_points} rows", ["text"])
    for failure_type in outcome.failure_types:
        log_calculation_failure(failure_type)
    return to_parse_response(outcome)
