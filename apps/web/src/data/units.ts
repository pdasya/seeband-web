import type { components } from "@seeband/api-client";

import type { Quantity } from "@/session/store";

type ColumnRole = components["schemas"]["ColumnRole"];
type Issue = components["schemas"]["IssueResponse"];

/** A unit a column can be read in. The core holds the factors, and converts to SI. */
export type Unit = NonNullable<ColumnRole["unit"]>;

/**
 * The units offered for each quantity, SI first, as `input-data.md` of the core lists them. Only
 * labels and choices live here; a test checks them against the contract.
 */
export const UNITS_OF: Readonly<Record<Quantity, readonly [Unit, ...Unit[]]>> =
  {
    seebeck: ["V/K", "uV/K"],
    resistivity: ["Ohm*m", "mOhm*cm", "uOhm*m"],
    hall: ["m^3/C", "cm^3/C"],
  };

/** The unit a column of a mapping was read in, or SI when the answer names none. */
export function unitOf(
  mapping: readonly ColumnRole[] | undefined,
  quantity: Quantity,
): Unit {
  return (
    mapping?.find(({ role }) => role === quantity)?.unit ??
    UNITS_OF[quantity][0]
  );
}

/** A mapping with one quantity's column read in another unit. */
export function withUnit(
  mapping: readonly ColumnRole[],
  quantity: Quantity,
  unit: Unit,
): ColumnRole[] {
  return mapping.map((item) =>
    item.role === quantity ? { ...item, unit } : item,
  );
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
