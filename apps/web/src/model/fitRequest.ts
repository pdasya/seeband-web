import type { FitRequest } from "@/api/client";
import {
  editableParameters,
  parameterValues,
  visibleParameters,
} from "@/model/parameters";
import { fitModeOf, type ModelDescription } from "@/model/selection";
import { fitData, type Quantity, type SessionState } from "@/session/store";

type FitInputs = Pick<
  SessionState,
  | "selection"
  | "parameters"
  | "data"
  | "interpolation"
  | "customBounds"
  | "held"
>;

/** Why a fit cannot start, for a text that names the quantities. */
export type FitBlocker =
  | { reason: "no_mode" }
  | { reason: "missing_data"; quantities: Quantity[] }
  | { reason: "interpolating" }
  | { reason: "not_interpolated"; quantities: Quantity[] }
  | { reason: "no_points_in_range"; quantities: Quantity[] }
  | { reason: "all_held" }
  | { reason: "start_outside_bounds"; parameters: string[] };

/** Blockers that come from the request as it is, and so before it is built. */
type InputBlocker = Exclude<FitBlocker, { reason: "start_outside_bounds" }>;

/** A request for the current values, or why there can be none. */
export function fitRequest(
  state: FitInputs,
  models: readonly ModelDescription[] | undefined,
): { request: FitRequest } | { blocked: InputBlocker } {
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
    maxK === null
  ) {
    return { blocked: { reason: "no_mode" } };
  }

  const quantities = mode.quantities;
  const missing = quantities.filter((q) => state.data[q] === undefined);
  if (missing.length > 0) {
    return { blocked: { reason: "missing_data", quantities: missing } };
  }
  if (state.interpolation.enabled && state.interpolation.loading) {
    return { blocked: { reason: "interpolating" } };
  }

  const measurements: FitRequest["measurements"] = {};
  const notInterpolated: Quantity[] = [];
  const noPoints: Quantity[] = [];
  let extrapolated = false;
  for (const quantity of quantities) {
    const data = fitData(state, quantity);
    if (data === null) {
      notInterpolated.push(quantity);
    } else if (!data.temperature_k.some((t) => t >= minK && t <= maxK)) {
      noPoints.push(quantity);
    } else {
      // The API takes only the points in the range into the fit.
      measurements[quantity] = {
        temperature_k: [...data.temperature_k],
        values: [...data.values],
      };
      extrapolated ||= data.extrapolated;
    }
  }
  if (notInterpolated.length > 0) {
    return {
      blocked: { reason: "not_interpolated", quantities: notInterpolated },
    };
  }
  if (noPoints.length > 0) {
    return { blocked: { reason: "no_points_in_range", quantities: noPoints } };
  }

  // Held parameters of another scattering type are not fitted, so the request leaves them out.
  const fitted = visibleParameters(mode, selection.scattering)
    .filter(({ role }) => role === "fitted")
    .map(({ name }) => name);
  const held = (state.held[mode.id] ?? []).filter((name) =>
    fitted.includes(name),
  );
  if (fitted.length > 0 && held.length === fitted.length) {
    return { blocked: { reason: "all_held" } };
  }

  const custom = state.customBounds[mode.id] ?? {};
  const bounds = Object.fromEntries(
    editableParameters(mode, selection.scattering).flatMap(({ parameter }) => {
      const chosen = custom[parameter.name];
      return chosen === undefined ? [] : [[parameter.name, chosen] as const];
    }),
  );

  return {
    request: {
      model: model.id,
      fit_mode: mode.id,
      scattering: selection.scattering,
      start: parameterValues(mode, state.parameters[mode.id]),
      ...(Object.keys(bounds).length === 0 ? {} : { bounds }),
      ...(held.length === 0 ? {} : { held }),
      min_temperature_k: minK,
      max_temperature_k: maxK,
      band_1_degeneracy: selection.band1Degeneracy,
      band_2_degeneracy: selection.band2Degeneracy,
      extrapolated,
      measurements,
    },
  };
}

/**
 * What a request starts outside the bounds the user set. It is separate from the request because it
 * is about values, which a fit moves as it runs: with N2/N1 other than 1 they can read past the
 * bounds (D12), and that must not look like a change of what is being fitted. A start outside the
 * description's own bounds is for the API to report.
 */
export function startsOutsideBounds(request: FitRequest): string[] {
  return Object.entries(request.bounds ?? {}).flatMap(
    ([name, { lower, upper }]) => {
      const value = request.start[name];
      return value !== undefined && (value < lower || value > upper)
        ? [name]
        : [];
    },
  );
}

/**
 * What a running fit depends on. Its start values are not part of this, as the fit itself moves
 * them, and a change to anything else makes it a fit of something no longer on screen.
 */
export function fitInputsKey(request: FitRequest): string {
  return JSON.stringify({ ...request, start: undefined });
}
