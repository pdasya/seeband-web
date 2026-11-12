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

/** Whether the values of a column look like another unit, which a user must see before a fit. */
export function looksLikeAnotherUnit(
  warnings: readonly Issue[],
  column: number | undefined,
): boolean {
  return warnings.some(
    (issue) =>
      issue.code === "implausible_magnitude" &&
      (column === undefined || issue.column === column),
  );
}
