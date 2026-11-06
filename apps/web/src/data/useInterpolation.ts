import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { apiClient, type ParseRequest } from "@/api/client";
import { modelsQuery } from "@/api/queries";
import { failureMessage } from "@/data/messages";
import {
  QUANTITIES,
  useSessionStore,
  type InterpolatedQuantities,
  type Quantity,
} from "@/session/store";

// A field being typed in, or a slider, should not send a request for each step, as the API has a
// limit on the rate of these.
const DEBOUNCE_MS = 300;

export interface FitRange {
  minK: number;
  maxK: number;
}

/** The selected fit range, or the default of the models until one is chosen. */
export function useFitRange(): FitRange | null {
  const selected = useSessionStore((state) => state.selection);
  const { data } = useQuery(modelsQuery);
  const model = data?.models[0];
  const minK = selected.minTemperatureK ?? model?.default_min_temperature_k;
  const maxK = selected.maxTemperatureK ?? model?.default_max_temperature_k;
  return minK === undefined || maxK === undefined ? null : { minK, maxK };
}

interface InterpolationRequest {
  body: ParseRequest;
  /** Which quantities to take from its answer. */
  quantities: readonly Quantity[];
}

function requestsFor(range: FitRange): InterpolationRequest[] {
  const { data, dataMode, singleFile } = useSessionStore.getState();
  const interpolate = {
    min_temperature_k: range.minK,
    max_temperature_k: range.maxK,
  };
  if (dataMode === "single") {
    return singleFile === null || singleFile.text === ""
      ? []
      : [
          {
            body: {
              text: singleFile.text,
              mapping: [...singleFile.mapping],
              interpolate,
            },
            quantities: QUANTITIES,
          },
        ];
  }
  return QUANTITIES.flatMap((quantity) => {
    const entry = data[quantity];
    return entry === undefined
      ? []
      : [
          {
            body: { text: entry.text, expected: quantity, interpolate },
            quantities: [quantity],
          },
        ];
  });
}

/**
 * Keeps the interpolated values up to date with the switch, the data and the fit range. The API
 * keeps nothing, so each change asks again. The measured data stay as they are in the store.
 */
export function useInterpolation(range: FitRange | null) {
  const enabled = useSessionStore((state) => state.interpolation.enabled);
  const data = useSessionStore((state) => state.data);
  const finish = useSessionStore((state) => state.finishInterpolation);
  const fail = useSessionStore((state) => state.failInterpolation);
  const start = useSessionStore((state) => state.startInterpolation);
  const minK = range?.minK;
  const maxK = range?.maxK;

  useEffect(() => {
    if (!enabled || minK === undefined || maxK === undefined) {
      return;
    }
    const requests = requestsFor({ minK, maxK });
    if (requests.length === 0) {
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    start();
    const timer = setTimeout(() => {
      Promise.all(
        requests.map(async ({ body, quantities }) => ({
          quantities,
          parsed: await apiClient.postParse(body, signal),
        })),
      ).then(
        (answers) => {
          if (signal.aborted) {
            return;
          }
          const values: InterpolatedQuantities = {};
          const failed: Quantity[] = [];
          for (const { quantities, parsed } of answers) {
            for (const quantity of quantities) {
              const result = parsed.interpolated[quantity];
              if (result !== undefined) {
                values[quantity] = result;
              }
              if (parsed.interpolation_failed.includes(quantity)) {
                failed.push(quantity);
              }
            }
          }
          finish(values, failed);
        },
        (error: unknown) => {
          if (!signal.aborted) {
            fail(failureMessage(error));
          }
        },
      );
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, minK, maxK, data, start, finish, fail]);
}
