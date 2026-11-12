import type { Unit } from "@/data/units";
import type { ColumnRole, Quantity } from "@/session/store";

export type Role = ColumnRole["role"];

/**
 * What each column of a file with no header holds, before the user chooses: T first, as the
 * desktop reads it, and the slot's quantity second, for a file of two columns unless something
 * speaks against it: a name of another quantity, or values that quantity cannot have. With more
 * columns, or such doubt, the user decides.
 */
export function initialRoles(
  columns: number,
  quantity: Quantity,
  doubtful: boolean,
): (Role | null)[] {
  return Array.from({ length: columns }, (_, column) => {
    if (column === 0) {
      return "temperature";
    }
    return column === 1 && columns === 2 && !doubtful ? quantity : null;
  });
}

/** The quantity a choice gives, or null unless it has one T and one quantity. */
export function chosenQuantity(
  roles: readonly (Role | null)[],
): Quantity | null {
  // Two chosen, of which one is a quantity, leaves T as the other.
  const chosen = roles.filter((role) => role !== null);
  const quantities = chosen.filter((role) => role !== "temperature");
  return chosen.length === 2 && quantities.length === 1
    ? (quantities[0] as Quantity)
    : null;
}

/**
 * As `POST /api/parse` takes it, with the columns left out that hold nothing, and the unit chosen
 * for a column. With no unit, the server reads the column in SI.
 */
export function mappingOf(
  roles: readonly (Role | null)[],
  units: readonly (Unit | null)[] = [],
): ColumnRole[] {
  return roles.flatMap((role, column) => {
    if (role === null) {
      return [];
    }
    const unit = units[column] ?? null;
    return unit === null ? [{ column, role }] : [{ column, role, unit }];
  });
}
