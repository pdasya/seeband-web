import type { components } from "@seeband/api-client";
import { create } from "zustand";

import type { FitEvent } from "@/api/fitStream";

type Schemas = components["schemas"];

export type Quantity = NonNullable<Schemas["ParseRequest"]["expected"]>;
export const QUANTITIES: readonly Quantity[] = [
  "seebeck",
  "resistivity",
  "hall",
];
export type ParsedTable = Schemas["ParseResponse"];
export type ColumnRole = Schemas["ColumnRole"];
export type Measurement = Schemas["MeasurementResponse"];
export type FitResult = Schemas["FitResponse"];
export type FitFailure = Schemas["ErrorResponse"];

/** Where data came from. Demo data keep their label, as it must show wherever they appear. */
export type DataSource =
  { kind: "file"; name: string } | { kind: "demo"; messageKey: string };

export interface SessionData {
  measurement: Measurement;
  source: DataSource;
  extrapolated: boolean;
}

/** Data come from a file for each quantity, or from one table. Only one way at a time. */
export type DataMode = "separate" | "single";

/**
 * One table, kept with its text in memory only, as a new mapping sends it again. `table` is the
 * last answer, which stays on screen during the next.
 */
export interface SingleFile {
  name: string;
  text: string;
  mapping: readonly ColumnRole[];
  table: ParsedTable | null;
  loading: boolean;
  failure: string | null;
  request: number;
}

export interface Selection {
  model: string | null;
  fitMode: string | null;
  scattering: string | null;
  band1Degeneracy: number;
  band2Degeneracy: number;
  minTemperatureK: number | null;
  maxTemperatureK: number | null;
}

export type IterationParameters = Record<string, number | null>;

/**
 * `waiting` holds until the fit leaves the queue. `stopped` keeps the last values received, which
 * are the start values if `lastParameters` is null. A value that is not finite is null.
 */
export type FitState =
  | { status: "idle" }
  | { status: "waiting" }
  | {
      status: "running";
      iteration: number | null;
      lastParameters: IterationParameters | null;
    }
  | {
      status: "stopped";
      iteration: number | null;
      lastParameters: IterationParameters | null;
    }
  | { status: "done"; result: FitResult }
  | { status: "failed"; failure: FitFailure };

const INITIAL_SELECTION: Selection = {
  model: null,
  fitMode: null,
  scattering: null,
  band1Degeneracy: 1,
  band2Degeneracy: 1,
  minTemperatureK: null,
  maxTemperatureK: null,
};

export interface SessionState {
  data: Partial<Record<Quantity, SessionData>>;
  selection: Selection;
  /** In core units, as the API takes them. */
  parameters: Record<string, number>;
  fit: FitState;
  dataMode: DataMode;
  singleFile: SingleFile | null;

  /** Clears all the data, as what the other way loaded no longer shows. */
  setDataMode: (mode: DataMode) => void;
  /** Returns the id of this request, so that a late answer to an older one can be ignored. */
  startSingleFile: (
    file: Pick<SingleFile, "name" | "text" | "mapping" | "table">,
  ) => number;
  finishSingleFile: (table: ParsedTable) => void;
  failSingleFile: (failure: string) => void;
  clearSingleFile: () => void;
  setData: (quantity: Quantity, data: SessionData) => void;
  removeData: (quantity: Quantity) => void;
  setSelection: (selection: Partial<Selection>) => void;
  setParameters: (parameters: Record<string, number>) => void;
  setParameter: (name: string, value: number) => void;
  /** Starts a new run, which replaces any other, and returns its id for the calls below. */
  fitRequested: () => number;
  fitEvent: (run: number, event: FitEvent) => void;
  fitStopped: (run: number) => void;
  fitFailed: (run: number, failure: FitFailure) => void;
}

function isActive(fit: FitState): boolean {
  return fit.status === "waiting" || fit.status === "running";
}

function afterEvent(fit: FitState, event: FitEvent): FitState {
  switch (event.type) {
    case "started":
      return { status: "running", iteration: null, lastParameters: null };
    case "iteration":
      return {
        status: "running",
        iteration: event.iteration,
        lastParameters: event.parameters,
      };
    case "done":
      return { status: "done", result: event.result };
    case "error":
      return { status: "failed", failure: event.error };
    default:
      return fit;
  }
}

/**
 * The session, in memory only and with no persistence, as measurements must not be stored.
 *
 * It holds codes and numbers, and no text in any language. A change to the data, selection or
 * parameters leaves a running fit alone, as stopping it is the caller's, but a finished result no
 * longer matches them, so that goes back to `idle`.
 */
export const createSessionStore = () =>
  create<SessionState>()((set) => {
    // Late events of an old run must not reach a newer one, or the wrong result would show.
    let currentRun = 0;
    let lastRequest = 0;
    const withoutOldResult = (fit: FitState): FitState =>
      isActive(fit) ? fit : { status: "idle" };

    return {
      data: {},
      selection: INITIAL_SELECTION,
      parameters: {},
      fit: { status: "idle" },
      dataMode: "separate",
      singleFile: null,

      setDataMode: (mode) => {
        set((state) =>
          state.dataMode === mode
            ? state
            : {
                dataMode: mode,
                data: {},
                singleFile: null,
                fit: withoutOldResult(state.fit),
              },
        );
      },
      startSingleFile: (file) => {
        lastRequest += 1;
        set({
          singleFile: {
            ...file,
            loading: true,
            failure: null,
            request: lastRequest,
          },
        });
        return lastRequest;
      },
      finishSingleFile: (table) => {
        set((state) =>
          state.singleFile === null
            ? state
            : {
                singleFile: {
                  ...state.singleFile,
                  table,
                  mapping: table.mapping,
                  loading: false,
                },
              },
        );
      },
      failSingleFile: (failure) => {
        set((state) =>
          state.singleFile === null
            ? state
            : { singleFile: { ...state.singleFile, loading: false, failure } },
        );
      },
      clearSingleFile: () => {
        set({ singleFile: null });
      },
      setData: (quantity, data) => {
        set((state) => ({
          data: { ...state.data, [quantity]: data },
          fit: withoutOldResult(state.fit),
        }));
      },
      removeData: (quantity) => {
        set((state) => {
          const data = Object.fromEntries(
            Object.entries(state.data).filter(([name]) => name !== quantity),
          );
          return { data, fit: withoutOldResult(state.fit) };
        });
      },
      setSelection: (selection) => {
        set((state) => ({
          selection: { ...state.selection, ...selection },
          fit: withoutOldResult(state.fit),
        }));
      },
      setParameters: (parameters) => {
        set((state) => ({ parameters, fit: withoutOldResult(state.fit) }));
      },
      setParameter: (name, value) => {
        set((state) => ({
          parameters: { ...state.parameters, [name]: value },
          fit: withoutOldResult(state.fit),
        }));
      },
      fitRequested: () => {
        currentRun += 1;
        set({ fit: { status: "waiting" } });
        return currentRun;
      },
      // An event after a stop belongs to a fit that no longer counts.
      fitEvent: (run, event) => {
        set((state) =>
          run === currentRun && isActive(state.fit)
            ? { fit: afterEvent(state.fit, event) }
            : state,
        );
      },
      fitStopped: (run) => {
        set((state) => {
          if (run !== currentRun) {
            return state;
          }
          if (state.fit.status === "waiting") {
            return {
              fit: { status: "stopped", iteration: null, lastParameters: null },
            };
          }
          if (state.fit.status === "running") {
            return { fit: { ...state.fit, status: "stopped" } };
          }
          return state;
        });
      },
      fitFailed: (run, failure) => {
        set((state) =>
          run === currentRun && isActive(state.fit)
            ? { fit: { status: "failed", failure } }
            : state,
        );
      },
    };
  });

export const useSessionStore = createSessionStore();
