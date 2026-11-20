import type { components } from "@seeband/api-client";
import { create } from "zustand";

import type { FitEvent } from "@/api/fitStream";
import type { UnitDoubtIssue } from "@/data/units";

type Schemas = components["schemas"];

/** A quantity a fit uses. A conductivity loads as the resistivity 1/σ, so it is not one. */
export type Quantity = Schemas["FitStageResponse"]["quantity"];
/** What a file can hold for a quantity: the quantity itself, or σ in place of ρ. */
export type LoadedQuantity = NonNullable<Schemas["ParseRequest"]["expected"]>;
export const QUANTITIES: readonly Quantity[] = [
  "seebeck",
  "resistivity",
  "hall",
];
/** What a file can hold, in the order a choice lists them: σ beside ρ, which it takes the place of. */
export const LOADED_QUANTITIES: readonly LoadedQuantity[] = [
  "seebeck",
  "resistivity",
  "conductivity",
  "hall",
];

/** The quantity a fit takes from what a file held: ρ = 1/σ for a conductivity. */
export function quantityOf(loaded: LoadedQuantity): Quantity {
  return loaded === "conductivity" ? "resistivity" : loaded;
}

/** What the data of a quantity were loaded as, which is the quantity itself unless ρ came from σ. */
export function loadedAs(
  quantity: Quantity,
  data: Pick<SessionData, "measurement"> | undefined,
): LoadedQuantity {
  return data?.measurement.loaded_as ?? quantity;
}
export type ParsedTable = Schemas["ParseResponse"];
export type ColumnRole = Schemas["ColumnRole"];
/** A column as the server read it, with where its unit came from. */
export type ColumnRead = Schemas["ColumnRead"];
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
  /** The columns and units a user chose, sent again with the text. */
  mapping?: readonly ColumnRole[] | undefined;
  /** The columns as the server read them, with the unit of each, so that a unit can change. */
  readAs?: readonly ColumnRead[] | undefined;
  /** Why the unit of the quantity's column may be wrong, which a user must see before a fit. */
  unitDoubts?: readonly UnitDoubtIssue[] | undefined;
  /** The file's first row, as written and in SI, so that a user can check the units against it. */
  firstRow?: FirstRow | undefined;
  /**
   * The user said the values are right despite `unitDoubts`, so a fit may use them. It lasts until
   * the file or its unit changes, as those give new data.
   */
  unitConfirmed?: boolean | undefined;
}

/** Whether data have a doubt about their unit that the user has not confirmed, which stops a fit. */
export function hasOpenUnitDoubt(
  entry: Pick<SessionData, "unitDoubts" | "unitConfirmed"> | undefined,
): boolean {
  return (entry?.unitDoubts?.length ?? 0) > 0 && entry?.unitConfirmed !== true;
}

/** One row of a file by column: exactly as written, and in SI, with null for a column not read. */
export interface FirstRow {
  written: readonly string[];
  si: readonly (number | null)[];
}

/**
 * A row of an answer's preview exactly as the text writes it. An answer from before the server
 * sent the text gives the values as read instead.
 */
export function writtenRow(
  table: ParsedTable,
  row: number,
): readonly string[] | undefined {
  const texts: ParsedTable["preview_text"] | undefined = table.preview_text;
  return texts?.[row] ?? table.preview[row]?.map(String);
}

/** The first row of an answer, if it has one. */
export function firstRowOf(table: ParsedTable): FirstRow | undefined {
  const written = writtenRow(table, 0);
  const si = table.preview_si[0];
  return written === undefined || si === undefined
    ? undefined
    : { written, si };
}

export type InterpolatedQuantities = Partial<
  Record<Quantity, Schemas["InterpolatedResponse"]>
>;

/** Interpolated values sit beside the measured data, so that turning it off restores those. */
export type InterpolationFailureReason =
  Schemas["ParseResponse"]["interpolation_failure_reasons"][string];

export interface InterpolationState {
  enabled: boolean;
  loading: boolean;
  values: InterpolatedQuantities;
  failed: readonly Quantity[];
  /** Why the server could not interpolate a quantity in `failed`. None for a lost request. */
  failureReasons?: Partial<Record<Quantity, InterpolationFailureReason>>;
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
  | Quantity
  | "conductivity"
  | "chemical_potential"
  | "thermal_conductivity"
  | "lorenz_number"
  | "bands"
  | "carrier_concentration"
  | "band_diagram";

/** What the four charts show at first: the measured quantities, and the bands. */
export const INITIAL_CHART_PANELS: readonly ChartTab[] = [
  "seebeck",
  "resistivity",
  "hall",
  "band_diagram",
];

/**
 * One table, kept with its text in memory only, as a new mapping sends it again. `table` is the
 * last answer, which stays on screen during the next.
 */
export interface SingleFile {
  name: string;
  text: string;
  /** The user's mapping while it is read, then the server's, with where each unit came from. */
  mapping: readonly ColumnRead[];
  table: ParsedTable | null;
  loading: boolean;
  failure: string | null;
  request: number;
}

export interface Selection {
  parameterization?: "explicit_density_v1" | "explicit_fermi_v1";
  carrierType?: "p" | "n";
  bandConfiguration?: "vb_vb" | "vb_cb" | "cb_cb";
  netElectronDensityPerM3?: number;
  fitAbsoluteMass?: boolean;
  /** Original verified session, including its fit, holds, units and bounds. */
  legacySource?: string;
  /** Absent in older in-memory state; new requests use the verified method. */
  algorithm?: Schemas["FitApiRequest"]["algorithm"];
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
  | { status: "waiting"; algorithm?: Selection["algorithm"] }
  | {
      status: "running";
      algorithm?: Selection["algorithm"];
      iteration: number | null;
      lastParameters: IterationParameters | null;
    }
  | {
      status: "stopped";
      algorithm?: Selection["algorithm"];
      iteration: number | null;
      lastParameters: IterationParameters | null;
    }
  | { status: "done"; result: FitResult }
  | { status: "failed"; failure: FitFailure };

function supportedSelection(selection: Selection): Selection {
  return selection.scattering === "ionized" ||
    (selection.model === "dpb" && selection.parameterization !== undefined)
    ? { ...selection, algorithm: "verified-sequential-v2" }
    : selection;
}

const INITIAL_SELECTION: Selection = {
  algorithm: "verified-sequential-v2",
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
export type NetRange = Schemas["NetRange"];

/** How the last initial guess ended. Only `applied` changed any value. */
export type GuessOutcome =
  | {
      kind: "unsupported";
      reason:
        | "sign_change"
        | "too_few_temperatures"
        | "zero_seebeck"
        | "scattering_not_supported";
      warnings: GuessWarnings;
    }
  | {
      kind: "applied";
      netRange?: NetRange;
      warnings: GuessWarnings;
      fitModes?: readonly string[];
    }
  | { kind: "unchanged"; warnings: GuessWarnings }
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
  /** Stable selector result for a mode that received no values. */
  unchanged: Extract<GuessOutcome, { kind: "unchanged" }>;
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
  /** Last estimates, so automatic guesses can distinguish them from manual starts. */
  guessedParameters: Record<string, Record<string, number>>;
  fit: FitState;
  dataMode: DataMode;
  singleFile: SingleFile | null;
  /** The files of the way not in use. */
  otherSource: DataSourceFiles | null;
  interpolation: InterpolationState;
  /** What each of the four charts shows. */
  chartPanels: readonly ChartTab[];
  guessPending: boolean;
  guess: GuessRecord | null;
  /** The net whose guess the last fit started from, or null if it started from other values. */
  fitStartNet: NetRange | null;
  fitStartNumerical: boolean;
  /** The values the last fit started from, in core units, for its curve before the fit. */
  fitStartValues: Record<string, number> | null;
  /** Counts resets, so that fields can start again even if the values do not change. */
  parameterResets: number;
  /** Bounds a fit of each mode uses in place of the description's, in core units. */
  customBounds: Record<string, Record<string, FitBounds>>;
  /** Fitted parameters a fit of each mode keeps at their values, as the design's fix toggle. */
  held: Record<string, readonly string[]>;
  /** Slots with a file on its way or waiting for a choice, which is the user's though not in `data`. */
  slotsReading: readonly Quantity[];
  /** What each model had when another was chosen, as the design keeps them apart. */
  savedModelSettings: Record<string, ModelSettings>;
  /** The session file this session came from, until a fit runs, or null. */
  restored: Restored | null;
  /**
   * Fits that finished in this session, oldest first, each as it was when it ended and kept so
   * whatever changes after: a change of values ends the current result, not these. At most
   * `MAX_RUNS`, in memory only.
   */
  runs: readonly FitRun[];

  setChartPanel: (index: number, tab: ChartTab) => void;
  /** Keeps the current model's settings, and takes up these for the new one. */
  chooseModel: (model: string, settings: ModelSettings) => void;
  setInterpolationEnabled: (enabled: boolean) => void;
  startInterpolation: () => void;
  stopInterpolation: () => void;
  finishInterpolation: (
    values: InterpolatedQuantities,
    failed: readonly Quantity[],
    failure?: string | null,
    failureReasons?: Partial<Record<Quantity, InterpolationFailureReason>>,
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
  /** The user says the values of a quantity are right despite a doubt about their unit. */
  confirmUnit: (quantity: Quantity) => void;
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
  setHeld: (fitMode: string, parameter: string, held: boolean) => void;
  fileReadStarted: (quantity: Quantity) => void;
  fileReadEnded: (quantity: Quantity) => void;
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
  fitRequested: (
    fitMode?: string,
    start?: Record<string, number>,
    algorithm?: Selection["algorithm"],
  ) => number;
  fitEvent: (run: number, event: FitEvent) => void;
  fitStopped: (run: number) => void;
  fitFailed: (run: number, failure: FitFailure) => void;
  /** Takes up a session from a file in place of this one, its last fit as it was. */
  restoreSession: (session: RestoredSession, from: RestoredFrom) => void;
  /** The restored fit used other data than the session has now, so it goes. */
  restoredFitStale: () => void;
}

/** What a session file gives the store. `sessionFile` checks it before. */
export interface RestoredSession {
  dataMode: DataMode;
  data: Partial<Record<Quantity, SessionData>>;
  singleFile: Pick<SingleFile, "name" | "text" | "mapping" | "table"> | null;
  otherSource: {
    data: Partial<Record<Quantity, SessionData>>;
    singleFile: Pick<SingleFile, "name" | "text" | "mapping" | "table"> | null;
  } | null;
  chartPanels: readonly ChartTab[];
  savedModelSettings: Record<string, ModelSettings>;
  selection: Selection;
  parameters: SessionState["parameters"];
  guessedParameters?: SessionState["guessedParameters"];
  customBounds: SessionState["customBounds"];
  held: SessionState["held"];
  interpolationEnabled: boolean;
  fitStart: {
    values: Record<string, number> | null;
    net: NetRange | null;
    numerical: boolean;
  };
  result: FitResult | null;
  /** The request that made `result`, kept as it was so that saving again keeps it too. */
  request: Schemas["FitApiRequest"] | null;
}

/** Where a restored session came from, which the fit screen names. */
export interface RestoredFrom {
  saved: string;
  appVersion: string;
  /** The core the restored fit ran on, or null with no fit. */
  fitCoreVersion: string | null;
  /** The core of the server when the file was loaded, or null if it did not answer. */
  serverCoreVersion: string | null;
}

/** How many finished fits a session keeps to compare, the oldest going first. */
export const MAX_RUNS = 10;

/**
 * A fit as it was when it ended: what it was of, and what it found. The data, interpolation and
 * values are the session's own objects of that moment, which the store never changes in place, so
 * that a run is a snapshot that costs no copy, and `data === state.data` says the data are the same.
 */
export interface FitRun {
  /** Counts from 1 in a session, so that a run keeps its name as older ones go. */
  number: number;
  /** When it ended, as ISO 8601. */
  finishedAt: string;
  selection: Selection;
  /** Every parameter of its mode, the fitted ones at what the fit found. */
  parameters: Record<string, number>;
  start: Record<string, number> | null;
  customBounds: Record<string, FitBounds>;
  held: readonly string[];
  data: Partial<Record<Quantity, SessionData>>;
  interpolation: InterpolationState;
  result: FitResult;
}

/** A restored session's origin, its fit and that fit's request, as the store keeps them. */
export interface Restored extends RestoredFrom {
  /** The restored fit, the same object as `fit.result` while it stands. */
  result: FitResult | null;
  request: Schemas["FitApiRequest"] | null;
  /**
   * The data this server gives now differ from those the restored fit used, as a server can
   * interpolate otherwise, so that fit was taken off the screen.
   */
  stale: boolean;
}

function withoutMode<T>(
  values: Record<string, T>,
  fitMode: string,
): Record<string, T> {
  return Object.fromEntries(
    Object.entries(values).filter(([name]) => name !== fitMode),
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
  const algorithm = fitAlgorithm(fit);
  const provenance = algorithm === undefined ? {} : { algorithm };
  switch (event.type) {
    case "started":
      return {
        status: "running",
        ...provenance,
        iteration: null,
        lastParameters: null,
      };
    case "iteration":
      return {
        status: "running",
        ...provenance,
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
  state: Pick<SessionState, "guess" | "data" | "parameters" | "selection">,
): GuessOutcome | null {
  const { guess } = state;
  if (guess === null || state.data.seebeck?.measurement !== guess.measurement) {
    return null;
  }
  if (guess.outcome.kind === "applied") {
    if (guess.parameters !== state.parameters) return null;
    if (
      guess.outcome.fitModes !== undefined &&
      !guess.outcome.fitModes.includes(state.selection.fitMode ?? "")
    ) {
      return guess.unchanged;
    }
  }
  return guess.outcome;
}

/** Whether a file of the user's is on its way, in either way of loading. */
export function readsFiles(
  state: Pick<SessionState, "slotsReading" | "singleFile">,
): boolean {
  return state.slotsReading.length > 0 || state.singleFile?.loading === true;
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
    // What the current fit was asked with, as the session can change while it runs.
    let currentInputs: Pick<
      FitRun,
      "selection" | "start" | "customBounds" | "held" | "data" | "interpolation"
    > | null = null;
    let lastRequest = 0;
    const withoutOldResult = (fit: FitState): FitState =>
      isFitActive(fit) ? fit : { status: "idle" };

    return {
      data: {},
      selection: INITIAL_SELECTION,
      parameters: {},
      guessedParameters: {},
      fit: { status: "idle" },
      dataMode: "separate",
      singleFile: null,
      otherSource: null,
      interpolation: INITIAL_INTERPOLATION,
      chartPanels: INITIAL_CHART_PANELS,
      guessPending: false,
      guess: null,
      fitStartNet: null,
      fitStartNumerical: false,
      fitStartValues: null,
      parameterResets: 0,
      customBounds: {},
      held: {},
      slotsReading: [],
      savedModelSettings: {},
      restored: null,
      runs: [],

      restoreSession: (session, from) => {
        // Events of a fit that ran before belong to no session now.
        currentRun += 1;
        currentFitMode = null;
        set((state) => ({
          data: session.data,
          dataMode: session.dataMode,
          singleFile:
            session.singleFile === null
              ? null
              : {
                  ...session.singleFile,
                  loading: false,
                  failure: null,
                  request: 0,
                },
          otherSource:
            session.otherSource === null
              ? null
              : {
                  data: session.otherSource.data,
                  singleFile:
                    session.otherSource.singleFile === null
                      ? null
                      : {
                          ...session.otherSource.singleFile,
                          loading: false,
                          failure: null,
                          request: 0,
                        },
                },
          chartPanels: session.chartPanels,
          selection: supportedSelection(session.selection),
          parameters: session.parameters,
          guessedParameters: session.guessedParameters ?? {},
          customBounds: session.customBounds,
          held: session.held,
          interpolation: {
            ...INITIAL_INTERPOLATION,
            enabled: session.interpolationEnabled,
          },
          fit:
            session.result === null
              ? { status: "idle" }
              : { status: "done", result: session.result },
          fitStartValues: session.fitStart.values,
          fitStartNet: session.fitStart.net,
          fitStartNumerical: session.fitStart.numerical,
          guess: null,
          guessPending: false,
          slotsReading: [],
          savedModelSettings: session.savedModelSettings,
          // Fields being typed in start again from the restored values.
          parameterResets: state.parameterResets + 1,
          restored: {
            ...from,
            result: session.result,
            request: session.request,
            stale: false,
          },
          // The runs of the session left behind were of other data and settings.
          runs: [],
        }));
      },
      restoredFitStale: () => {
        set((state) =>
          state.restored === null ||
          state.fit.status !== "done" ||
          state.fit.result !== state.restored.result
            ? {}
            : {
                fit: { status: "idle" },
                restored: { ...state.restored, stale: true },
              },
        );
      },

      fileReadStarted: (quantity) => {
        set((state) => ({
          slotsReading: [
            ...state.slotsReading.filter((slot) => slot !== quantity),
            quantity,
          ],
        }));
      },
      fileReadEnded: (quantity) => {
        set((state) => ({
          slotsReading: state.slotsReading.filter((slot) => slot !== quantity),
        }));
      },
      guessStarted: () => {
        set({ guessPending: true, guess: null });
      },
      guessFinished: (outcome, model, measurement) => {
        set((state) => ({
          guessPending: false,
          guess: {
            unchanged: { kind: "unchanged", warnings: outcome.warnings },
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
          const guessedParameters = { ...state.guessedParameters };
          for (const { fitMode, values } of modes) {
            parameters[fitMode] = { ...parameters[fitMode], ...values };
            guessedParameters[fitMode] = {
              ...guessedParameters[fitMode],
              ...values,
            };
          }
          return {
            parameters,
            guessedParameters,
            guessPending: false,
            guess: {
              outcome,
              model,
              measurement,
              parameters,
              unchanged: { kind: "unchanged", warnings: outcome.warnings },
            },
            fit: withoutOldResult(state.fit),
          };
        });
      },
      setChartPanel: (index, tab) => {
        set((state) => ({
          chartPanels: state.chartPanels.map((old, at) =>
            at === index ? tab : old,
          ),
        }));
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
            selection: supportedSelection({ ...selection, ...settings, model }),
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
      finishInterpolation: (
        values,
        failed,
        failure = null,
        failureReasons = {},
      ) => {
        set((state) => ({
          interpolation: {
            ...state.interpolation,
            loading: false,
            values,
            failed,
            failureReasons,
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
      confirmUnit: (quantity) => {
        set((state) => {
          const entry = state.data[quantity];
          return entry === undefined
            ? state
            : {
                data: {
                  ...state.data,
                  [quantity]: { ...entry, unitConfirmed: true },
                },
              };
        });
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
          selection: supportedSelection({ ...state.selection, ...selection }),
          ...(selection.scattering !== undefined &&
          selection.scattering !== state.selection.scattering
            ? { guess: null }
            : {}),
          fit:
            state.fit.status === "stopped" &&
            Object.keys(selection).every((key) => key === "algorithm")
              ? state.fit
              : withoutOldResult(state.fit),
        }));
      },
      setParameters: (fitMode, values) => {
        set((state) => ({
          parameters: { ...state.parameters, [fitMode]: values },
          guessedParameters: withoutMode(state.guessedParameters, fitMode),
          fit: withoutOldResult(state.fit),
        }));
      },
      setParameter: (fitMode, name, value) => {
        set((state) => ({
          guessedParameters: {
            ...state.guessedParameters,
            [fitMode]: Object.fromEntries(
              Object.entries(state.guessedParameters[fitMode] ?? {}).filter(
                ([parameter]) => parameter !== name,
              ),
            ),
          },
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
      setHeld: (fitMode, parameter, held) => {
        set((state) => {
          const kept = (state.held[fitMode] ?? []).filter(
            (name) => name !== parameter,
          );
          return {
            held: {
              ...state.held,
              [fitMode]: held ? [...kept, parameter] : kept,
            },
            // A result of a fit that held other parameters is not one of this.
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
          guessedParameters: withoutMode(state.guessedParameters, fitMode),
          customBounds: withoutMode(state.customBounds, fitMode),
          held: Object.fromEntries(
            Object.entries(state.held).filter(([name]) => name !== fitMode),
          ),
          parameters: Object.fromEntries(
            Object.entries(state.parameters).filter(
              ([name]) => name !== fitMode,
            ),
          ),
          parameterResets: state.parameterResets + 1,
          fit: withoutOldResult(state.fit),
        }));
      },
      fitRequested: (fitMode, start, algorithm) => {
        currentRun += 1;
        currentFitMode = fitMode ?? null;
        // A guess wrote the values of its own model only, so a fit of another did not start from it.
        set((state) => {
          const guess = currentGuess(state);
          currentInputs =
            fitMode === undefined
              ? null
              : {
                  selection: state.selection,
                  start: start ?? null,
                  customBounds: state.customBounds[fitMode] ?? {},
                  held: state.held[fitMode] ?? [],
                  data: state.data,
                  interpolation: state.interpolation,
                };
          return {
            // The fit restored from a file is replaced, and with it what the file said of it.
            restored: null,
            fit: {
              status: "waiting",
              ...(algorithm === undefined ? {} : { algorithm }),
            },
            fitStartValues: start ?? null,
            fitStartNumerical:
              guess?.kind === "applied" &&
              !guess.netRange &&
              state.guess?.model === state.selection.model,
            fitStartNet:
              guess?.kind === "applied" &&
              state.guess?.model === state.selection.model
                ? (guess.netRange ?? null)
                : null,
          };
        });
        return currentRun;
      },
      // An event after a stop belongs to a fit that no longer counts.
      fitEvent: (run, event) => {
        set((state) => {
          if (run !== currentRun || !isFitActive(state.fit)) {
            return state;
          }
          const parameters = withFitValues(
            state.parameters,
            currentFitMode,
            event,
          );
          const fit = afterEvent(state.fit, event);
          const mode = currentFitMode;
          const inputs = currentInputs;
          // A finished fit with values is kept, as it was asked and as it ended, to compare.
          const kept =
            event.type === "done" &&
            event.result.status !== "failed" &&
            mode !== null &&
            inputs !== null
              ? [
                  ...state.runs,
                  {
                    ...inputs,
                    number: (state.runs.at(-1)?.number ?? 0) + 1,
                    finishedAt: new Date().toISOString(),
                    parameters: parameters[mode] ?? {},
                    result: event.result,
                  },
                ].slice(-MAX_RUNS)
              : state.runs;
          return { fit, parameters, runs: kept };
        });
      },
      fitStopped: (run) => {
        set((state) => {
          if (run !== currentRun) {
            return state;
          }
          if (state.fit.status === "waiting") {
            return {
              fit: {
                ...state.fit,
                status: "stopped",
                iteration: null,
                lastParameters: null,
              },
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

/** Provenance belongs to the submitted run; old snapshots without it remain unknown. */
export function fitAlgorithm(fit: FitState): Selection["algorithm"] {
  if (fit.status === "done") return fit.result.algorithm;
  if (
    fit.status === "waiting" ||
    fit.status === "running" ||
    fit.status === "stopped"
  )
    return fit.algorithm;
  return undefined;
}
