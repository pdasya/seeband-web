import type { components } from "@seeband/api-client";

import type { Role } from "@/data/columnChoice";
import { STRINGS } from "@/strings";

type ColumnRole = components["schemas"]["ColumnRole"];
type ColumnRead = components["schemas"]["ColumnRead"];
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

/**
 * Whether a column was read in SI only because nothing named its unit: no header unit, a header
 * unit the parser cannot read, or no header at all. A user's choice, even of SI, ends it.
 */
export function unitIsDefault(
  item: Pick<ColumnRead, "unit_source"> | undefined,
) {
  return item?.unit_source === "default";
}

/**
 * The mapping to send again with the text: a unit only where a user chose it, so that a header
 * unit is read from the header again, and a column read in SI by default stays marked as such.
 * An answer that does not say where a unit came from keeps it, as before the source was known.
 */
export function requestMapping(readAs: readonly ColumnRead[]): ColumnRole[] {
  return readAs.map(({ column, role, unit, unit_source: source }) =>
    unit != null && (source === "chosen" || source == null)
      ? { column, role, unit }
      : { column, role },
  );
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

/**
 * What a doubt about a column's unit means for its quantity, and what to do. Values read in SI as
 * nothing named a unit name the lab units the quantity is often written in, and those SeeBand
 * cannot read; a unit the header named or the user chose is what to check. The size itself is the
 * server's to judge, and it does not say whether values are too large or too small.
 */
export function unitDoubtMessage(
  doubt: UnitDoubt,
  role: Role,
  item: Pick<ColumnRead, "unit" | "unit_source"> | undefined,
): string {
  const { data: text } = STRINGS;
  if (doubt === "unit_assumed" || role === "temperature") {
    return text.issues[doubt];
  }
  const unit = item?.unit ?? UNITS_OF[role][0];
  const label = text.units[unit];
  if (item?.unit_source === "header") {
    return text.implausible.inHeaderUnit(label);
  }
  return item?.unit_source === "chosen" || unit !== UNITS_OF[role][0]
    ? text.implausible.inChosenUnit(label)
    : text.implausible.inSi[role];
}
