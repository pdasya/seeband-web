import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  apiClient,
  type BandDiagramRequest,
  type BandDiagramResponse,
  type CalcRequest,
  type CalcResponse,
} from "@/api/client";
import type { ApiError } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { derivedKind, needsMeasuredCurves } from "@/model/chartTabs";
import { LatestOnly } from "@/model/latestOnly";
import {
  bandDiagramRequest,
  bandDiagramScope,
  calcRequest,
  derivedRequest,
  requestScope,
} from "@/model/liveCurves";
import { fitModeOf } from "@/model/selection";
import { useSessionStore } from "@/session/store";

// From the change, which includes the debounce. A quick answer shows no indicator, as it would
// only flicker.
const BUSY_AFTER_MS = 600;

export interface LiveCalc<Result = CalcResponse> {
  /** The latest answer, kept through later requests and errors, so that the chart stays. */
  result: Result | null;
  busy: boolean;
  error: ApiError | null;
}

export interface LiveCurves {
  /** The curves that measurements go with, and their RMSE. */
  measured: LiveCalc;
  /** The curves that the open tab needs on top of those. */
  derived: LiveCalc;
  /** The sketch of the bands, while its tab is open. */
  diagram: LiveCalc<BandDiagramResponse>;
}

interface Answers<Result> {
  result: Result | null;
  resultScope: string | null;
  error: ApiError | null;
  errorScope: string | null;
  /** The values that the last answer or failure ended. */
  settled: string | null;
}

const NOTHING: Answers<never> = {
  result: null,
  resultScope: null,
  error: null,
  errorScope: null,
  settled: null,
};

/** What to send a request's body with, and what its answer is of. */
interface Route<Result> {
  send: (body: string, signal: AbortSignal) => Promise<Result>;
  scopeOf: (body: string) => string;
}

const CALC: Route<CalcResponse> = {
  send: (body, signal) =>
    apiClient.postCalc(JSON.parse(body) as CalcRequest, signal),
  scopeOf: (body) => requestScope(JSON.parse(body) as CalcRequest),
};

const BAND_DIAGRAM: Route<BandDiagramResponse> = {
  send: (body, signal) =>
    apiClient.postBandDiagram(JSON.parse(body) as BandDiagramRequest, signal),
  scopeOf: (body) => bandDiagramScope(JSON.parse(body) as BandDiagramRequest),
};

/** One request at a time for these values, with the state to show while it lasts. */
function useLatest<Result>(
  route: Route<Result>,
  body: string | null,
  scope: string | null,
  waiting: boolean,
): LiveCalc<Result> {
  const [answers, setAnswers] = useState<Answers<Result>>(NOTHING);
  // With nothing to ask, the old curve goes at once, and does not return with new data.
  if (body === null && answers !== NOTHING) {
    setAnswers(NOTHING);
  }

  const [sender] = useState(
    () =>
      new LatestOnly<Result>({
        send: route.send,
        onResult: (result, settled) => {
          setAnswers({
            result,
            resultScope: route.scopeOf(settled),
            error: null,
            errorScope: null,
            settled,
          });
        },
        onFailure: (error, settled, sent) => {
          setAnswers((previous) => ({
            ...previous,
            error,
            errorScope: route.scopeOf(sent),
            settled,
          }));
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
    result: answers.resultScope === scope ? answers.result : null,
    busy: pending && longPending,
    error: answers.errorScope === scope ? answers.error : null,
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

  const {
    measuredBody,
    measuredScope,
    derivedBody,
    derivedScope,
    diagramBody,
    diagramScope,
  } = useMemo(() => {
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
    const diagram =
      tab === "band_diagram" ? bandDiagramRequest(state, models?.models) : null;
    return {
      measuredBody: measured && JSON.stringify(measured),
      measuredScope: measured && requestScope(measured),
      derivedBody: derived && JSON.stringify(derived),
      derivedScope: derived && requestScope(derived),
      diagramBody: diagram && JSON.stringify(diagram),
      diagramScope: diagram && bandDiagramScope(diagram),
    };
  }, [selection, parameters, data, interpolation, models, tab]);
  // New interpolated values are on their way, and the old ones are for another range.
  const waiting = interpolation.enabled && interpolation.loading;

  return {
    measured: useLatest(CALC, measuredBody, measuredScope, waiting),
    derived: useLatest(CALC, derivedBody, derivedScope, false),
    diagram: useLatest(BAND_DIAGRAM, diagramBody, diagramScope, false),
  };
}
