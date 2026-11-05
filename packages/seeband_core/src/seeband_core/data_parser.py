"""Read measured data from text, as the Conventions page describes.

Columns are separated by spaces, tabs or commas, and values are in the units of `QUANTITY_UNITS`.
Where it is not clear what a column holds, it stays unassigned for a user to assign, because a wrong
guess gives numbers that look fine. Problems come back as codes with no text and no measured values,
so that a client can translate them and a log can hold them.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal, get_args

import numpy as np

from seeband_core.model_interface import Measurement, Quantity

Role = Literal["temperature", "seebeck", "resistivity", "hall"]
IssueCode = Literal[
    # Errors
    "no_data",
    "wrong_encoding",
    "line_too_long",
    "too_many_problems",
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
    # Warnings
    "preamble_skipped",
    "header_mismatch",
    "unit_differs",
    "repeated_header",
    "columns_need_assigning",
    "expected_not_found",
    "no_quantity",
    "few_rows",
    "unsorted_temperature",
    "duplicate_temperature",
]

MIN_ROWS = 2
# Below this, the degree 5 fit that chooses DPB start values is not determined.
FEW_DISTINCT_TEMPERATURES = 6
# Limits on what one text can cost, because a request can hold any text.
MAX_LINE_LENGTH = 2000
MAX_ERRORS = 50
# Matched exactly, because lower-case t and s usually mean time and a standard deviation.
_EXACT_NAMES: Mapping[str, Role] = {"T": "temperature", "S": "seebeck"}
_NAMES: Mapping[str, Role] = {
    "t_k": "temperature",
    "temp": "temperature",
    "seebeck": "seebeck",
    "rho": "resistivity",
    "ρ": "resistivity",
    "resistivity": "resistivity",
    "rh": "hall",
    "r_h": "hall",
    "hall": "hall",
}
# The units values are read in, without spaces and in lower case.
_UNITS: Mapping[Role, frozenset[str]] = {
    "temperature": frozenset({"k"}),
    "seebeck": frozenset({"v/k"}),
    "resistivity": frozenset({"ohmm", "ohm*m", "ohm·m", "ωm", "ω*m", "ω·m"}),
    "hall": frozenset({"m3/c", "m^3/c", "m³/c"}),
}
_MEASURING_ROLES: tuple[Role, ...] = get_args(Role)
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_STARTS_LIKE_A_NUMBER = re.compile(r"[+-]?\.?\d")
_ANY_SEPARATOR = re.compile(r"\s*,\s*|\s+")
_STRONG_SEPARATOR = re.compile(r"\s*[,\t]\s*")
_DECIMAL_COMMA = re.compile(r"\d,\d")
_SPACE_BETWEEN_NUMBERS = re.compile(r"\d\s+[+-]?[\d.]")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_NAMED_COLUMN = re.compile(r"[^\s(\[]+(?:\s*[(\[][^)\]]*[)\]])?|\S+")
_NAME_AND_UNIT = re.compile(r"([^(\[]*)(?:[(\[]([^)\]]*)[)\]])?\s*")


@dataclass(frozen=True)
class ParseIssue:
    """A problem in the data. `line` counts every line of the text from 1, and `column` from 0."""

    code: IssueCode
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, eq=False)
class ParsedTable:
    """The columns of a text, and what they seem to hold.

    `columns` holds every row that could be read, for a preview, in the order of the text, with
    `lines` giving each row's line. `column_count` is that of the first row of numbers, and 0 if no
    row set one. `mapping` goes from column to role, as a suggestion or as a user
    chose it. `measurements` is sorted by temperature, and is empty with any `errors`.
    """

    headers: tuple[str, ...] | None
    columns: tuple[np.ndarray, ...]
    lines: tuple[int, ...]
    mapping: Mapping[int, Role]
    measurements: Mapping[Quantity, Measurement]
    errors: tuple[ParseIssue, ...]
    warnings: tuple[ParseIssue, ...]
    column_count: int = 0


def _content_lines(text: str) -> list[tuple[int, str]]:
    found = []
    for number, line in enumerate(_LINE_BREAK.split(text), start=1):
        content = line.partition("#")[0].strip().lstrip("﻿").strip()
        if content:
            found.append((number, content))
    return found


def _split(line: str) -> list[str]:
    return _ANY_SEPARATOR.split(line.rstrip(",").rstrip())


def _is_name_line(line: str) -> bool:
    return any(field and _STARTS_LIKE_A_NUMBER.match(field) is None for field in _split(line))


def _header_fields(line: str) -> list[str]:
    """Split a header. Tabs and commas win over spaces, so that `T (K)` stays one column."""
    line = line.rstrip(",").rstrip()
    if "," in line or "\t" in line:
        fields = _STRONG_SEPARATOR.split(line)
    else:
        fields = _NAMED_COLUMN.findall(line)
    return [field.strip("\"'") for field in fields]


def _role_and_unit(header: str) -> tuple[Role | None, str | None]:
    match = _NAME_AND_UNIT.fullmatch(header)
    if match is None:
        return None, None
    name = match.group(1).strip()
    role = _EXACT_NAMES.get(name) or _NAMES.get(name.lower())
    unit = match.group(2)
    return role, unit


def _unit_is_right(role: Role, unit: str) -> bool:
    return re.sub(r"\s+", "", unit).lower() in _UNITS[role]


def _mapping_from_headers(headers: list[str]) -> tuple[dict[int, Role], list[ParseIssue]]:
    mapping: dict[int, Role] = {}
    warnings: list[ParseIssue] = []
    for index, header in enumerate(headers):
        role, unit = _role_and_unit(header)
        if role is None:
            continue
        if unit is not None and not _unit_is_right(role, unit):
            # A value in another unit would be read wrongly, by a factor such as 1e6.
            warnings.append(ParseIssue("unit_differs", column=index))
        elif role in mapping.values():
            warnings.append(ParseIssue("repeated_header", column=index))
        else:
            mapping[index] = role
    return mapping, warnings


def _measure(
    columns: tuple[np.ndarray, ...], lines: tuple[int, ...], mapping: Mapping[int, Role]
) -> tuple[dict[Quantity, Measurement], list[ParseIssue], list[ParseIssue]]:
    """Return sorted measurements for a mapping, with errors and warnings."""
    temperature_columns = [index for index, role in mapping.items() if role == "temperature"]
    if not temperature_columns:
        return {}, [ParseIssue("missing_temperature")], []
    roles = list(mapping.values())
    repeated = [index for index, role in mapping.items() if roles.count(role) > 1]
    if repeated:
        return {}, [ParseIssue("repeated_role", column=index) for index in repeated], []
    temperature_column = temperature_columns[0]
    temperature_k = columns[temperature_column]
    errors = [
        ParseIssue("non_positive_temperature", lines[row], temperature_column)
        for row in np.flatnonzero(temperature_k <= 0)[:MAX_ERRORS]
    ]
    if errors:
        return {}, errors, []
    warnings: list[ParseIssue] = []
    if len(np.unique(temperature_k)) < FEW_DISTINCT_TEMPERATURES:
        warnings.append(ParseIssue("few_rows"))
    order = np.argsort(temperature_k, kind="stable")
    if np.any(np.diff(temperature_k) < 0):
        warnings.append(ParseIssue("unsorted_temperature", column=temperature_column))
    sorted_k = temperature_k[order]
    for position in np.flatnonzero(np.diff(sorted_k) == 0)[:MAX_ERRORS]:
        warnings.append(
            ParseIssue("duplicate_temperature", lines[order[position + 1]], temperature_column)
        )
    measurements: dict[Quantity, Measurement] = {}
    for index, role in mapping.items():
        if role != "temperature":
            measurements[role] = Measurement(sorted_k.copy(), columns[index][order])
    if not measurements:
        warnings.append(ParseIssue("no_quantity"))
    return measurements, [], warnings


_FROM_MAPPING: frozenset[str] = frozenset(
    {
        "missing_temperature",
        "non_positive_temperature",
        "repeated_role",
        "few_rows",
        "unsorted_temperature",
        "duplicate_temperature",
        "no_quantity",
        "expected_not_found",
    }
)


def with_mapping(table: ParsedTable, mapping: Mapping[int, Role]) -> ParsedTable:
    """Return the table with a mapping a user chose. A column or role that does not exist raises."""
    for index, role in mapping.items():
        if not 0 <= index < len(table.columns):
            raise ValueError(f"The table has no column {index}")
        if role not in _MEASURING_ROLES:
            raise ValueError(f"Unknown role: {role}")
    kept_errors = tuple(issue for issue in table.errors if issue.code not in _FROM_MAPPING)
    kept_warnings = tuple(issue for issue in table.warnings if issue.code not in _FROM_MAPPING)
    if kept_errors:
        return replace(
            table,
            mapping=dict(mapping),
            measurements={},
            errors=kept_errors,
            warnings=kept_warnings,
        )
    measurements, errors, warnings = _measure(table.columns, table.lines, mapping)
    return replace(
        table,
        mapping=dict(mapping),
        measurements=measurements,
        errors=tuple(errors),
        warnings=kept_warnings + tuple(warnings),
    )


def _read_rows(
    lines: list[tuple[int, str]],
) -> tuple[list[list[float]], list[int], int | None, list[ParseIssue]]:
    errors: list[ParseIssue] = []
    rows: list[list[float]] = []
    row_lines: list[int] = []
    column_count: int | None = None
    for number, line in lines:
        if len(errors) >= MAX_ERRORS:
            errors.append(ParseIssue("too_many_problems"))
            break
        if len(line) > MAX_LINE_LENGTH:
            errors.append(ParseIssue("line_too_long", number))
            continue
        if _DECIMAL_COMMA.search(line) and _SPACE_BETWEEN_NUMBERS.search(line.replace(", ", ",")):
            errors.append(ParseIssue("decimal_comma", number))
            continue
        fields = _split(line)
        if len(fields) < 2:
            errors.append(ParseIssue("too_few_columns", number))
            continue
        if column_count is None:
            column_count = len(fields)
        if len(fields) != column_count:
            errors.append(ParseIssue("wrong_column_count", number))
            continue
        row: list[float] = []
        for column, field in enumerate(fields):
            if not field:
                errors.append(ParseIssue("missing_value", number, column))
            elif _NUMBER.fullmatch(field) is None:
                errors.append(ParseIssue("not_numeric", number, column))
            elif not np.isfinite(float(field)):
                errors.append(ParseIssue("not_finite", number, column))
            else:
                row.append(float(field))
        if len(row) == len(fields):
            rows.append(row)
            row_lines.append(number)
    return rows, row_lines, column_count, errors


def parse_table(
    text: str,
    expected: Quantity | None = None,
    mapping: Mapping[int, Role] | None = None,
) -> ParsedTable:
    """Read a text of measured data.

    `expected` names the quantity of a file meant to hold one. It gives the second column of a file
    with two columns and no header. `mapping` replaces the suggested mapping with a user's choice.
    Text before a table is skipped with a warning, its last line is the header, and `#` starts a
    comment.
    """
    if expected is not None and expected not in _MEASURING_ROLES:
        raise ValueError(f"Unknown quantity: {expected}")
    lines = _content_lines(text)
    leading = 0
    while (
        leading < len(lines)
        and len(lines[leading][1]) <= MAX_LINE_LENGTH
        and _is_name_line(lines[leading][1])
    ):
        leading += 1
    warnings = [
        ParseIssue("preamble_skipped", number) for number, _ in lines[: max(leading - 1, 0)]
    ]
    header_fields = _header_fields(lines[leading - 1][1]) if leading else None
    data_lines = lines[leading:]
    empty = ParsedTable(None, (), (), {}, {}, (), tuple(warnings))
    if not data_lines:
        # A text read in the wrong encoding, such as UTF-16 as UTF-8, has only "text" lines.
        code: IssueCode = "wrong_encoding" if "\x00" in text or "\ufffd" in text else "no_data"
        return replace(empty, errors=(ParseIssue(code),))

    rows, row_lines, column_count, errors = _read_rows(data_lines)
    columns: tuple[np.ndarray, ...] = ()
    if rows:
        table = np.array(rows, dtype=np.float64)
        columns = tuple(table[:, index] for index in range(table.shape[1]))
    if not errors and len(rows) < MIN_ROWS:
        errors.append(ParseIssue("too_few_rows"))

    suggestion: dict[int, Role] = {}
    headers = header_fields
    if header_fields is not None and column_count is not None:
        if len(header_fields) == column_count:
            suggestion, header_warnings = _mapping_from_headers(header_fields)
            warnings += header_warnings
        else:
            warnings.append(ParseIssue("header_mismatch"))
            headers = None
    elif column_count is not None:
        suggestion[0] = "temperature"
        if column_count == 2 and expected is not None:
            suggestion[1] = expected
        elif column_count > 2:
            warnings.append(ParseIssue("columns_need_assigning"))
    if expected is not None and column_count is not None and expected not in suggestion.values():
        warnings.append(ParseIssue("expected_not_found"))

    parsed = ParsedTable(
        tuple(headers) if headers is not None else None,
        columns,
        tuple(row_lines),
        suggestion,
        {},
        tuple(errors),
        tuple(warnings),
        column_count or 0,
    )
    if errors:
        return parsed
    expected_warning = tuple(i for i in parsed.warnings if i.code == "expected_not_found")
    chosen = with_mapping(parsed, suggestion if mapping is None else mapping)
    if mapping is None:
        return replace(chosen, warnings=chosen.warnings + expected_warning)
    return chosen
