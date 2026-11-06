import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { apiClient, type CalcRequest, type CalcResponse } from "@/api/client";
import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { calcRequest } from "@/model/liveCurves";
import { useSessionStore } from "@/session/store";

// Until a slider rests, or at the latest at the longer delay, so that a curve follows a long drag.
// The shorter is above 100 ms, as the API allows 10 curves a second. FS12 measures these.
export const DEBOUNCE_MS = 120;
export const MAX_WAIT_MS = 300;
// A quick answer shows no indicator, which would only flicker.
const BUSY_AFTER_MS = 300;
// If a limit asks for longer, the next change tries again anyway.
const MAX_RETRY_AFTER_S = 30;

export interface LiveCurves {
  /** The latest answer, kept through later requests and errors, so that the chart stays. */
  result: CalcResponse | null;
  busy: boolean;
  error: ApiError | null;
}

const NOTHING: LiveCurves = { result: null, busy: false, error: null };

function isAbort(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

/** Curves and RMSE for the current values, from the server. */
export function useLiveCurves(): LiveCurves {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);

  const body = useMemo(
    () =>
      JSON.stringify(
        calcRequest(
          { selection, parameters, data, interpolation },
          models?.models,
        ),
      ),
    [selection, parameters, data, interpolation, models],
  );
  // New interpolated values are on their way, and the old ones are for another range.
  const waiting = interpolation.enabled && interpolation.loading;

  const [live, setLive] = useState(NOTHING);
  // With nothing to ask, the old curve goes at once, and does not return with new data.
  if (body === "null" && live !== NOTHING) {
    setLive(NOTHING);
  }
  const running = useRef<AbortController | null>(null);
  const latestRun = useRef(0);
  const firstChangeAt = useRef<number | null>(null);

  useEffect(() => {
    if (waiting) {
      return undefined;
    }
    if (body === "null") {
      running.current?.abort();
      latestRun.current += 1;
      firstChangeAt.current = null;
      return undefined;
    }

    let retry: ReturnType<typeof setTimeout> | undefined;
    let busy: ReturnType<typeof setTimeout> | undefined;
    const send = () => {
      firstChangeAt.current = null;
      running.current?.abort();
      const controller = new AbortController();
      running.current = controller;
      latestRun.current += 1;
      const run = latestRun.current;
      const isCurrent = () => run === latestRun.current;

      clearTimeout(busy);
      busy = setTimeout(() => {
        if (isCurrent()) {
          setLive((previous) => ({ ...previous, busy: true }));
        }
      }, BUSY_AFTER_MS);

      apiClient
        .postCalc(JSON.parse(body) as CalcRequest, controller.signal)
        .then((result) => {
          if (isCurrent()) {
            clearTimeout(busy);
            setLive({ result, busy: false, error: null });
          }
        })
        .catch((error: unknown) => {
          if (!isCurrent() || isAbort(error)) {
            return;
          }
          clearTimeout(busy);
          const failure =
            error instanceof ApiError
              ? error
              : new ApiError(0, NETWORK_ERROR, "The request failed");
          setLive((previous) => ({
            ...previous,
            busy: false,
            error: failure,
          }));
          if (
            failure.status === 429 &&
            failure.retryAfterS !== null &&
            failure.retryAfterS <= MAX_RETRY_AFTER_S
          ) {
            retry = setTimeout(send, failure.retryAfterS * 1000);
          }
        });
    };

    const now = Date.now();
    firstChangeAt.current ??= now;
    const timer = setTimeout(
      send,
      Math.min(
        DEBOUNCE_MS,
        Math.max(0, MAX_WAIT_MS - (now - firstChangeAt.current)),
      ),
    );
    return () => {
      clearTimeout(timer);
      clearTimeout(retry);
      clearTimeout(busy);
    };
  }, [body, waiting]);

  // Leaving the page ends what is running, and no late answer can come in.
  useEffect(
    () => () => {
      running.current?.abort();
      latestRun.current += 1;
    },
    [],
  );

  return live;
}
