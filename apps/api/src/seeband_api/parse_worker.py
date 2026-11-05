"""What runs in a worker process for `POST /api/parse`. It holds no state between calls."""

from collections.abc import Mapping
from dataclasses import dataclass

from seeband_core.data_parser import ParsedTable, Role, parse_table
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
    table: ParsedTable
    interpolated: Mapping[Quantity, InterpolatedData]
    interpolation_failed: tuple[Quantity, ...]


def parse(
    text: str,
    expected: Quantity | None,
    mapping: Mapping[int, Role] | None,
    fit_range: FitRange | None,
) -> ParseOutcome:
    """Reads the text, and interpolates each quantity over a fit range, if one is given.

    One quantity failing leaves the others, as a fit may not use it.
    """
    try:
        table = parse_table(text, expected, mapping)
    except ValueError as error:
        # The route has checked the rest, so this comes from the columns of the text.
        raise UnknownColumn from error
    interpolated: dict[Quantity, InterpolatedData] = {}
    failed: list[Quantity] = []
    if fit_range is not None:
        for quantity, measurement in table.measurements.items():
            try:
                interpolated[quantity] = interpolate(
                    measurement, fit_range.min_temperature_k, fit_range.max_temperature_k
                )
            except (ArithmeticError, ValueError):
                failed.append(quantity)
    return ParseOutcome(table, interpolated, tuple(failed))
