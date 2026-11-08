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
    // With no data, a table has errors, or is on its way, and an answer could only be empty.
    return singleFile === null || Object.keys(data).length === 0
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
            // A user's choice of columns goes again, or the server would guess anew.
            body:
              entry.mapping === undefined
                ? { text: entry.text, expected: quantity, interpolate }
                : {
                    text: entry.text,
                    mapping: [...entry.mapping],
                    interpolate,
                  },
            quantities: [quantity],
          },
        ];
  });
}

/**
 * Keeps the interpolated values up to date with the switch, the data and the fit range. The API
 * keeps nothing, so each change asks again. The measured data stay as they are in the store.
 *
 * It runs in the app's shell rather than the data panel, so that moving between screens neither
 * sends requests again nor stops following a change.
 */
export function useInterpolation() {
  const range = useFitRange();
  const enabled = useSessionStore((state) => state.interpolation.enabled);
  const data = useSessionStore((state) => state.data);
  const start = useSessionStore((state) => state.startInterpolation);
  const stop = useSessionStore((state) => state.stopInterpolation);
  const finish = useSessionStore((state) => state.finishInterpolation);
  const minK = range?.minK;
  const maxK = range?.maxK;

  useEffect(() => {
    const requests =
      enabled && minK !== undefined && maxK !== undefined
        ? requestsFor({ minK, maxK })
        : [];
    if (requests.length === 0) {
      // A request stopped by this change must not leave the panel waiting for it.
      stop();
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    start();
    const timer = setTimeout(() => {
      void Promise.allSettled(
        requests.map(({ body }) => apiClient.postParse(body, signal)),
      ).then((answers) => {
        if (signal.aborted) {
          return;
        }
        const values: InterpolatedQuantities = {};
        const failed: Quantity[] = [];
        let failure: string | null = null;
        answers.forEach((answer, index) => {
          const quantities = requests[index]?.quantities ?? [];
          if (answer.status === "rejected") {
            // One file's failure leaves the others, and the flags name it.
            failed.push(...quantities);
            failure ??= failureMessage(answer.reason);
            return;
          }
          for (const quantity of quantities) {
            const result = answer.value.interpolated[quantity];
            if (result !== undefined) {
              values[quantity] = result;
            }
            if (answer.value.interpolation_failed.includes(quantity)) {
              failed.push(quantity);
            }
          }
        });
        finish(values, failed, failure);
      });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, minK, maxK, data, start, stop, finish]);
}
