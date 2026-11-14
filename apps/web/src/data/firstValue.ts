import type { Role } from "@/data/columnChoice";
import { UNITS_OF, type Unit } from "@/data/units";
import { formatNumber, withDecimalComma } from "@/lib/numbers";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/** A value of a column: T as a plain number, a quantity with four digits and an exponent. */
export function formatValue(
  value: number | null | undefined,
  isTemperature: boolean,
): string {
  if (value === undefined || value === null) {
    return "";
  }
  return isTemperature
    ? formatNumber(value)
    : withDecimalComma(value.toExponential(3));
}

/**
 * A value exactly as the file writes it, in its unit, and in SI from the server's conversion where
 * the unit is another, so that a user can find it in their file and check the unit against it.
 */
export function valueInUnit(
  written: string | undefined,
  si: number | null | undefined,
  role: Role,
  unit: Unit,
): string {
  const isTemperature = role === "temperature";
  const shown = written ?? "";
  if (shown === "") {
    return "";
  }
  const siUnit = UNITS_OF[role][0];
  const inUnit = `${shown} ${text.units[unit]}`;
  const converted = formatValue(si, isTemperature);
  return unit === siUnit || converted === ""
    ? inUnit
    : text.inSi(inUnit, `${converted} ${text.units[siUnit]}`);
}
