import type { Unit } from "@/data/units";
import { quantityOf, type ColumnRole, type Quantity } from "@/session/store";

export type Role = ColumnRole["role"];

/**
 * What each column of a file with no header holds, before the user chooses: T first, as the
 * desktop reads it, and nothing else. Values alone cannot tell ρ from S, so the user names the
 * quantity, which reads the file at once.
 */
export function initialRoles(columns: number): (Role | null)[] {
  return Array.from({ length: columns }, (_, column) =>
    column === 0 ? "temperature" : null,
  );
}

/** The quantity a choice gives, or null unless it has one T and one quantity. σ gives ρ = 1/σ. */
export function chosenQuantity(
  roles: readonly (Role | null)[],
): Quantity | null {
  // Two chosen, of which one is a quantity, leaves T as the other.
  const chosen = roles.filter((role) => role !== null);
  const quantities = chosen.filter((role) => role !== "temperature");
  const [only] = quantities;
  return chosen.length === 2 && quantities.length === 1 && only !== undefined
    ? quantityOf(only)
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
