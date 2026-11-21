import type { components } from "@seeband/api-client";

import { parseNumber } from "@/lib/numbers";
import type { FitModeDescription } from "@/model/selection";
import type { Selection } from "@/session/store";
import { STRINGS } from "@/strings";

export type ParameterDescription = components["schemas"]["ParameterResponse"];
export type FitBounds = components["schemas"]["BoundsInput"];

/** Core-unit limits for manual exploration, independent of joint fit bounds. */
export type ExplorationDomain = {
  lower?: number;
  upper?: number;
  inclusive: boolean;
};

export function inExplorationDomain(
  value: number,
  domain?: ExplorationDomain,
): boolean {
  return (
    Number.isFinite(value) &&
    (domain === undefined ||
      ((domain.lower === undefined ||
        (domain.inclusive ? value >= domain.lower : value > domain.lower)) &&
        (domain.upper === undefined ||
          (domain.inclusive ? value <= domain.upper : value < domain.upper))))
  );
}

/** Keep the usual conversion, but never round a valid typed value onto an excluded edge. */
export function explorationCoreValue(
  parameter: ParameterDescription,
  displayed: number,
  domain?: ExplorationDomain,
): number | null {
  const converted = displayToCore(parameter, displayed);
  const raw = scaled(
    displayed / parameter.display_factor,
    parameter.fit_scale / parameter.display_scale,
  );
  if (domain !== undefined) {
    // A displayed endpoint selects the exact server value, even when a round trip
    // through eV would move EF just to one side of compensation.
    for (const edge of [domain.lower, domain.upper]) {
      if (edge === undefined || !Number.isFinite(edge)) continue;
      const displayEdge = coreToDisplay(parameter, edge);
      if (displayed === displayEdge || displayed === tidy(displayEdge)) {
        return domain.inclusive ? edge : null;
      }
    }
    const displayDomain = {
      ...(domain.lower === undefined
        ? {}
        : { lower: coreToDisplay(parameter, domain.lower) }),
      ...(domain.upper === undefined
        ? {}
        : { upper: coreToDisplay(parameter, domain.upper) }),
      inclusive: domain.inclusive,
    };
    if (!inExplorationDomain(displayed, displayDomain)) return null;
  }
  return inExplorationDomain(converted, domain)
    ? converted
    : inExplorationDomain(raw, domain)
      ? raw
      : null;
}

/** Slider grid remains anchored to the saved range; narrow ranges retain valid endpoints. */
export function explorationSliderRange(
  parameter: ParameterDescription,
  domain?: ExplorationDomain,
): { minimum: number; maximum: number } | null {
  const { minimum, maximum } = parameter.display_range;
  if (domain === undefined) return { minimum, maximum };
  const step =
    parameter.display_factor === 1
      ? parameter.display_scale
      : parameter.display_range.step;
  const valid = (value: number) =>
    value >= minimum &&
    value <= maximum &&
    explorationCoreValue(parameter, value, domain) !== null;
  let lower = minimum;
  let upper = maximum;
  if (!valid(lower)) {
    const edge = coreToDisplay(parameter, domain.lower ?? -Infinity);
    const index = Math.max(0, Math.ceil((edge - minimum) / step));
    lower = tidy(minimum + index * step);
    if (!valid(lower)) lower = tidy(minimum + (index + 1) * step);
    if (!valid(lower)) lower = maximum;
  }
  if (!valid(upper)) {
    const edge = coreToDisplay(parameter, domain.upper ?? Infinity);
    const index = Math.floor((edge - minimum) / step);
    upper = tidy(minimum + index * step);
    if (!valid(upper)) upper = tidy(minimum + (index - 1) * step);
    if (!valid(upper)) upper = minimum;
  }
  return valid(lower) && valid(upper) && lower <= upper
    ? { minimum: lower, maximum: upper }
    : null;
}

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
  const chosen = scattering ?? mode.default_scattering;
  return mode.parameters.filter(
    (parameter) =>
      mode.scattering.length === 0 ||
      parameter.scattering.length === 0 ||
      (chosen != null && parameter.scattering.includes(chosen)),
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

export type ParameterSelection = Pick<
  Selection,
  "parameterization" | "bandConfiguration" | "carrierType"
>;

/** Every parameter in core units. Virgin E_F starts follow the selected bands; stored values win. */
export function parameterValues(
  mode: FitModeDescription,
  saved: Readonly<Record<string, number>> | undefined,
  selection?: ParameterSelection,
): Record<string, number> {
  const values = Object.fromEntries(
    mode.parameters.map((parameter) => [
      parameter.name,
      saved?.[parameter.name] ?? parameter.core_range.default,
    ]),
  );
  if (
    selection?.parameterization === "explicit_fermi_v1" &&
    saved?.fermi_energy === undefined
  ) {
    const energy = mode.parameters.find(({ name }) => name === "fermi_energy");
    const offset =
      mode.band_2_edge == null ? undefined : values[mode.band_2_edge];
    if (energy !== undefined && offset !== undefined) {
      // Initial suggestions only: the server validates carrier populations and all fitted states.
      const scale =
        Math.abs(energy.core_range.default) || energy.core_range.step;
      const low = Math.min(0, offset);
      const high = Math.max(0, offset);
      values.fermi_energy =
        selection.bandConfiguration === "cb_cb"
          ? low + scale
          : selection.bandConfiguration === "vb_vb"
            ? high - scale
            : selection.carrierType === "n"
              ? high + scale
              : low - scale;
    }
  }
  return values;
}

// As the core converts: dividing where a scale is a fraction, which keeps the last bit.
function scaled(value: number, scale: number): number {
  return scale > 0 && scale < 1 ? value / Math.round(1 / scale) : value * scale;
}

export function coreToDisplay(
  parameter: ParameterDescription,
  value: number,
): number {
  const inControl =
    parameter.display_scale === parameter.fit_scale
      ? value
      : scaled(value, parameter.display_scale / parameter.fit_scale);
  // To the unit a user sees, such as eV for an energy in K.
  return parameter.display_factor === 1
    ? inControl
    : inControl * parameter.display_factor;
}

/**
 * Tidied where the scales differ, so 2.55 at a display scale of 0.01 and a fit scale of 1 gives 255,
 * as the desktop's slider sends, where 2.55 * 100 is 254.99999999999997.
 */
export function displayToCore(
  parameter: ParameterDescription,
  value: number,
): number {
  // Tidied as below, so that an energy shown in eV comes back to the same whole kelvin.
  const inControl =
    parameter.display_factor === 1
      ? value
      : tidy(value / parameter.display_factor);
  return parameter.display_scale === parameter.fit_scale
    ? inControl
    : tidy(scaled(inControl, parameter.fit_scale / parameter.display_scale));
}

/** A displayed number, without the noise of binary fractions such as 1.1500000000000001. */
export function tidy(value: number): number {
  return Number(value.toPrecision(12));
}

/**
 * A displayed value as the screen shows it: an energy in eV to its step, 0.01 eV, as more digits
 * say nothing a user can set, and any other value shortened. The session keeps every digit.
 */
export function shownValue(
  parameter: ParameterDescription,
  value: number,
): number {
  if (parameter.display_factor === 1) {
    return shortened(value);
  }
  const decimals = Math.max(
    0,
    -Math.floor(Math.log10(parameter.display_range.step)),
  );
  // Adding 0 turns -0 into 0, so that no "-0" shows.
  return Number(value.toFixed(decimals)) + 0;
}

/**
 * Whether a typed number is what a field shows for a value, such as 0,12 for a fitted 1234.567 K,
 * so that leaving a field as it is changes nothing, to the last bit.
 */
export function isShownValue(
  parameter: ParameterDescription,
  displayed: number,
  typed: number,
): boolean {
  return typed === displayed || typed === shownValue(parameter, displayed);
}

/** What a field shows, as a fit's value has more digits than fit. The session keeps them all. */
export function shortened(value: number): number {
  return Number(value.toPrecision(6));
}

/** The displayed number a typed text stands for, or null if it is not one within the range. */
export function typedDisplayValue(
  parameter: ParameterDescription,
  text: string,
  domain?: ExplorationDomain,
): number | null {
  const value = parseNumber(text);
  const { minimum, maximum } = parameter.display_range;
  // Bounds as the screen shows them, so that a bound typed as shown counts, as that bound.
  return value !== null &&
    explorationCoreValue(parameter, value, domain) !== null &&
    value >= Math.min(minimum, shownValue(parameter, minimum)) &&
    value <= Math.max(maximum, shownValue(parameter, maximum))
    ? Math.min(maximum, Math.max(minimum, value))
    : null;
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
