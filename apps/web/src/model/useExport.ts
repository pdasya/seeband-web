import { useState } from "react";
import { limitedRanges } from "@/model/interpolatedRanges";

import { apiClient, type CalcRequest, type CalcResponse } from "@/api/client";
import { ApiError } from "@/api/errors";
import { APP_VERSION, withCommit } from "@/lib/version";
import { useModels } from "@/api/queries";
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
import { retriesByItself } from "@/model/latestOnly";
import { recordedHolds, runLines } from "@/model/runRecord";
import { fitRequest } from "@/model/fitRequest";
import { sessionFile } from "@/session/sessionFile";
import { hasFittedValues, resultIssues } from "@/model/resultSummary";
import { fitModeOf } from "@/model/selection";
import {
  loadedAs,
  QUANTITIES,
  useSessionStore,
  type SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { export: text } = STRINGS;

// Long enough for a browser to take the file before its address is freed.
const RELEASE_AFTER_MS = 60_000;

/** Temporary admission failures can outlive a live curve; an export must still finish or fail. */
async function exportCalc(request: CalcRequest): Promise<CalcResponse> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await apiClient.postCalc(request);
    } catch (error) {
      if (
        attempt >= 2 ||
        !(error instanceof ApiError) ||
        !retriesByItself(error)
      ) {
        throw error;
      }
      await new Promise((resolve) =>
        setTimeout(resolve, (error.retryAfterS ?? 0) * 1000),
      );
    }
  }
}

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

async function serverVersions() {
  try {
    return await apiClient.getHealth();
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
  const { data: models } = useModels();
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
      coreVersions?: readonly (string | undefined)[];
      /**
       * The curve whose RMSE the file names: the fitted one, or that of the values in use, or
       * "failed" if asking for it failed.
       */
      curve?: CalcResponse | "failed" | null;
    } = {},
  ) => {
    const issues = resultIssues(mode, {
      fit: state.fit.status === "done" ? state.fit.result.known_issues : [],
      measured: extraIssues.measured ?? [],
      derived: extraIssues.derived ?? [],
    });
    const server = await serverVersions();
    const info = {
      appVersion: APP_VERSION,
      apiVersion:
        server === null ? null : withCommit(server.version, server.commit),
      serverCoreVersion: server?.core_version ?? null,
      curveCoreVersions: extraIssues.coreVersions ?? [],
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
      fromConductivity:
        mode.quantities.includes("resistivity") &&
        loadedAs("resistivity", state.data.resistivity) === "conductivity",
      run: runLines(
        state,
        mode,
        extraIssues.curve === "failed"
          ? "failed"
          : (extraIssues.curve?.rmse ?? null),
        hasFittedValues(state.fit),
      ),
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

  /** The session as the text of a session file. */
  const sessionText = async (state: SessionState) => {
    const server = await serverVersions();
    const file = await sessionFile(
      state,
      {
        appVersion: APP_VERSION,
        apiVersion:
          server === null ? null : withCommit(server.version, server.commit),
        saved: new Date().toISOString(),
      },
      (inputs) => {
        const built = fitRequest(inputs, models?.models);
        return "request" in built ? built.request : null;
      },
    );
    return `${JSON.stringify(file, null, 1)}\n`;
  };

  const calc = async (state: SessionState): Promise<CalcResponse | null> => {
    const request = calcRequest(state, models?.models);
    return request === null ? null : exportCalc(request);
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
    // Results also asks for live curves. Keep the export to one slot rather than submitting
    // every graph at once and exceeding the API's per-client calculation admission limit.
    const preFit = await calc(preFitState(state, mode.id));
    const fit = hasFittedValues(state.fit) ? await calc(state) : null;
    const graphs: { kind: string; result: CalcResponse }[] = [];
    for (const kind of kinds) {
      const request = derivedRequest(state, models?.models, kind);
      if (request !== null) {
        graphs.push({ kind, result: await exportCalc(request) });
      }
    }
    const missing = kinds.filter(
      (kind) => !graphs.some((graph) => graph.kind === kind),
    );
    const made = await context(now, {
      measured: [...(preFit?.known_issues ?? []), ...(fit?.known_issues ?? [])],
      derived: graphs.flatMap(({ result }) => result.known_issues),
      coreVersions: [preFit, fit, ...graphs.map(({ result }) => result)]
        .filter((result): result is CalcResponse => result !== null)
        .map((result) => result.core_version),
      // With no fit, the curve before it is that of the values in use. After a failed fit the
      // values in use are its last iteration's, which neither curve is of, so they get their own.
      curve: hasFittedValues(state.fit)
        ? fit
        : state.fit.status === "idle"
          ? preFit
          : await calc(state).catch(() => "failed" as const),
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
        // For the RMSE of the values in the file; a file without it still goes.
        const curve = await calc(now.state).catch(() => "failed" as const);
        const { state, mode, header } = await context(now, { curve });
        download(
          name,
          build(
            header,
            mode,
            state.selection,
            state.parameters[mode.id],
            state.fit,
            recordedHolds(state, mode.id),
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
          // The session is an extra of the ZIP, which goes without it if it cannot be made.
          const session = await sessionText(state).catch(() => null);
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
              recordedHolds(state, mode.id),
            ),
            graphs,
            energy,
            missing,
          );
          download(
            text.zipFile,
            zipSync(
              Object.fromEntries(
                Object.entries({
                  ...entries,
                  ...(session === null ? {} : { [text.sessionFile]: session }),
                }).map(([name, contents]) => [name, strToU8(contents)]),
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
    /** The session, to load back later: data, settings and the last fit, kept by the user only. */
    session: () =>
      run(async () => {
        const now = snapshot();
        download(
          text.sessionFile,
          await sessionText(now?.state ?? useSessionStore.getState()),
          "application/json;charset=utf-8",
        );
      }),
    /** One additional graph, from the answers it already drew. */
    graph: (
      name: string,
      temperatureK: readonly number[],
      curves: readonly { name: string; values: readonly (number | null)[] }[],
      issues: readonly string[],
      coreVersion?: string,
    ) =>
      run(async () => {
        const now = snapshot();
        if (now !== null) {
          const { header } = await context(now, {
            derived: issues,
            coreVersions: [coreVersion],
          });
          download(
            text.graphFile(name),
            graphFile(header, temperatureK, curves, energy),
          );
        }
      }),
  };
}
