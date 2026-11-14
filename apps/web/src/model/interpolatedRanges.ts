import type { InterpolationState, Quantity } from "@/session/store";

/** A quantity whose measured range narrowed its interpolation, and the range a fit uses. */
export interface LimitedRange {
  quantity: Quantity;
  minK: number;
  maxK: number;
}

/**
 * The quantities of a mode whose interpolation the measured range narrowed, with the range a fit
 * uses for each, as the fit range alone would claim more. None while values for a new range are on
 * their way, or with interpolation off.
 */
export function limitedRanges(
  interpolation: Pick<InterpolationState, "enabled" | "loading" | "values">,
  quantities: readonly Quantity[],
): LimitedRange[] {
  if (!interpolation.enabled || interpolation.loading) {
    return [];
  }
  return quantities.flatMap((quantity) => {
    const result = interpolation.values[quantity];
    if (result?.range_limited !== true || result.temperature_k.length === 0) {
      return [];
    }
    return [
      {
        quantity,
        minK: Math.min(...result.temperature_k),
        maxK: Math.max(...result.temperature_k),
      },
    ];
  });
}
