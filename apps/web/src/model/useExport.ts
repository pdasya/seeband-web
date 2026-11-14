import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { limitedRanges } from "@/model/interpolatedRanges";

import { apiClient, type CalcResponse } from "@/api/client";
import { modelsQuery } from "@/api/queries";
import { strToU8, zipSync } from "fflate";

import { DERIVED_KINDS_ASKED, ENERGY_IN_K } from "@/model/chartTabs";
import {
  csvFile,
  dataFile,
  exportHeader,
  graphFile,
  modeLabel,
  parametersCsv,
  parametersFile,
  zipEntries,
} from "@/model/exportFiles";
import { calcRequest, derivedRequest } from "@/model/liveCurves";
import { hasFittedValues, resultIssues } from "@/model/resultSummary";
import { fitModeOf } from "@/model/selection";
import {
  QUANTITIES,
  useSessionStore,
  type SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { export: text } = STRINGS;

// Long enough for a browser to take the file before its address is freed.
const RELEASE_AFTER_MS = 60_000;

/** Hands the user a file, as a download. */
export function download(
  name: string,
  contents: string | Uint8Array<ArrayBuffer>,
  type = "text/plain;charset=utf-8",
): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.hidden = true;
  // In the page, and freed later, as Firefox and Safari can drop a download otherwise.
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, RELEASE_AFTER_MS);
}

async function apiVersion(): Promise<string | null> {
  try {
    return (await apiClient.getHealth()).version;
  } catch {
    return null;
  }
}

/**
 * The values a fit started from, so that the curve before it can be drawn again: also while it
 * runs, or after it failed, as each iteration writes its values on screen. A change of values ends
 * a fit's state, so with none the values on screen are those before any fit.
 */
function preFitState(state: SessionState, modeId: string): SessionState {
  const start = state.fitStartValues;
  return state.fit.status !== "idle" && start !== null
    ? { ...state, parameters: { ...state.parameters, [modeId]: start } }
    : state;
}

/**
 * The exports of the fit and results screens. Each reads the session when pressed, and asks the
 * server for the curves it needs, as the client calculates nothing.
 */
export function useExport() {
  const { data: models } = useQuery(modelsQuery);
  const energy = models?.energy_display ?? ENERGY_IN_K;
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  /** The session and its mode as they are now, read once for all of a file. */
  const snapshot = () => {
    const state = useSessionStore.getState();
    const model = models?.models.find(({ id }) => id === state.selection.model);
    const mode = fitModeOf(model, state.selection.fitMode);
    return model === undefined || mode === undefined
      ? null
      : { state, model, mode };
  };

  // From the snapshot the curves were asked for, so that a fit ending or a value changing while
  // the server answers cannot make the header describe another state than the curves.
  const context = async (
    { state, model, mode }: NonNullable<ReturnType<typeof snapshot>>,
    extraIssues: {
      measured?: readonly string[];
      derived?: readonly string[];
    } = {},
  ) => {
    const issues = resultIssues(mode, {
      fit: state.fit.status === "done" ? state.fit.result.known_issues : [],
      measured: extraIssues.measured ?? [],
      derived: extraIssues.derived ?? [],
    });
    const info = {
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
      limitedRanges: limitedRanges(state.interpolation, mode.quantities),
    };
    return { state, mode, header: exportHeader(info) };
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

  /**
   * The curves before and after the fit, and with `withGraphs` each additional kind the mode
   * offers, with the header that names their flags.
   */
  const everything = async (withGraphs: boolean) => {
    const now = snapshot();
    if (now === null) {
      return null;
    }
    const { state, mode } = now;
    const kinds = withGraphs
      ? DERIVED_KINDS_ASKED.filter((kind) =>
          mode.curves.some((curve) => curve.kind === kind && curve.available),
        )
      : [];
    const [preFit, fit, ...answers] = await Promise.all([
      calc(preFitState(state, mode.id)),
      hasFittedValues(state.fit) ? calc(state) : Promise.resolve(null),
      ...kinds.map((kind) => {
        const request = derivedRequest(state, models?.models, kind);
        return request === null ? null : apiClient.postCalc(request);
      }),
    ]);
    const graphs = kinds.flatMap((kind, at) => {
      const result = answers[at];
      return result === null || result === undefined ? [] : [{ kind, result }];
    });
    const missing = kinds.filter(
      (kind) => !graphs.some((graph) => graph.kind === kind),
    );
    const made = await context(now, {
      measured: [...(preFit?.known_issues ?? []), ...(fit?.known_issues ?? [])],
      derived: graphs.flatMap(({ result }) => result.known_issues),
    });
    return { ...made, preFit, fit, graphs, missing };
  };

  const parametersAs = (
    build: typeof parametersFile,
    name: string,
    type?: string,
  ) =>
    run(async () => {
      const now = snapshot();
      if (now !== null) {
        const { state, mode, header } = await context(now);
        download(
          name,
          build(
            header,
            mode,
            state.selection,
            state.parameters[mode.id],
            state.fit,
          ),
          type,
        );
      }
    });

  return {
    busy,
    failed,
    /** Measured data, interpolated values, and the curves before and after the fit. */
    data: () =>
      run(async () => {
        const made = await everything(false);
        if (made !== null) {
          const { header, mode, state, preFit, fit } = made;
          download(text.dataFile, dataFile(header, mode, state, preFit, fit));
        }
      }),
    /** The same points, as one table with a row each. */
    csv: () =>
      run(async () => {
        const made = await everything(false);
        if (made !== null) {
          const { header, mode, state, preFit, fit } = made;
          download(
            text.csvFile,
            csvFile(header, mode, state, preFit, fit),
            "text/csv;charset=utf-8",
          );
        }
      }),
    /** A file for each part, in one ZIP, with the additional graphs. */
    zip: () =>
      run(async () => {
        const made = await everything(true);
        if (made !== null) {
          const { header, mode, state, preFit, fit, graphs, missing } = made;
          const entries = zipEntries(
            header,
            mode,
            state,
            preFit,
            fit,
            parametersFile(
              header,
              mode,
              state.selection,
              state.parameters[mode.id],
              state.fit,
            ),
            graphs,
            energy,
            missing,
          );
          download(
            text.zipFile,
            zipSync(
              Object.fromEntries(
                Object.entries(entries).map(([name, contents]) => [
                  name,
                  strToU8(contents),
                ]),
              ),
            ) as Uint8Array<ArrayBuffer>,
            "application/zip",
          );
        }
      }),
    /** The values in use, with how each was found, as text. */
    parameters: () => parametersAs(parametersFile, text.parametersFile),
    /** The same, as a CSV. */
    parametersCsv: () =>
      parametersAs(
        parametersCsv,
        text.parametersCsvFile,
        "text/csv;charset=utf-8",
      ),
    /** One additional graph, from the answers it already drew. */
    graph: (
      name: string,
      temperatureK: readonly number[],
      curves: readonly { name: string; values: readonly (number | null)[] }[],
      issues: readonly string[],
    ) =>
      run(async () => {
        const now = snapshot();
        if (now !== null) {
          const { header } = await context(now, { derived: issues });
          download(
            text.graphFile(name),
            graphFile(header, temperatureK, curves, energy),
          );
        }
      }),
  };
}
