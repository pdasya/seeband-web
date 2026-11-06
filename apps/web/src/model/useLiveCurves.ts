import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { apiClient, type CalcRequest, type CalcResponse } from "@/api/client";
import type { ApiError } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { LatestOnly } from "@/model/latestOnly";
import { calcRequest } from "@/model/liveCurves";
import { useSessionStore } from "@/session/store";

// From the change, which includes the debounce. A quick answer shows no indicator, as it would
// only flicker.
const BUSY_AFTER_MS = 600;

export interface LiveCurves {
  /** The latest answer, kept through later requests and errors, so that the chart stays. */
  result: CalcResponse | null;
  busy: boolean;
  error: ApiError | null;
}

interface Answers {
  result: CalcResponse | null;
  error: ApiError | null;
  /** The values that the last answer or failure ended. */
  settled: string | null;
}

const NOTHING: Answers = { result: null, error: null, settled: null };

/** Curves and RMSE for the current values, from the server. */
export function useLiveCurves(): LiveCurves {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);

  const body = useMemo(() => {
    const request = calcRequest(
      { selection, parameters, data, interpolation },
      models?.models,
    );
    return request === null ? null : JSON.stringify(request);
  }, [selection, parameters, data, interpolation, models]);
  // New interpolated values are on their way, and the old ones are for another range.
  const waiting = interpolation.enabled && interpolation.loading;

  const [answers, setAnswers] = useState(NOTHING);
  // With nothing to ask, the old curve goes at once, and does not return with new data.
  if (body === null && answers !== NOTHING) {
    setAnswers(NOTHING);
  }

  const [sender] = useState(
    () =>
      new LatestOnly<CalcResponse>({
        send: (values, signal) =>
          apiClient.postCalc(JSON.parse(values) as CalcRequest, signal),
        onResult: (result, settled) => {
          setAnswers({ result, error: null, settled });
        },
        onFailure: (error, settled) => {
          setAnswers((previous) => ({ ...previous, error, settled }));
        },
      }),
  );
  useEffect(() => {
    sender.change(body, waiting);
  }, [sender, body, waiting]);
  // Leaving the page ends what is running, and no late answer can come in.
  useEffect(() => () => sender.dispose(), [sender]);

  const pending = body !== null && (waiting || answers.settled !== body);
  const [longPending, setLongPending] = useState(false);
  if (!pending && longPending) {
    setLongPending(false);
  }
  useEffect(() => {
    if (!pending) {
      return undefined;
    }
    const timer = setTimeout(() => {
      setLongPending(true);
    }, BUSY_AFTER_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [pending]);

  return {
    result: answers.result,
    busy: pending && longPending,
    error: answers.error,
  };
}
