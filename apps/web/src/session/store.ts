import type { components } from "@seeband/api-client";
import { create } from "zustand";

import type { FitEvent } from "@/api/fitStream";

type Schemas = components["schemas"];

export type Quantity = NonNullable<Schemas["ParseRequest"]["expected"]>;
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
    const withoutOldResult = (fit: FitState): FitState =>
      isActive(fit) ? fit : { status: "idle" };

    return {
      data: {},
      selection: INITIAL_SELECTION,
      parameters: {},
      fit: { status: "idle" },

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
