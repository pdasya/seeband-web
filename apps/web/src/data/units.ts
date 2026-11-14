import type { components } from "@seeband/api-client";

import type { Role } from "@/data/columnChoice";

type ColumnRole = components["schemas"]["ColumnRole"];
type Issue = components["schemas"]["IssueResponse"];

/** A unit a column can be read in. The core holds the conversions, and converts to SI. */
export type Unit = NonNullable<ColumnRole["unit"]>;

/**
 * The units offered for each column's role, SI first, as `input-data.md` of the core lists them.
 * Only labels and choices live here; a test checks them against the contract.
 */
export const UNITS_OF: Readonly<Record<Role, readonly [Unit, ...Unit[]]>> = {
  temperature: ["K", "C"],
  seebeck: ["V/K", "uV/K"],
  resistivity: ["Ohm*m", "mOhm*cm", "uOhm*m"],
  conductivity: ["S/m", "S/cm"],
  hall: ["m^3/C", "cm^3/C"],
};

/** The unit the column of a role was read in, or SI when the answer names none. */
export function unitOf(
  mapping: readonly ColumnRole[] | undefined,
  role: Role,
): Unit {
  return mapping?.find((item) => item.role === role)?.unit ?? UNITS_OF[role][0];
}

/** A mapping with the column of one role read in another unit. */
export function withUnit(
  mapping: readonly ColumnRole[],
  role: Role,
  unit: Unit,
): ColumnRole[] {
  return mapping.map((item) => (item.role === role ? { ...item, unit } : item));
}

/**
 * Why a column's unit may be wrong: values that look like another unit, or a unit its header names
 * that was not used, so it was read in SI. A user must see either before a fit.
 */
export type UnitDoubt = Extract<
  Issue["code"],
  "implausible_magnitude" | "unit_assumed"
>;

export function isUnitDoubt(code: Issue["code"]): code is UnitDoubt {
  return code === "implausible_magnitude" || code === "unit_assumed";
}

/** The column the server read a role from, if any. */
export function columnOf(
  mapping: readonly ColumnRole[] | undefined,
  role: Role,
): number | undefined {
  return mapping?.find((item) => item.role === role)?.column;
}

/** The doubts about one column's unit, and none for a column not read, as another holds them. */
export function unitDoubts(
  warnings: readonly Issue[],
  column: number | undefined,
): UnitDoubt[] {
  if (column === undefined) {
    return [];
  }
  return warnings.flatMap(({ code, column: at }) =>
    at === column && isUnitDoubt(code) ? [code] : [],
  );
}
