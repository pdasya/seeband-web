import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { apiClient, type CalcRequest, type CalcResponse } from "@/api/client";
import type { ApiError } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { derivedKind, needsMeasuredCurves } from "@/model/chartTabs";
import { LatestOnly } from "@/model/latestOnly";
import { calcRequest, derivedRequest } from "@/model/liveCurves";
import { fitModeOf } from "@/model/selection";
import { useSessionStore } from "@/session/store";

// From the change, which includes the debounce. A quick answer shows no indicator, as it would
// only flicker.
const BUSY_AFTER_MS = 600;

export interface LiveCalc {
  /** The latest answer, kept through later requests and errors, so that the chart stays. */
  result: CalcResponse | null;
  busy: boolean;
  error: ApiError | null;
}

export interface LiveCurves {
  /** The curves that measurements go with, and their RMSE. */
  measured: LiveCalc;
  /** The curves that the open tab needs on top of those. */
  derived: LiveCalc;
}

interface Answers {
  result: CalcResponse | null;
  error: ApiError | null;
  /** The values that the last answer or failure ended. */
  settled: string | null;
}

const NOTHING: Answers = { result: null, error: null, settled: null };

/** One request at a time for these values, with the state to show while it lasts. */
function useLatestCalc(body: string | null, waiting: boolean): LiveCalc {
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

  // While interpolated values are on their way, the request has no measurements, so it differs too.
  const pending = body !== null && answers.settled !== body;
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

/** Curves and RMSE for the current values, from the server. */
export function useLiveCurves(): LiveCurves {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const tab = useSessionStore((state) => state.chartTab);

  const { measuredBody, derivedBody } = useMemo(() => {
    const state = { selection, parameters, data, interpolation };
    const model = models?.models.find(({ id }) => id === selection.model);
    const mode = fitModeOf(model, selection.fitMode);
    const measured = calcRequest(
      state,
      models?.models,
      needsMeasuredCurves(tab, mode),
    );
    const kind = derivedKind(tab, mode);
    const derived =
      kind === null ? null : derivedRequest(state, models?.models, kind);
    return {
      measuredBody: measured === null ? null : JSON.stringify(measured),
      derivedBody: derived === null ? null : JSON.stringify(derived),
    };
  }, [selection, parameters, data, interpolation, models, tab]);
  // New interpolated values are on their way, and the old ones are for another range.
  const waiting = interpolation.enabled && interpolation.loading;

  return {
    measured: useLatestCalc(measuredBody, waiting),
    derived: useLatestCalc(derivedBody, false),
  };
}
