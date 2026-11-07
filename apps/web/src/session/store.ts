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
export type ModelSettings = Pick<
  Selection,
  "fitMode" | "scattering" | "band1Degeneracy" | "band2Degeneracy"
>;
export type Measurement = Schemas["MeasurementResponse"];
export type FitBounds = Schemas["BoundsInput"];
export type FitResult = Schemas["FitResponse"];
export type FitFailure = Schemas["ErrorResponse"];

/** Where data came from. Demo data keep their label, as it must show wherever they appear. */
export type DataSource =
  { kind: "file"; name: string } | { kind: "demo"; messageKey: string };

export interface SessionData {
  measurement: Measurement;
  source: DataSource;
  extrapolated: boolean;
  /** The file's text, in memory only, as interpolating sends it again. */
  text: string;
}

export type InterpolatedQuantities = Partial<
  Record<Quantity, Schemas["InterpolatedResponse"]>
>;

/** Interpolated values sit beside the measured data, so that turning it off restores those. */
export interface InterpolationState {
  enabled: boolean;
  loading: boolean;
  values: InterpolatedQuantities;
  failed: readonly Quantity[];
  failure: string | null;
}

/** What a fit reads for a quantity. */
export interface FitData {
  temperature_k: readonly number[];
  values: readonly number[];
  extrapolated: boolean;
}

/** Data come from a file for each quantity, or from one table. Only one way counts at a time. */
export type DataMode = "separate" | "single";

/** What the fit screen's chart shows. */
export type ChartTab =
  Quantity | "chemical_potential" | "bands" | "band_diagram";

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

const INITIAL_INTERPOLATION: InterpolationState = {
  enabled: false,
  loading: false,
  values: {},
  failed: [],
  failure: null,
};

interface DataSourceFiles {
  data: Partial<Record<Quantity, SessionData>>;
  singleFile: SingleFile | null;
}

// Leaving a way of loading ends its read. A table on its way goes, and a change of mapping on its
// way leaves the last answer, which the data belong to.
function filesToKeep({
  data,
  singleFile,
}: DataSourceFiles): DataSourceFiles | null {
  if (singleFile?.loading === true && singleFile.table === null) {
    return null;
  }
  return {
    data,
    singleFile:
      singleFile === null
        ? null
        : {
            ...singleFile,
            mapping: singleFile.table?.mapping ?? singleFile.mapping,
            loading: false,
            // No later answer belongs to it, as ids of requests start at 1.
            request: 0,
          },
  };
}

type GuessWarnings = Schemas["GuessFound"]["warnings"];
type NetRange = Schemas["NetRange"];

/** How the last initial guess ended. Only `applied` changed any value. */
export type GuessOutcome =
  | { kind: "applied"; netRange: NetRange; warnings: GuessWarnings }
  | {
      kind: "no_net";
      firstK: number;
      lastK: number;
      available: NetRange[];
      warnings: GuessWarnings;
    }
  | { kind: "not_finite"; warnings: GuessWarnings }
  | { kind: "needs_mass"; warnings: GuessWarnings }
  | { kind: "failed"; code: string; warnings: GuessWarnings };

interface GuessRecord {
  outcome: GuessOutcome;
  model: string;
  measurement: Measurement;
  /** The values it left, as a badge about it holds only while they stand. */
  parameters: SessionState["parameters"];
}

export interface SessionState {
  data: Partial<Record<Quantity, SessionData>>;
  selection: Selection;
  /**
   * What was set, per fit mode, in core units as the API takes them. Modes have their own defaults
   * and ranges, so a value of one does not carry to another. `parameterValues` adds the defaults.
   */
  parameters: Record<string, Record<string, number>>;
  fit: FitState;
  dataMode: DataMode;
  singleFile: SingleFile | null;
  /** The files of the way not in use. */
  otherSource: DataSourceFiles | null;
  interpolation: InterpolationState;
  chartTab: ChartTab;
  guessPending: boolean;
  guess: GuessRecord | null;
  /** Counts resets, so that fields can start again even if the values do not change. */
  parameterResets: number;
  /** Bounds a fit of each mode uses in place of the description's, in core units. */
  customBounds: Record<string, Record<string, FitBounds>>;
  /** Files of the separate slots on their way, which are the user's though not yet in `data`. */
  fileReads: number;
  /** What each model had when another was chosen, as the design keeps them apart. */
  savedModelSettings: Record<string, ModelSettings>;

  setChartTab: (tab: ChartTab) => void;
  /** Keeps the current model's settings, and takes up these for the new one. */
  chooseModel: (model: string, settings: ModelSettings) => void;
  setInterpolationEnabled: (enabled: boolean) => void;
  startInterpolation: () => void;
  stopInterpolation: () => void;
  finishInterpolation: (
    values: InterpolatedQuantities,
    failed: readonly Quantity[],
    failure?: string | null,
  ) => void;
  /** What the other way loaded stays for coming back, and does not count until then. */
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
  setParameters: (fitMode: string, values: Record<string, number>) => void;
  setParameter: (fitMode: string, name: string, value: number) => void;
  /** Back to the defaults of a fit mode, also for a number being typed. */
  resetParameters: (fitMode: string) => void;
  /** With null, the parameter goes back to the bounds of its description. */
  setCustomBounds: (
    fitMode: string,
    parameter: string,
    bounds: FitBounds | null,
  ) => void;
  clearCustomBounds: (fitMode: string) => void;
  fileReadStarted: () => void;
  fileReadEnded: () => void;
  guessStarted: () => void;
  guessFinished: (
    outcome: GuessOutcome,
    model: string,
    measurement: Measurement,
  ) => void;
  /** It ended with nothing to say, as the user moved on from it. */
  guessDropped: () => void;
  guessApplied: (
    modes: readonly { fitMode: string; values: Record<string, number> }[],
    outcome: GuessOutcome,
    model: string,
    measurement: Measurement,
  ) => void;
  /** Starts a new run, which replaces any other, and returns its id for the calls below. */
  fitRequested: (fitMode?: string) => number;
  fitEvent: (run: number, event: FitEvent) => void;
  fitStopped: (run: number) => void;
  fitFailed: (run: number, failure: FitFailure) => void;
}

function withoutMode(
  customBounds: SessionState["customBounds"],
  fitMode: string,
): SessionState["customBounds"] {
  return Object.fromEntries(
    Object.entries(customBounds).filter(([name]) => name !== fitMode),
  );
}

function withoutValues(interpolation: InterpolationState): InterpolationState {
  return { ...interpolation, values: {}, failed: [], failure: null };
}

export function isFitActive(fit: FitState): boolean {
  return fit.status === "waiting" || fit.status === "running";
}

// A fit moves the values on screen as it goes, so a Stop keeps the last ones. A value that is not
// finite has nothing to show, and the last one stays.
function withFitValues(
  parameters: SessionState["parameters"],
  fitMode: string | null,
  event: FitEvent,
): SessionState["parameters"] {
  const values =
    event.type === "iteration"
      ? event.parameters
      : event.type === "done"
        ? event.result.parameters
        : null;
  if (fitMode === null || values === null) {
    return parameters;
  }
  const finite: Record<string, number> = {};
  for (const [name, value] of Object.entries(values)) {
    if (value !== null) {
      finite[name] = value;
    }
  }
  return { ...parameters, [fitMode]: { ...parameters[fitMode], ...finite } };
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
 * The last guess, while what it says still holds. New data end any of them, and new values end the
 * badge of one that was applied, as these are no longer its values.
 */
export function currentGuess(
  state: Pick<SessionState, "guess" | "data" | "parameters">,
): GuessOutcome | null {
  const { guess } = state;
  if (guess === null || state.data.seebeck?.measurement !== guess.measurement) {
    return null;
  }
  return guess.outcome.kind === "applied" &&
    guess.parameters !== state.parameters
    ? null
    : guess.outcome;
}

/** Whether a file of the user's is on its way, in either way of loading. */
export function readsFiles(
  state: Pick<SessionState, "fileReads" | "singleFile">,
): boolean {
  return state.fileReads > 0 || state.singleFile?.loading === true;
}

/** Whether a reload would lose any file, in the way in use or the other. */
export function holdsFiles(
  state: Pick<SessionState, "data" | "singleFile" | "otherSource">,
): boolean {
  const { data, singleFile, otherSource } = state;
  return (
    Object.keys(data).length > 0 ||
    singleFile?.table != null ||
    (otherSource !== null &&
      (Object.keys(otherSource.data).length > 0 ||
        otherSource.singleFile?.table != null))
  );
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
    let currentFitMode: string | null = null;
    let lastRequest = 0;
    const withoutOldResult = (fit: FitState): FitState =>
      isFitActive(fit) ? fit : { status: "idle" };

    return {
      data: {},
      selection: INITIAL_SELECTION,
      parameters: {},
      fit: { status: "idle" },
      dataMode: "separate",
      singleFile: null,
      otherSource: null,
      interpolation: INITIAL_INTERPOLATION,
      chartTab: "seebeck",
      guessPending: false,
      guess: null,
      parameterResets: 0,
      customBounds: {},
      fileReads: 0,
      savedModelSettings: {},

      fileReadStarted: () => {
        set((state) => ({ fileReads: state.fileReads + 1 }));
      },
      fileReadEnded: () => {
        set((state) => ({ fileReads: state.fileReads - 1 }));
      },
      guessStarted: () => {
        set({ guessPending: true, guess: null });
      },
      guessFinished: (outcome, model, measurement) => {
        set((state) => ({
          guessPending: false,
          guess: {
            outcome,
            model,
            measurement,
            parameters: state.parameters,
          },
        }));
      },
      guessDropped: () => {
        set({ guessPending: false, guess: null });
      },
      guessApplied: (modes, outcome, model, measurement) => {
        set((state) => {
          const parameters = { ...state.parameters };
          for (const { fitMode, values } of modes) {
            parameters[fitMode] = { ...parameters[fitMode], ...values };
          }
          return {
            parameters,
            guessPending: false,
            guess: { outcome, model, measurement, parameters },
            fit: withoutOldResult(state.fit),
          };
        });
      },
      setChartTab: (chartTab) => {
        set({ chartTab });
      },
      chooseModel: (model, settings) => {
        set((state) => {
          const { selection } = state;
          if (selection.model === model) {
            return state;
          }
          return {
            savedModelSettings:
              selection.model === null
                ? state.savedModelSettings
                : {
                    ...state.savedModelSettings,
                    [selection.model]: {
                      fitMode: selection.fitMode,
                      scattering: selection.scattering,
                      band1Degeneracy: selection.band1Degeneracy,
                      band2Degeneracy: selection.band2Degeneracy,
                    },
                  },
            selection: { ...selection, ...settings, model },
            fit: withoutOldResult(state.fit),
          };
        });
      },
      setInterpolationEnabled: (enabled) => {
        set((state) => ({
          interpolation: { ...INITIAL_INTERPOLATION, enabled },
          fit: withoutOldResult(state.fit),
        }));
      },
      startInterpolation: () => {
        set((state) => ({
          interpolation: {
            ...state.interpolation,
            loading: true,
            failure: null,
          },
        }));
      },
      stopInterpolation: () => {
        set((state) =>
          state.interpolation.loading
            ? { interpolation: { ...state.interpolation, loading: false } }
            : state,
        );
      },
      // What leads here has already cleared a fit's result: new data, a range or the switch.
      finishInterpolation: (values, failed, failure = null) => {
        set((state) => ({
          interpolation: {
            ...state.interpolation,
            loading: false,
            values,
            failed,
            failure,
          },
        }));
      },
      setDataMode: (mode) => {
        set((state) =>
          state.dataMode === mode
            ? state
            : {
                dataMode: mode,
                data: state.otherSource?.data ?? {},
                singleFile: state.otherSource?.singleFile ?? null,
                otherSource: filesToKeep(state),
                interpolation: withoutValues(state.interpolation),
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
          interpolation: withoutValues(state.interpolation),
          fit: withoutOldResult(state.fit),
        }));
      },
      removeData: (quantity) => {
        set((state) => {
          const data = Object.fromEntries(
            Object.entries(state.data).filter(([name]) => name !== quantity),
          );
          return {
            data,
            interpolation: withoutValues(state.interpolation),
            fit: withoutOldResult(state.fit),
          };
        });
      },
      setSelection: (selection) => {
        set((state) => ({
          selection: { ...state.selection, ...selection },
          fit: withoutOldResult(state.fit),
        }));
      },
      setParameters: (fitMode, values) => {
        set((state) => ({
          parameters: { ...state.parameters, [fitMode]: values },
          fit: withoutOldResult(state.fit),
        }));
      },
      setParameter: (fitMode, name, value) => {
        set((state) => ({
          parameters: {
            ...state.parameters,
            [fitMode]: { ...state.parameters[fitMode], [name]: value },
          },
          fit: withoutOldResult(state.fit),
        }));
      },
      setCustomBounds: (fitMode, parameter, bounds) => {
        set((state) => {
          const kept = Object.entries(state.customBounds[fitMode] ?? {}).filter(
            ([name]) => name !== parameter,
          );
          return {
            customBounds: {
              ...state.customBounds,
              [fitMode]: Object.fromEntries(
                bounds === null ? kept : [...kept, [parameter, bounds]],
              ),
            },
            fit: withoutOldResult(state.fit),
          };
        });
      },
      clearCustomBounds: (fitMode) => {
        set((state) => ({
          customBounds: withoutMode(state.customBounds, fitMode),
          fit: withoutOldResult(state.fit),
        }));
      },
      resetParameters: (fitMode) => {
        set((state) => ({
          customBounds: withoutMode(state.customBounds, fitMode),
          parameters: Object.fromEntries(
            Object.entries(state.parameters).filter(
              ([name]) => name !== fitMode,
            ),
          ),
          parameterResets: state.parameterResets + 1,
          fit: withoutOldResult(state.fit),
        }));
      },
      fitRequested: (fitMode) => {
        currentRun += 1;
        currentFitMode = fitMode ?? null;
        set({ fit: { status: "waiting" } });
        return currentRun;
      },
      // An event after a stop belongs to a fit that no longer counts.
      fitEvent: (run, event) => {
        set((state) =>
          run === currentRun && isFitActive(state.fit)
            ? {
                fit: afterEvent(state.fit, event),
                parameters: withFitValues(
                  state.parameters,
                  currentFitMode,
                  event,
                ),
              }
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
          run === currentRun && isFitActive(state.fit)
            ? { fit: { status: "failed", failure } }
            : state,
        );
      },
    };
  });

/**
 * What a fit reads for a quantity: its interpolated values with the switch on, or else the measured
 * data. With the switch on, a quantity with no usable values gives null rather than quietly falling
 * back to measured data, and so does a value that is not finite, which the API would refuse.
 */
export function fitData(
  state: Pick<SessionState, "data" | "interpolation">,
  quantity: Quantity,
): FitData | null {
  const entry = state.data[quantity];
  if (entry === undefined) {
    return null;
  }
  if (!state.interpolation.enabled) {
    const { temperature_k, values } = entry.measurement;
    return { temperature_k, values, extrapolated: entry.extrapolated };
  }
  // While it waits for an answer, the values are for an older range.
  if (state.interpolation.loading) {
    return null;
  }
  const result = state.interpolation.values[quantity];
  if (result?.values.some((value) => value === null) !== false) {
    return null;
  }
  return {
    temperature_k: result.temperature_k,
    values: result.values as number[],
    extrapolated: result.extrapolated,
  };
}

export const useSessionStore = createSessionStore();
