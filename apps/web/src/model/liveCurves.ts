import type { CalcRequest } from "@/api/client";
import { parameterValues } from "@/model/parameters";
import { fitModeOf, type ModelDescription } from "@/model/selection";
import { fitData, type SessionState } from "@/session/store";

/** What the chart's axis shows, from the core's V/K. */
const MICROVOLT_PER_VOLT = 1e6;

export function toMicrovoltPerK(
  values: readonly (number | null)[],
): (number | null)[] {
  return values.map((value) =>
    value === null ? null : value * MICROVOLT_PER_VOLT,
  );
}

export const SEEBECK_CURVE = "seebeck_v_per_k";

type RequestState = Pick<
  SessionState,
  "selection" | "parameters" | "data" | "interpolation"
>;

/**
 * The curves to ask for, or null where there is nothing to ask: no data for this fit mode, or no
 * mode that can run. Measurements hold only points in the fit range, as the API asks.
 */
export function calcRequest(
  state: RequestState,
  models: readonly ModelDescription[] | undefined,
): CalcRequest | null {
  const { selection } = state;
  const model = models?.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  const minK = selection.minTemperatureK;
  const maxK = selection.maxTemperatureK;
  if (
    model === undefined ||
    mode === undefined ||
    mode.disabled ||
    minK === null ||
    maxK === null ||
    !mode.quantities.some((quantity) => state.data[quantity] !== undefined)
  ) {
    return null;
  }

  const measurements: NonNullable<CalcRequest["measurements"]> = {};
  let extrapolated = false;
  for (const quantity of mode.quantities) {
    const data = fitData(state, quantity);
    if (data === null) {
      continue;
    }
    const inRange = data.temperature_k.flatMap((temperature, index) => {
      const value = data.values[index];
      return temperature >= minK && temperature <= maxK && value !== undefined
        ? [{ temperature, value }]
        : [];
    });
    if (inRange.length > 0) {
      measurements[quantity] = {
        temperature_k: inRange.map(({ temperature }) => temperature),
        values: inRange.map(({ value }) => value),
      };
      extrapolated ||= data.extrapolated;
    }
  }

  return {
    model: model.id,
    fit_mode: mode.id,
    scattering: selection.scattering,
    parameters: parameterValues(mode, state.parameters[mode.id]),
    min_temperature_k: minK,
    max_temperature_k: maxK,
    band_1_degeneracy: selection.band1Degeneracy,
    band_2_degeneracy: selection.band2Degeneracy,
    extrapolated,
    measurements,
  };
}
