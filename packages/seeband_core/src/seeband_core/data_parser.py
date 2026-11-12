"""Read measured data from text, as the Conventions page describes.

Columns are separated by spaces, tabs or commas. Each column is read in a unit of `UNITS`, from its
header or a user's choice, and measurements are converted to SI here, so nothing after this reads a
unit.
Where it is not clear what a column holds, it stays unassigned for a user to assign, because a wrong
guess gives numbers that look fine. Problems come back as codes with no text and no measured values,
so that a client can translate them and a log can hold them.
"""

import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
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
    "negative_resistivity",
    "repeated_role",
    "unit_not_allowed",
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
    "unit_assumed",
    "implausible_magnitude",
]
Unit = Literal["K", "C", "V/K", "uV/K", "Ohm*m", "mOhm*cm", "uOhm*m", "m^3/C", "cm^3/C"]

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


@dataclass(frozen=True)
class Conversion:
    """How a unit goes to SI: shift the decimal point by `exponent`, then add `offset`.

    Both are exact in decimal, so a value converted from its text is the float its SI text would
    give: 50.1 µV/K is the float of 5.01e-5 V/K, and 26.85 °C that of 300 K, to the last bit.
    """

    exponent: int = 0
    offset: Decimal = Decimal(0)

    @property
    def is_si(self) -> bool:
        return self.exponent == 0 and self.offset == 0


# The units a column can be read in. The first of each is SI and the default.
UNITS: Mapping[Role, Mapping[Unit, Conversion]] = {
    "temperature": {"K": Conversion(), "C": Conversion(offset=Decimal("273.15"))},
    "seebeck": {"V/K": Conversion(), "uV/K": Conversion(-6)},
    "resistivity": {"Ohm*m": Conversion(), "mOhm*cm": Conversion(-5), "uOhm*m": Conversion(-6)},
    "hall": {"m^3/C": Conversion(), "cm^3/C": Conversion(-6)},
}
# How a header writes each unit, after `_unit_key`.
_HEADER_UNITS: Mapping[Role, Mapping[str, Unit]] = {
    "temperature": {"k": "K", "kelvin": "K", "c": "C", "°c": "C", "degc": "C", "celsius": "C"},
    "seebeck": {"v/k": "V/K", "uv/k": "uV/K"},
    "resistivity": {"ohmm": "Ohm*m", "mohmcm": "mOhm*cm", "uohmm": "uOhm*m"},
    "hall": {"m3/c": "m^3/C", "cm3/c": "cm^3/C"},
}
# A largest |value| in SI outside these is more likely a wrong unit than a measurement, as for µV/K
# read as V/K, 1e6 too large. Only a warning, and only for gross errors: the SiP example reaches
# ρ = 0.16 Ω·m and |R_H| = 0.013 m³/C, so mΩ·cm or cm³/C read as SI often look possible, and
# only the unit chosen for a column protects them.
PLAUSIBLE_MAGNITUDE: Mapping[Quantity, tuple[float, float]] = {
    "seebeck": (1e-7, 1e-2),
    "resistivity": (1e-10, 1.0),
    "hall": (1e-13, 1e-1),
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

    `columns` holds every row that could be read, for a preview, in the order of the text and in its
    units, with `lines` giving each row's line, and `texts` the same values as written.
    `column_count` is that of the first row of numbers, and 0 if no row set one. `mapping` goes
    from column to role, as a suggestion or as a user chose it, and `units` gives the unit each
    mapped column is read in. `measurements` is in SI, sorted by temperature, and is empty with any
    `errors`. `header_units` holds the unit text of each header that has one, so that a column
    assigned by hand is read in it.
    """

    headers: tuple[str, ...] | None
    columns: tuple[np.ndarray, ...]
    lines: tuple[int, ...]
    mapping: Mapping[int, Role]
    measurements: Mapping[Quantity, Measurement]
    errors: tuple[ParseIssue, ...]
    warnings: tuple[ParseIssue, ...]
    column_count: int = 0
    units: Mapping[int, Unit] = dataclasses.field(default_factory=dict)
    header_units: Mapping[int, str] = dataclasses.field(default_factory=dict)
    texts: tuple[tuple[str, ...], ...] = ()


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


def _unit_key(unit: str) -> str | None:
    """A unit as written, in one spelling: `mΩ·cm`, `mOhm cm` and `mohm*cm` give `mohmcm`."""
    key = re.sub(r"\s+", "", unit)
    # Lower case would read mega as milli, wrong by 1e9.
    if key.startswith("M"):
        return None
    for written, spelling in (
        ("µ", "u"),
        ("μ", "u"),
        ("Ω", "ohm"),
        ("\u2126", "ohm"),  # OHM SIGN, as Excel and Windows write it
        ("ω", "ohm"),
        ("³", "3"),
        ("℃", "°C"),
        ("º", "°"),
    ):
        key = key.replace(written, spelling)
    return re.sub(r"[*·⋅^]", "", key).lower()


def header_unit(role: Role, unit: str) -> Unit | None:
    """The unit a header's text names for a role, or None for one this cannot read."""
    key = _unit_key(unit)
    return None if key is None else _HEADER_UNITS[role].get(key)


def _mapping_from_headers(
    headers: list[str],
) -> tuple[dict[int, Role], dict[int, str], list[ParseIssue]]:
    mapping: dict[int, Role] = {}
    units: dict[int, str] = {}
    warnings: list[ParseIssue] = []
    for index, header in enumerate(headers):
        role, unit = _role_and_unit(header)
        if unit is not None and unit.strip():
            units[index] = unit.strip()
        if role is None:
            continue
        if unit is not None and header_unit(role, unit) is None:
            # A value in a unit this cannot read would be wrong by a factor such as 1e6.
            warnings.append(ParseIssue("unit_differs", column=index))
        elif role in mapping.values():
            warnings.append(ParseIssue("repeated_header", column=index))
        else:
            mapping[index] = role
    return mapping, units, warnings


def to_si(role: Role, unit: Unit, texts: tuple[str, ...], values: np.ndarray) -> np.ndarray:
    """A column in SI, from its values as written. A unit that is not one of the role's raises.

    SI comes back as read. Another unit is converted in decimal and rounded once, as float
    arithmetic such as 50 * 1e-6 = 4.9999999999999996e-05 would differ from the SI value in its
    last bit, and a fit can make that 1e-8 apart.
    """
    if unit not in UNITS[role]:
        raise ValueError(f"{unit} is not a unit of {role}")
    conversion = UNITS[role][unit]
    if conversion.is_si:
        return values.copy()
    return np.array(
        [
            _convert(text, float(value), conversion)
            for text, value in zip(texts, values, strict=True)
        ],
        dtype=np.float64,
    )


# Beyond this decimal exponent a finite value as read is 0 or below 1e-308. Decimal cannot hold an
# exponent such as that of `1e-99999999999999999999`, which float reads as 0.
_DECIMAL_EXPONENT_LIMIT = 400


def _convert(text: str, value: float, conversion: Conversion) -> float:
    """One value as written, in SI. Decimal from its text, or from the value read at an exponent
    no measurement has."""
    try:
        written = Decimal(text)
    except InvalidOperation:
        written = Decimal(value)
    if abs(written.adjusted()) > _DECIMAL_EXPONENT_LIMIT:
        written = Decimal(value)
    return float(written.scaleb(conversion.exponent) + conversion.offset)


def si_column(table: ParsedTable, index: int, rows: int | None = None) -> np.ndarray | None:
    """A mapped column in SI, in the order of the text, or None for a column with no role or no
    unit, as with errors. With `rows`, only the first rows, so a preview converts no more."""
    role = table.mapping.get(index)
    unit = table.units.get(index)
    if role is None or unit is None:
        return None
    return to_si(role, unit, table.texts[index][:rows], table.columns[index][:rows])


def _units_for(
    mapping: Mapping[int, Role], chosen: Mapping[int, Unit], header_units: Mapping[int, str]
) -> tuple[dict[int, Unit], list[ParseIssue]]:
    """The unit of each mapped column: the user's, then its header's, then SI.

    A header unit that cannot be read leaves SI, with a warning that says so.
    """
    units: dict[int, Unit] = {}
    warnings: list[ParseIssue] = []
    for index, role in mapping.items():
        if index in chosen:
            units[index] = chosen[index]
            continue
        written = header_units.get(index)
        read = None if written is None else header_unit(role, written)
        if written is not None and read is None:
            warnings.append(ParseIssue("unit_assumed", column=index))
        units[index] = next(iter(UNITS[role])) if read is None else read
    return units, warnings


def _measure(
    columns: tuple[np.ndarray, ...],
    texts: tuple[tuple[str, ...], ...],
    lines: tuple[int, ...],
    mapping: Mapping[int, Role],
    units: Mapping[int, Unit],
) -> tuple[dict[Quantity, Measurement], list[ParseIssue], list[ParseIssue]]:
    """Return sorted measurements in SI for a mapping, with errors and warnings."""
    temperature_columns = [index for index, role in mapping.items() if role == "temperature"]
    if not temperature_columns:
        return {}, [ParseIssue("missing_temperature")], []
    roles = list(mapping.values())
    repeated = [index for index, role in mapping.items() if roles.count(role) > 1]
    if repeated:
        return {}, [ParseIssue("repeated_role", column=index) for index in repeated], []
    temperature_column = temperature_columns[0]
    # In K, so that 0 °C is not below zero and rows sort the same in any unit.
    temperature_k = to_si(
        "temperature",
        units[temperature_column],
        texts[temperature_column],
        columns[temperature_column],
    )
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
    # A measured resistivity cannot be below 0, and a sign from another convention would fit
    # wrongly without a word.
    negative = [
        ParseIssue("negative_resistivity", lines[row], index)
        for index, role in mapping.items()
        if role == "resistivity"
        for row in np.flatnonzero(columns[index] < 0)[:MAX_ERRORS]
    ]
    if negative:
        return {}, negative, warnings
    measurements: dict[Quantity, Measurement] = {}
    for index, role in mapping.items():
        if role != "temperature":
            values = to_si(role, units[index], texts[index], columns[index])[order]
            measurements[role] = Measurement(sorted_k.copy(), values)
            low, high = PLAUSIBLE_MAGNITUDE[role]
            if not low <= float(np.max(np.abs(values))) <= high:
                warnings.append(ParseIssue("implausible_magnitude", column=index))
    if not measurements:
        warnings.append(ParseIssue("no_quantity"))
    return measurements, [], warnings


_FROM_MAPPING: frozenset[str] = frozenset(
    {
        "missing_temperature",
        "non_positive_temperature",
        "negative_resistivity",
        "repeated_role",
        "few_rows",
        "unsorted_temperature",
        "duplicate_temperature",
        "no_quantity",
        "expected_not_found",
        "unit_not_allowed",
        "unit_assumed",
        "implausible_magnitude",
    }
)


def with_mapping(
    table: ParsedTable, mapping: Mapping[int, Role], units: Mapping[int, Unit] | None = None
) -> ParsedTable:
    """Return the table with a mapping a user chose, and the units of any columns they chose.

    A column or role that does not exist raises. A unit for a column outside the mapping is
    ignored, and one its role cannot have is an error, as the values would be wrong by a factor.
    """
    for index, role in mapping.items():
        if not 0 <= index < len(table.columns):
            raise ValueError(f"The table has no column {index}")
        if role not in _MEASURING_ROLES:
            raise ValueError(f"Unknown role: {role}")
    chosen = {index: unit for index, unit in (units or {}).items() if index in mapping}
    wrong = [index for index, unit in chosen.items() if unit not in UNITS[mapping[index]]]
    # A column with an unreadable unit stops being "not used" once a user assigns it.
    kept_warnings = tuple(
        issue
        for issue in table.warnings
        if issue.code not in _FROM_MAPPING
        and not (issue.code == "unit_differs" and issue.column in mapping)
    )
    kept_errors = tuple(issue for issue in table.errors if issue.code not in _FROM_MAPPING)
    if wrong:
        kept_errors += tuple(ParseIssue("unit_not_allowed", column=index) for index in wrong)
    if kept_errors:
        return replace(
            table,
            mapping=dict(mapping),
            units={index: unit for index, unit in chosen.items() if index not in wrong},
            measurements={},
            errors=kept_errors,
            warnings=kept_warnings,
        )
    column_units, unit_warnings = _units_for(mapping, chosen, table.header_units)
    measurements, errors, warnings = _measure(
        table.columns, table.texts, table.lines, mapping, column_units
    )
    return replace(
        table,
        mapping=dict(mapping),
        units=column_units,
        measurements=measurements,
        errors=tuple(errors),
        warnings=kept_warnings + tuple(unit_warnings) + tuple(warnings),
    )


def _read_rows(
    lines: list[tuple[int, str]],
) -> tuple[list[list[float]], list[list[str]], list[int], int | None, list[ParseIssue]]:
    errors: list[ParseIssue] = []
    rows: list[list[float]] = []
    texts: list[list[str]] = []
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
            texts.append(fields)
            row_lines.append(number)
    return rows, texts, row_lines, column_count, errors


def parse_table(
    text: str,
    expected: Quantity | None = None,
    mapping: Mapping[int, Role] | None = None,
    units: Mapping[int, Unit] | None = None,
) -> ParsedTable:
    """Read a text of measured data.

    `expected` names the quantity of a file meant to hold one. It gives the second column of a file
    with two columns and no header. `mapping` replaces the suggested mapping with a user's choice,
    and `units` the unit of a column, which is otherwise its header's, or SI.
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

    rows, row_texts, row_lines, column_count, errors = _read_rows(data_lines)
    columns: tuple[np.ndarray, ...] = ()
    texts: tuple[tuple[str, ...], ...] = ()
    if rows:
        table = np.array(rows, dtype=np.float64)
        columns = tuple(table[:, index] for index in range(table.shape[1]))
        texts = tuple(zip(*row_texts, strict=True))
    if not errors and len(rows) < MIN_ROWS:
        errors.append(ParseIssue("too_few_rows"))

    suggestion: dict[int, Role] = {}
    header_units: dict[int, str] = {}
    headers = header_fields
    if header_fields is not None and column_count is not None:
        if len(header_fields) == column_count:
            suggestion, header_units, header_warnings = _mapping_from_headers(header_fields)
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
        header_units=header_units,
        texts=texts,
    )
    if errors:
        return parsed
    expected_warning = tuple(i for i in parsed.warnings if i.code == "expected_not_found")
    chosen = with_mapping(parsed, suggestion if mapping is None else mapping, units)
    if mapping is None:
        return replace(chosen, warnings=chosen.warnings + expected_warning)
    return chosen
