"""What runs in a worker process for `POST /api/parse`. It holds no state between calls."""

from collections.abc import Mapping
from dataclasses import dataclass

from seeband_core.data_parser import ParsedTable, Role, Unit, parse_table, with_mapping
from seeband_core.interpolation import InterpolatedData, interpolate
from seeband_core.model_interface import Quantity


class UnknownColumn(Exception):
    """A mapping names a column that the text does not have."""


@dataclass(frozen=True)
class FitRange:
    min_temperature_k: float
    max_temperature_k: float


@dataclass(frozen=True, eq=False)
class ParseOutcome:
    """`failure_types` holds the exception types behind `interpolation_failed`, for the log."""

    table: ParsedTable
    interpolated: Mapping[Quantity, InterpolatedData]
    interpolation_failed: tuple[Quantity, ...]
    failure_types: tuple[str, ...] = ()


def _read(
    text: str,
    expected: Quantity | None,
    mapping: Mapping[int, Role] | None,
    units: Mapping[int, Unit] | None,
) -> ParsedTable:
    """Reads the text, and applies a user's mapping and units even if some rows have errors.

    `parse_table` keeps its suggestion when there are errors, and a user fixing columns needs their
    choice kept. With no readable rows, there are no columns to check it against, so it is ignored.
    """
    table = parse_table(text, expected)
    if mapping is None or not table.columns:
        return table
    try:
        return with_mapping(table, mapping, units)
    except ValueError as error:
        raise UnknownColumn from error


def parse(
    text: str,
    expected: Quantity | None,
    mapping: Mapping[int, Role] | None,
    fit_range: FitRange | None,
    units: Mapping[int, Unit] | None = None,
) -> ParseOutcome:
    """Reads the text, and interpolates each quantity over a fit range, if one is given.

    One quantity failing leaves the others, as a fit may not use it.
    """
    table = _read(text, expected, mapping, units)
    interpolated: dict[Quantity, InterpolatedData] = {}
    failed: list[Quantity] = []
    failure_types: list[str] = []
    if fit_range is not None:
        for quantity, measurement in table.measurements.items():
            try:
                interpolated[quantity] = interpolate(
                    measurement, fit_range.min_temperature_k, fit_range.max_temperature_k
                )
            except (ArithmeticError, ValueError) as error:
                failed.append(quantity)
                failure_types.append(type(error).__name__)
    return ParseOutcome(table, interpolated, tuple(failed), tuple(failure_types))
