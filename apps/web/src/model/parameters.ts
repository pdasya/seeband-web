import type { components } from "@seeband/api-client";

import { parseNumber } from "@/lib/numbers";
import type { FitModeDescription } from "@/model/selection";
import { STRINGS } from "@/strings";

export type ParameterDescription = components["schemas"]["ParameterResponse"];
export type FitBounds = components["schemas"]["BoundsInput"];

/** How a parameter is written. Any other shows its name, so a new one needs no change. */
export function parameterSymbol(name: string): string {
  const known: Record<string, string> = STRINGS.parameters.symbols;
  return known[name] ?? name;
}

/** A mode with no choice of scattering uses all its parameters, whatever they list. */
export function visibleParameters(
  mode: FitModeDescription,
  scattering: string | null,
): ParameterDescription[] {
  return mode.parameters.filter(
    (parameter) =>
      mode.scattering.length === 0 ||
      parameter.scattering.length === 0 ||
      (scattering !== null && parameter.scattering.includes(scattering)),
  );
}

/** What a fit of this mode lets the user bound, with the bounds of its description. */
export function editableParameters(
  mode: FitModeDescription,
  scattering: string | null,
): { parameter: ParameterDescription; bounds: FitBounds }[] {
  return visibleParameters(mode, scattering).flatMap((parameter) => {
    const { fit_bounds: bounds, role, bounds_editable: editable } = parameter;
    return role === "fitted" && editable && bounds != null
      ? [{ parameter, bounds }]
      : [];
  });
}

/** The control of a parameter with bounds of the user's, as on the desktop they set its range. */
export function withCustomRange(
  parameter: ParameterDescription,
  bounds: FitBounds | undefined,
): ParameterDescription {
  return bounds === undefined
    ? parameter
    : {
        ...parameter,
        display_range: {
          ...parameter.display_range,
          minimum: coreToDisplay(parameter, bounds.lower),
          maximum: coreToDisplay(parameter, bounds.upper),
        },
      };
}

/** Every parameter of a mode in core units, as requests need them: those set, then the defaults. */
export function parameterValues(
  mode: FitModeDescription,
  saved: Readonly<Record<string, number>> | undefined,
): Record<string, number> {
  return Object.fromEntries(
    mode.parameters.map((parameter) => [
      parameter.name,
      saved?.[parameter.name] ?? parameter.core_range.default,
    ]),
  );
}

// As the core converts: dividing where a scale is a fraction, which keeps the last bit.
function scaled(value: number, scale: number): number {
  return scale > 0 && scale < 1 ? value / Math.round(1 / scale) : value * scale;
}

export function coreToDisplay(
  parameter: ParameterDescription,
  value: number,
): number {
  return parameter.display_scale === parameter.fit_scale
    ? value
    : scaled(value, parameter.display_scale / parameter.fit_scale);
}

/**
 * Tidied where the scales differ, so 2.55 at a display scale of 0.01 and a fit scale of 1 gives 255,
 * as the desktop's slider sends, where 2.55 * 100 is 254.99999999999997.
 */
export function displayToCore(
  parameter: ParameterDescription,
  value: number,
): number {
  return parameter.display_scale === parameter.fit_scale
    ? value
    : tidy(scaled(value, parameter.fit_scale / parameter.display_scale));
}

/** A displayed number, without the noise of binary fractions such as 1.1500000000000001. */
export function tidy(value: number): number {
  return Number(value.toPrecision(12));
}

/** What a field shows, as a fit's value has more digits than fit. The session keeps them all. */
export function shortened(value: number): number {
  return Number(value.toPrecision(6));
}

/** The displayed number a typed text stands for, or null if it is not one within the range. */
export function typedDisplayValue(
  parameter: ParameterDescription,
  text: string,
): number | null {
  const value = parseNumber(text);
  const { minimum, maximum } = parameter.display_range;
  return value !== null && value >= minimum && value <= maximum ? value : null;
}

/** One keyboard step from a displayed value. A step is an increment, not a grid. */
export function steppedDisplayValue(
  parameter: ParameterDescription,
  value: number,
  steps: number,
): number {
  const { minimum, maximum, step } = parameter.display_range;
  return Math.min(maximum, Math.max(minimum, tidy(value + steps * step)));
}
