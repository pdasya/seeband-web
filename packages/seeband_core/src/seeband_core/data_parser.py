"""Read measured data from text, as the Conventions page describes.

Columns are separated by spaces, tabs or commas, and values are in the units of `QUANTITY_UNITS`.
Problems come back as codes with no text and no measured values, so that a client can translate
them and a log can hold them.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np

from seeband_core.model_interface import Measurement, Quantity

Role = Literal["temperature", "seebeck", "resistivity", "hall"]
IssueCode = Literal[
    "no_data",
    "too_few_columns",
    "wrong_column_count",
    "missing_value",
    "not_numeric",
    "not_finite",
    "decimal_comma",
    "too_few_rows",
    "missing_temperature",
    "non_positive_temperature",
    "repeated_role",
    "few_rows",
    "unit_not_checked",
    "unsorted_temperature",
    "duplicate_temperature",
]

MIN_ROWS = 2
# Below this, the degree 5 fit that chooses DPB start values is not determined.
FEW_ROWS = 6
_HEADER_NAMES: Mapping[str, Role] = {
    "t": "temperature",
    "t_k": "temperature",
    "temp": "temperature",
    "s": "seebeck",
    "seebeck": "seebeck",
    "rho": "resistivity",
    "ρ": "resistivity",
    "resistivity": "resistivity",
    "rh": "hall",
    "r_h": "hall",
    "hall": "hall",
}
_NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
_ANY_SEPARATOR = re.compile(r"\s*,\s*|\s+")
_STRONG_SEPARATOR = re.compile(r"\s*[,\t]\s*")
_DECIMAL_COMMA = re.compile(r"\d,\d")
_UNIT = re.compile(r"[(\[].*?[)\]]")


@dataclass(frozen=True)
class ParseIssue:
    """A problem in the data. `line` counts from 1 in the text, and `column` from 0."""

    code: IssueCode
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, eq=False)
class ParsedTable:
    """The columns of a text, and what they seem to hold.

    `mapping` is a suggestion from column to role, which a user can change with `to_measurements`.
    With any `errors`, `measurements` is empty and `columns` may be empty or incomplete.
    """

    headers: tuple[str, ...] | None
    columns: tuple[np.ndarray, ...]
    lines: tuple[int, ...]
    mapping: Mapping[int, Role]
    measurements: Mapping[Quantity, Measurement]
    errors: tuple[ParseIssue, ...]
    warnings: tuple[ParseIssue, ...]


def _split(line: str, strong_only: bool = False) -> list[str]:
    stripped = line.strip()
    if not strong_only:
        stripped = stripped.rstrip(",").rstrip()
    return (_STRONG_SEPARATOR if strong_only else _ANY_SEPARATOR).split(stripped)


def _data_lines(text: str) -> list[tuple[int, str]]:
    found = []
    for number, line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            found.append((number, stripped))
    return found


def _is_header(line: str) -> bool:
    return any(field and _NUMBER.fullmatch(field) is None for field in _split(line))


def _header_fields(line: str) -> list[str]:
    """Split a header. Tabs and commas win over spaces, so that `T (K)` stays one column."""
    if "," in line or "\t" in line:
        return _split(line, strong_only=True)
    # With only spaces, a unit in brackets stays with its name.
    return re.findall(r"\S+(?:\s*[(\[][^)\]]*[)\]])?", line)


def _role_of(header: str) -> Role | None:
    return _HEADER_NAMES.get(_UNIT.sub("", header).strip().lower())


def _suggest_mapping(
    headers: list[str] | None, column_count: int, expected: Quantity | None
) -> tuple[dict[int, Role], list[ParseIssue]]:
    issues: list[ParseIssue] = []
    mapping: dict[int, Role] = {}
    if headers is None:
        mapping[0] = "temperature"
        if expected is not None and column_count >= 2:
            mapping[1] = expected
        return mapping, issues
    taken: set[Role] = set()
    for index, header in enumerate(headers):
        role = _role_of(header)
        if role is None:
            continue
        if role in taken:
            issues.append(ParseIssue("repeated_role", column=index))
            continue
        taken.add(role)
        mapping[index] = role
        if _UNIT.search(header):
            issues.append(ParseIssue("unit_not_checked", column=index))
    return mapping, issues


def to_measurements(
    columns: tuple[np.ndarray, ...],
    lines: tuple[int, ...],
    mapping: Mapping[int, Role],
) -> tuple[dict[Quantity, Measurement], list[ParseIssue], list[ParseIssue]]:
    """Return measurements for a mapping, sorted by temperature, with errors and warnings."""
    errors: list[ParseIssue] = []
    warnings: list[ParseIssue] = []
    roles = list(mapping.values())
    if "temperature" not in roles:
        return {}, [ParseIssue("missing_temperature")], warnings
    temperature_column = next(index for index, role in mapping.items() if role == "temperature")
    temperature_k = columns[temperature_column]
    for row in np.flatnonzero(temperature_k <= 0):
        errors.append(ParseIssue("non_positive_temperature", lines[row], temperature_column))
    if errors:
        return {}, errors, warnings
    order = np.argsort(temperature_k, kind="stable")
    if np.any(np.diff(temperature_k) < 0):
        warnings.append(ParseIssue("unsorted_temperature", column=temperature_column))
    sorted_k = temperature_k[order]
    for position in np.flatnonzero(np.diff(sorted_k) == 0):
        warnings.append(
            ParseIssue("duplicate_temperature", lines[order[position + 1]], temperature_column)
        )
    measurements: dict[Quantity, Measurement] = {}
    for index, role in mapping.items():
        if role != "temperature":
            measurements[role] = Measurement(sorted_k.copy(), columns[index][order])
    return measurements, errors, warnings


def _failed(
    errors: Iterable[ParseIssue],
    warnings: Iterable[ParseIssue] = (),
    headers: list[str] | None = None,
) -> ParsedTable:
    return ParsedTable(
        tuple(headers) if headers else None, (), (), {}, {}, tuple(errors), tuple(warnings)
    )


def parse_table(text: str, expected: Quantity | None = None) -> ParsedTable:
    """Read a text of measured data.

    `expected` names the quantity of a file that holds one, for a file with no header. Unrecognised
    columns stay out of the mapping, and a user can assign them. Comment lines start with `#`.
    """
    lines = _data_lines(text)
    if not lines:
        return _failed([ParseIssue("no_data")])
    headers: list[str] | None = None
    first_number, first_line = lines[0]
    if _is_header(first_line):
        headers = _header_fields(first_line)
        lines = lines[1:]
        if not lines:
            return _failed([ParseIssue("no_data")], headers=headers)

    errors: list[ParseIssue] = []
    rows: list[list[float]] = []
    row_lines: list[int] = []
    column_count = len(headers) if headers is not None else None
    for number, line in lines:
        if _DECIMAL_COMMA.search(line) and re.search(r"\d\s+[+-]?[\d.]", line.replace(", ", ",")):
            errors.append(ParseIssue("decimal_comma", number))
            continue
        fields = _split(line)
        if column_count is None:
            column_count = len(fields)
        if len(fields) < 2:
            errors.append(ParseIssue("too_few_columns", number))
            continue
        if len(fields) != column_count:
            errors.append(ParseIssue("wrong_column_count", number))
            continue
        row: list[float] = []
        for column, field in enumerate(fields):
            if not field:
                errors.append(ParseIssue("missing_value", number, column))
            elif _NUMBER.fullmatch(field) is None:
                errors.append(ParseIssue("not_numeric", number, column))
            else:
                value = float(field)
                if not np.isfinite(value):
                    errors.append(ParseIssue("not_finite", number, column))
                row.append(value)
        if len(row) == len(fields):
            rows.append(row)
            row_lines.append(number)

    if errors:
        return _failed(errors, headers=headers)
    if len(rows) < MIN_ROWS:
        return _failed([ParseIssue("too_few_rows")], headers=headers)
    assert column_count is not None
    if column_count < 2:
        return _failed([ParseIssue("too_few_columns", first_number)], headers=headers)

    table = np.array(rows, dtype=np.float64)
    columns = tuple(table[:, index] for index in range(column_count))
    mapping, issues = _suggest_mapping(headers, column_count, expected)
    warnings = list(issues)
    if len(rows) < FEW_ROWS:
        warnings.append(ParseIssue("few_rows"))
    measurements, measurement_errors, measurement_warnings = to_measurements(
        columns, tuple(row_lines), mapping
    )
    return ParsedTable(
        tuple(headers) if headers else None,
        columns,
        tuple(row_lines),
        mapping,
        measurements,
        tuple(measurement_errors),
        tuple(warnings + measurement_warnings),
    )
