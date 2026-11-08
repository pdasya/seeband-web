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
import {
  derivedKind,
  needsMeasuredCurves,
  type DerivedKind,
} from "@/model/chartTabs";
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
  /** Other curves, of each kind that a chart shows. */
  derived: Record<DerivedKind, LiveCalc>;
  /** The sketch of the bands, while a chart shows it. */
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

type DerivedRequests = Record<
  DerivedKind,
  { body: string | null; scope: string | null }
>;

/** The latest answer for each kind of curve, asked in a fixed order, as hooks must be. */
function useDerivedCurves(
  requests: DerivedRequests,
): Record<DerivedKind, LiveCalc> {
  const {
    chemical_potential: chemical,
    seebeck_by_band: bands,
    electrical_conductivity: electrical,
    thermal_conductivity: thermal,
    carrier_concentration_by_band: carriers,
  } = requests;
  return {
    chemical_potential: useLatest(CALC, chemical.body, chemical.scope, false),
    seebeck_by_band: useLatest(CALC, bands.body, bands.scope, false),
    electrical_conductivity: useLatest(
      CALC,
      electrical.body,
      electrical.scope,
      false,
    ),
    thermal_conductivity: useLatest(CALC, thermal.body, thermal.scope, false),
    carrier_concentration_by_band: useLatest(
      CALC,
      carriers.body,
      carriers.scope,
      false,
    ),
  };
}

/** Curves and RMSE for the current values, from the server. */
export function useLiveCurves(): LiveCurves {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const panels = useSessionStore((state) => state.chartPanels);

  // Each kind of curve is asked for once, whichever charts show it, and only while one does.
  const { measured, derived, diagram } = useMemo(() => {
    const state = { selection, parameters, data, interpolation };
    const model = models?.models.find(({ id }) => id === selection.model);
    const mode = fitModeOf(model, selection.fitMode);
    const measuredRequest = calcRequest(
      state,
      models?.models,
      panels.some((tab) => needsMeasuredCurves(tab, mode)),
    );
    const asked = new Set(panels.map((tab) => derivedKind(tab, mode)));
    const derivedOf = (kind: DerivedKind) => {
      const request = asked.has(kind)
        ? derivedRequest(state, models?.models, kind)
        : null;
      return {
        body: request && JSON.stringify(request),
        scope: request && requestScope(request),
      };
    };
    const diagramRequest = panels.includes("band_diagram")
      ? bandDiagramRequest(state, models?.models)
      : null;
    return {
      measured: {
        body: measuredRequest && JSON.stringify(measuredRequest),
        scope: measuredRequest && requestScope(measuredRequest),
      },
      derived: {
        chemical_potential: derivedOf("chemical_potential"),
        seebeck_by_band: derivedOf("seebeck_by_band"),
        electrical_conductivity: derivedOf("electrical_conductivity"),
        thermal_conductivity: derivedOf("thermal_conductivity"),
        carrier_concentration_by_band: derivedOf(
          "carrier_concentration_by_band",
        ),
      },
      diagram: {
        body: diagramRequest && JSON.stringify(diagramRequest),
        scope: diagramRequest && bandDiagramScope(diagramRequest),
      },
    };
  }, [selection, parameters, data, interpolation, models, panels]);
  // New interpolated values are on their way, and the old ones are for another range.
  const waiting = interpolation.enabled && interpolation.loading;

  return {
    measured: useLatest(CALC, measured.body, measured.scope, waiting),
    derived: useDerivedCurves(derived),
    diagram: useLatest(BAND_DIAGRAM, diagram.body, diagram.scope, false),
  };
}

/**
 * Curves for a summary of a fit: the measured ones, with their RMSE and the total of S, and each
 * other kind the mode offers. With `enabled` false it asks for nothing.
 */
export function useResultCurves(enabled: boolean): {
  measured: LiveCalc;
  derived: Record<DerivedKind, LiveCalc>;
} {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const requests = useMemo(() => {
    const state = { selection, parameters, data, interpolation };
    const model = models?.models.find(({ id }) => id === selection.model);
    const mode = fitModeOf(model, selection.fitMode);
    const of = (request: CalcRequest | null) => ({
      body: request && JSON.stringify(request),
      scope: request && requestScope(request),
    });
    const derivedOf = (kind: DerivedKind) =>
      of(
        enabled &&
          mode?.curves.some((curve) => curve.kind === kind && curve.available)
          ? derivedRequest(state, models?.models, kind)
          : null,
      );
    return {
      measured: of(enabled ? calcRequest(state, models?.models, true) : null),
      chemical_potential: derivedOf("chemical_potential"),
      seebeck_by_band: derivedOf("seebeck_by_band"),
      electrical_conductivity: derivedOf("electrical_conductivity"),
      thermal_conductivity: derivedOf("thermal_conductivity"),
      carrier_concentration_by_band: derivedOf("carrier_concentration_by_band"),
    };
  }, [enabled, selection, parameters, data, interpolation, models]);
  const waiting = interpolation.enabled && interpolation.loading;
  return {
    measured: useLatest(
      CALC,
      requests.measured.body,
      requests.measured.scope,
      waiting,
    ),
    derived: useDerivedCurves(requests),
  };
}
