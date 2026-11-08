import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient, type CalcResponse } from "@/api/client";
import { modelsQuery } from "@/api/queries";
import {
  dataFile,
  exportHeader,
  graphFile,
  modeLabel,
  parametersFile,
} from "@/model/exportFiles";
import { calcRequest } from "@/model/liveCurves";
import { hasFittedValues, resultIssues } from "@/model/resultSummary";
import { fitModeOf } from "@/model/selection";
import {
  QUANTITIES,
  useSessionStore,
  type SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { export: text } = STRINGS;

/** Hands the user a text file, as a download. */
export function download(name: string, contents: string): void {
  const url = URL.createObjectURL(
    new Blob([contents], { type: "text/plain;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

async function apiVersion(): Promise<string | null> {
  try {
    return (await apiClient.getHealth()).version;
  } catch {
    return null;
  }
}

/** The values a fit started from, so that the curve before it can be drawn again. */
function preFitState(state: SessionState, modeId: string): SessionState {
  const start = state.fitStartValues;
  return hasFittedValues(state.fit) && start !== null
    ? { ...state, parameters: { ...state.parameters, [modeId]: start } }
    : state;
}

/**
 * The exports of the fit and results screens. Each reads the session when pressed, and asks the
 * server for the curves it needs, as the client calculates nothing.
 */
export function useExport() {
  const { data: models } = useQuery(modelsQuery);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const context = async (
    extraIssues: {
      measured?: readonly string[];
      derived?: readonly string[];
    } = {},
  ) => {
    const state = useSessionStore.getState();
    const model = models?.models.find(({ id }) => id === state.selection.model);
    const mode = fitModeOf(model, state.selection.fitMode);
    if (model === undefined || mode === undefined) {
      return null;
    }
    const issues = resultIssues(mode, {
      fit: state.fit.status === "done" ? state.fit.result.known_issues : [],
      measured: extraIssues.measured ?? [],
      derived: extraIssues.derived ?? [],
    });
    const header = exportHeader({
      appVersion: __APP_VERSION__,
      apiVersion: await apiVersion(),
      date: new Date().toISOString(),
      modelId: model.id,
      modeLabel: modeLabel(mode),
      selection: state.selection,
      degeneracy: mode.degeneracy !== null && mode.degeneracy !== undefined,
      fit: state.fit,
      demo: QUANTITIES.some(
        (quantity) => state.data[quantity]?.source.kind === "demo",
      ),
      issues,
    });
    return { state, mode, header };
  };

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setFailed(false);
    try {
      await work();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const calc = async (state: SessionState): Promise<CalcResponse | null> => {
    const request = calcRequest(state, models?.models, true);
    return request === null ? null : apiClient.postCalc(request);
  };

  return {
    busy,
    failed,
    /** Measured data, interpolated values, and the curves before and after the fit. */
    data: () =>
      run(async () => {
        const state = useSessionStore.getState();
        const model = models?.models.find(
          ({ id }) => id === state.selection.model,
        );
        const mode = fitModeOf(model, state.selection.fitMode);
        if (mode === undefined) {
          return;
        }
        const fitted = hasFittedValues(state.fit);
        const [preFit, fit] = await Promise.all([
          calc(preFitState(state, mode.id)),
          fitted ? calc(state) : Promise.resolve(null),
        ]);
        const made = await context({
          measured: [
            ...(preFit?.known_issues ?? []),
            ...(fit?.known_issues ?? []),
          ],
        });
        if (made !== null) {
          download(
            text.dataFile,
            dataFile(made.header, made.mode, made.state, preFit, fit),
          );
        }
      }),
    /** The values in use, with how each was found. */
    parameters: () =>
      run(async () => {
        const made = await context();
        if (made !== null) {
          const { state, mode, header } = made;
          download(
            text.parametersFile,
            parametersFile(
              header,
              mode,
              state.selection,
              state.parameters[mode.id],
              state.fit,
            ),
          );
        }
      }),
    /** One additional graph, from the answers it already drew. */
    graph: (
      name: string,
      temperatureK: readonly number[],
      curves: readonly { name: string; values: readonly (number | null)[] }[],
      issues: readonly string[],
    ) =>
      run(async () => {
        const made = await context({ derived: issues });
        if (made !== null) {
          download(
            text.graphFile(name),
            graphFile(made.header, temperatureK, curves),
          );
        }
      }),
  };
}
