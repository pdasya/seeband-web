import type { CalcRequest } from "@/api/client";
import { parameterValues } from "@/model/parameters";
import { fitModeOf, type ModelDescription } from "@/model/selection";
import {
  fitData,
  type FitData,
  type Quantity,
  type SessionState,
} from "@/session/store";

function pointsInRange(
  data: FitData,
  minK: number,
  maxK: number,
): { temperature: number; value: number }[] {
  return data.temperature_k.flatMap((temperature, index) => {
    const value = data.values[index];
    return temperature >= minK && temperature <= maxK && value !== undefined
      ? [{ temperature, value }]
      : [];
  });
}

// The RMSE of ρ and R_H is a percent of the data, which the API refuses at 0.
function usablePoints(
  data: FitData,
  quantity: Quantity,
  minK: number,
  maxK: number,
) {
  const points = pointsInRange(data, minK, maxK);
  return quantity === "seebeck"
    ? points
    : points.filter(({ value }) => value !== 0);
}

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
  evenWithoutData = false,
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
    (!evenWithoutData &&
      !mode.quantities.some((quantity) => state.data[quantity] !== undefined))
  ) {
    return null;
  }

  const measurements: NonNullable<CalcRequest["measurements"]> = {};
  let extrapolated = false;
  for (const quantity of mode.quantities) {
    const data = fitData(state, quantity);
    const points =
      data === null ? [] : usablePoints(data, quantity, minK, maxK);
    if (data !== null && points.length > 0) {
      measurements[quantity] = {
        temperature_k: points.map(({ temperature }) => temperature),
        values: points.map(({ value }) => value),
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

/** Other curves of the same values. These take no measurements, and need no data. */
export function derivedRequest(
  state: RequestState,
  models: readonly ModelDescription[] | undefined,
  kind: NonNullable<CalcRequest["kind"]>,
): CalcRequest | null {
  const request = calcRequest(state, models, true);
  return (
    request && {
      ...request,
      kind,
      measurements: {},
      extrapolated: false,
    }
  );
}

export interface RmseGaps {
  /** Data are loaded, and no point lies in the fit range. */
  noPointsInRange: Quantity[];
  /** The switch is on, and these have no usable interpolated values. */
  notInterpolated: Quantity[];
  /** Points with a value of 0 were left out of the RMSE. */
  zerosLeftOut: Quantity[];
}

/** Why an RMSE is missing or leaves points out, though data are loaded. */
export function rmseGaps(
  state: RequestState,
  models: readonly ModelDescription[] | undefined,
): RmseGaps {
  const gaps: RmseGaps = {
    noPointsInRange: [],
    notInterpolated: [],
    zerosLeftOut: [],
  };
  const { selection } = state;
  const model = models?.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  const minK = selection.minTemperatureK;
  const maxK = selection.maxTemperatureK;
  if (mode === undefined || minK === null || maxK === null) {
    return gaps;
  }
  for (const quantity of mode.quantities) {
    if (state.data[quantity] === undefined) {
      continue;
    }
    const data = fitData(state, quantity);
    if (data === null) {
      if (!state.interpolation.loading) {
        gaps.notInterpolated.push(quantity);
      }
      continue;
    }
    const inRange = pointsInRange(data, minK, maxK);
    if (inRange.length === 0) {
      gaps.noPointsInRange.push(quantity);
    } else if (
      usablePoints(data, quantity, minK, maxK).length < inRange.length
    ) {
      gaps.zerosLeftOut.push(quantity);
    }
  }
  return gaps;
}
