import type { FitRequest } from "@/api/client";
import { sha256Hex } from "@/session/sha256";
import {
  QUANTITIES,
  type ChartTab,
  type DataMode,
  type FitResult,
  type ModelSettings,
  type NetRange,
  type RestoredSession,
  type Quantity,
  type Selection,
  type SessionData,
  type SessionState,
  type SingleFile,
} from "@/session/store";

/**
 * A session as a file, which the user keeps and loads back: nothing is stored on the server.
 *
 * It holds the data as read, with the text of each file and how each column was read, the choices
 * of the fit screen, and the last finished fit with the request that made it. Loading it gives the
 * same session back; a fit it holds is shown as it was, never run again by a newer model on its
 * own. Versions 1 and 2 remain readable. Version 4 marks explicit DPB sessions with user B
 * inputs, so older clients reject them rather than reinterpret their physical inputs.
 */
export const SESSION_FORMAT = "seeband-session";
// Version 3 is reserved for composition sessions.
export const SESSION_VERSION = 4;
/**
 * The largest session file, in bytes of the file and characters of its text alike: the text of
 * three data files of 2 MB, their tables, and a fit, with room to spare.
 */
export const MAX_SESSION_BYTES = 50_000_000;
/** The most points of one quantity, far above the API's own limit, so a file cannot freeze the page. */
const MAX_POINTS = 1_000_000;

type SavedSingleFile = Pick<SingleFile, "name" | "text" | "mapping" | "table">;

/** What a session holds, which the checksum covers. */
export interface SessionContent {
  /** Explicit user B semantics; absent in historical v1/v2 files. */
  ionizedBInputs?: boolean;
  dataMode: DataMode;
  data: Partial<Record<Quantity, SessionData>>;
  /** The files of the way of loading not in use, which count again when the user goes back. */
  otherSource: {
    data: Partial<Record<Quantity, SessionData>>;
    singleFile: SavedSingleFile | null;
  } | null;
  singleFile: SavedSingleFile | null;
  selection: Selection;
  parameters: SessionState["parameters"];
  guessedParameters?: SessionState["guessedParameters"];
  customBounds: SessionState["customBounds"];
  held: SessionState["held"];
  interpolation: { enabled: boolean };
  chartPanels: readonly ChartTab[];
  savedModelSettings: Record<string, ModelSettings>;
  /** The start of the last fit and where it came from. */
  fitStart: {
    values: Record<string, number> | null;
    net: NetRange | null;
    numerical: boolean;
  };
  /** The last finished fit, with the request that made it, or null with none. */
  fit: { request: FitRequest | null; result: FitResult } | null;
}

/** Version 3 is reserved for composition; versions 2 and 4 require explicit DPB identity. */
export interface SessionFile {
  format: typeof SESSION_FORMAT;
  version: 1 | 2 | 4;
  /** When it was saved, as ISO 8601. */
  saved: string;
  /** The app's and the API's versions with their commits, as exports name them. */
  appVersion: string;
  apiVersion: string | null;
  /**
   * SHA-256 of `content`, as JSON with sorted keys, in hex. It shows a file damaged or edited by
   * accident; anyone can work it out again, so it is no proof that nobody changed the file.
   */
  checksum: string;
  content: SessionContent;
}

/** Why a file cannot be loaded, as a code for a text. */
export type SessionFileProblem =
  | "too_large"
  | "not_json"
  | "not_a_session"
  | "newer_version"
  | "invalid"
  | "checksum";

/** JSON with the keys of each object sorted, so the same content gives the same text. */
export function canonical(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonical).join(",")}]`;
  }
  if (typeof value === "object" && value !== null) {
    const entries = Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

/** The checksum of a session's content. */
export function checksum(content: SessionContent): Promise<string> {
  return sha256Hex(new TextEncoder().encode(canonical(content)));
}

function savedSingleFile(file: SingleFile | null): SavedSingleFile | null {
  return file === null
    ? null
    : {
        name: file.name,
        text: file.text,
        mapping: file.mapping,
        table: file.table,
      };
}

/**
 * The session as a file. The request of its fit is the one kept from a restored file while that
 * fit stands, and otherwise that of the fit's start values, built as a fit from them would be.
 */
export async function sessionFile(
  state: SessionState,
  versions: { appVersion: string; apiVersion: string | null; saved: string },
  fitRequestOf: (state: SessionState) => FitRequest | null,
): Promise<SessionFile> {
  const done = state.fit.status === "done" ? state.fit.result : null;
  const kept =
    done !== null && state.restored?.result === done
      ? state.restored.request
      : undefined;
  const request =
    kept !== undefined
      ? kept
      : done === null ||
          state.fitStartValues === null ||
          state.selection.fitMode === null
        ? null
        : fitRequestOf({
            ...state,
            parameters: {
              ...state.parameters,
              [state.selection.fitMode]: state.fitStartValues,
            },
          });
  const content: SessionContent = {
    ...(state.selection.parameterization === undefined
      ? {}
      : { ionizedBInputs: true }),
    dataMode: state.dataMode,
    data: state.data,
    otherSource:
      state.otherSource === null
        ? null
        : {
            data: state.otherSource.data,
            singleFile: savedSingleFile(state.otherSource.singleFile),
          },
    singleFile: savedSingleFile(state.singleFile),
    selection: state.selection,
    parameters: state.parameters,
    guessedParameters: state.guessedParameters,
    customBounds: state.customBounds,
    held: state.held,
    interpolation: { enabled: state.interpolation.enabled },
    chartPanels: state.chartPanels,
    savedModelSettings: state.savedModelSettings,
    fitStart: {
      values: state.fitStartValues,
      net: state.fitStartNet,
      numerical: state.fitStartNumerical,
    },
    fit: done === null ? null : { request, result: done },
  };
  return {
    format: SESSION_FORMAT,
    version: state.selection.parameterization !== undefined ? 4 : 1,
    saved: versions.saved,
    appVersion: versions.appVersion,
    apiVersion: versions.apiVersion,
    checksum: await checksum(content),
    content,
  };
}

// The checks below follow the types the app reads, so that nothing in a file it accepts can make
// a screen fail later. Numbers must be finite: JSON can spell 1e999, which reads as Infinity.

type Check = (value: unknown) => boolean;

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isNumber: Check = (value) =>
  typeof value === "number" && Number.isFinite(value);
const isString: Check = (value) => typeof value === "string";
const isBoolean: Check = (value) => typeof value === "boolean";
const isInteger: Check = (value) => Number.isInteger(value);
const orNull =
  (check: Check): Check =>
  (value) =>
    value === null || check(value);
const optional =
  (check: Check): Check =>
  (value) =>
    value === undefined || check(value);
const arrayOf =
  (check: Check, max = Number.POSITIVE_INFINITY): Check =>
  (value) =>
    Array.isArray(value) && value.length <= max && value.every(check);
const recordOf =
  (check: Check): Check =>
  (value) =>
    isObject(value) && Object.values(value).every(check);
const shape =
  (fields: Record<string, Check>): Check =>
  (value) =>
    isObject(value) &&
    Object.entries(fields).every(([key, check]) => check(value[key]));
const oneOf =
  (...allowed: readonly unknown[]): Check =>
  (value) =>
    allowed.includes(value);

const ROLES = ["temperature", "seebeck", "resistivity", "conductivity", "hall"];
const isQuantity = oneOf(...QUANTITIES);

const isColumn = shape({
  column: isInteger,
  role: oneOf(...ROLES),
  unit: optional(orNull(isString)),
  unit_source: optional(orNull(oneOf("chosen", "header", "default"))),
});

const isIssue = shape({ code: isString });

const isMeasurement: Check = (value) =>
  shape({
    temperature_k: arrayOf(isNumber, MAX_POINTS),
    values: arrayOf(isNumber, MAX_POINTS),
    points: isInteger,
    min_temperature_k: isNumber,
    max_temperature_k: isNumber,
    loaded_as: optional(oneOf(...QUANTITIES, "conductivity")),
  })(value) &&
  isObject(value) &&
  (value.temperature_k as unknown[]).length ===
    (value.values as unknown[]).length;

const isSessionData = shape({
  measurement: isMeasurement,
  source: (value) =>
    shape({ kind: oneOf("file"), name: isString })(value) ||
    shape({ kind: oneOf("demo"), messageKey: isString })(value),
  extrapolated: isBoolean,
  text: isString,
  mapping: optional(arrayOf(isColumn)),
  readAs: optional(arrayOf(isColumn)),
  unitDoubts: optional(
    arrayOf(
      shape({
        code: oneOf("implausible_magnitude", "unit_assumed"),
        direction: optional(orNull(oneOf("above", "below"))),
      }),
    ),
  ),
  firstRow: optional(
    shape({ written: arrayOf(isString), si: arrayOf(orNull(isNumber)) }),
  ),
  unitConfirmed: optional(isBoolean),
});

const isData: Check = (value) =>
  isObject(value) &&
  Object.entries(value).every(
    ([quantity, entry]) => isQuantity(quantity) && isSessionData(entry),
  );

const isTable = shape({
  headers: optional(orNull(arrayOf(isString))),
  column_count: isInteger,
  row_count: isInteger,
  preview: arrayOf(arrayOf(isNumber)),
  preview_text: optional(arrayOf(arrayOf(isString))),
  preview_si: arrayOf(arrayOf(orNull(isNumber))),
  mapping: arrayOf(isColumn),
  measurements: recordOf(isMeasurement),
  errors: arrayOf(isIssue),
  warnings: arrayOf(isIssue),
  warnings_omitted: isInteger,
  interpolated: isObject,
  interpolation_failed: arrayOf(isQuantity),
  interpolation_failure_reasons: isObject,
});

const isSingleFile = orNull(
  shape({
    name: isString,
    text: isString,
    mapping: arrayOf(isColumn),
    table: orNull(isTable),
  }),
);

const isSelection = shape({
  parameterization: optional(oneOf("explicit_density_v1", "explicit_fermi_v1")),
  carrierType: optional(oneOf("p", "n")),
  bandConfiguration: optional(oneOf("vb_vb", "vb_cb", "cb_cb")),
  netElectronDensityPerM3: optional(isNumber),
  fitAbsoluteMass: optional(isBoolean),
  legacySource: optional(isString),
  algorithm: optional(oneOf("verified-sequential-v2", "legacy-sequential-v1")),
  model: orNull(isString),
  fitMode: orNull(isString),
  scattering: orNull(isString),
  band1Degeneracy: isNumber,
  band2Degeneracy: isNumber,
  minTemperatureK: orNull(isNumber),
  maxTemperatureK: orNull(isNumber),
});

const isResult = shape({
  parameters: recordOf(orNull(isNumber)),
  status: oneOf("converged", "iteration_limit", "stopped", "failed", "stalled"),
  core_version: optional(isString),
  iterations: optional(orNull(isInteger)),
  message: optional(orNull(isString)),
  parameter_errors: recordOf(isNumber),
  at_bounds: arrayOf(isString),
  known_issues: arrayOf(isString),
  // The app reads neither, or not without a fallback, and an older server sent neither.
  held: optional(arrayOf(isString)),
  algorithm: optional(oneOf("verified-sequential-v2", "legacy-sequential-v1")),
  diagnostics: optional(orNull(isObject)),
  parameter_status: optional(recordOf(isString)),
  uncertainty: optional(oneOf("not_assessed")),
  last_changes: optional(recordOf(orNull(isNumber))),
});

const isRequest = shape({
  model: isString,
  fit_mode: isString,
  start: recordOf(isNumber),
  min_temperature_k: isNumber,
  max_temperature_k: isNumber,
  measurements: recordOf(
    shape({
      temperature_k: arrayOf(isNumber, MAX_POINTS),
      values: arrayOf(isNumber, MAX_POINTS),
    }),
  ),
});

const isContent = shape({
  ionizedBInputs: optional(isBoolean),
  dataMode: oneOf("separate", "single"),
  data: isData,
  otherSource: orNull(shape({ data: isData, singleFile: isSingleFile })),
  singleFile: isSingleFile,
  selection: isSelection,
  parameters: recordOf(recordOf(isNumber)),
  guessedParameters: optional(recordOf(recordOf(isNumber))),
  customBounds: recordOf(recordOf(shape({ lower: isNumber, upper: isNumber }))),
  held: recordOf(arrayOf(isString)),
  interpolation: shape({ enabled: isBoolean }),
  chartPanels: arrayOf(isString),
  savedModelSettings: recordOf(
    shape({
      fitMode: orNull(isString),
      scattering: orNull(isString),
      band1Degeneracy: isNumber,
      band2Degeneracy: isNumber,
    }),
  ),
  fitStart: shape({
    values: orNull(recordOf(isNumber)),
    net: orNull(
      shape({ min_temperature_k: isNumber, max_temperature_k: isNumber }),
    ),
    numerical: isBoolean,
  }),
  fit: orNull(shape({ request: orNull(isRequest), result: isResult })),
});

const isSessionFile = shape({
  saved: isString,
  appVersion: isString,
  apiVersion: orNull(isString),
  checksum: isString,
  content: isContent,
});

/**
 * A session from a file's text, or why it cannot be loaded. It checks the size, the format and its
 * version, migrates an older one, checks every field the app reads, and the checksum, so a file
 * that is broken is refused rather than loaded wrong.
 */
export async function readSessionFile(
  text: string,
): Promise<{ session: SessionFile } | { problem: SessionFileProblem }> {
  if (text.length > MAX_SESSION_BYTES) {
    return { problem: "too_large" };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { problem: "not_json" };
  }
  if (!isObject(parsed) || parsed.format !== SESSION_FORMAT) {
    return { problem: "not_a_session" };
  }
  const file = parsed;
  if (!isInteger(file.version)) {
    return { problem: "invalid" };
  }
  if ((file.version as number) > SESSION_VERSION) {
    return { problem: "newer_version" };
  }
  if (![1, 2, 4].includes(file.version as number))
    return { problem: "invalid" };
  if (!isSessionFile(file)) {
    return { problem: "invalid" };
  }
  const session = file as unknown as SessionFile;
  if ((session.version === 4) !== (session.content.ionizedBInputs === true))
    return { problem: "invalid" };
  const selected = session.content.selection;
  const explicit = selected.parameterization !== undefined;
  if (
    (session.version === 1 && explicit) ||
    ((session.version === 2 || session.version === 4) &&
      selected.model === "dpb" &&
      !explicit)
  )
    return { problem: "invalid" };
  if (
    explicit &&
    (selected.bandConfiguration === undefined ||
      (selected.parameterization === "explicit_density_v1" &&
        selected.netElectronDensityPerM3 === undefined) ||
      selected.band1Degeneracy <= 0 ||
      selected.band2Degeneracy <= 0 ||
      !Number.isInteger(selected.band1Degeneracy) ||
      !Number.isInteger(selected.band2Degeneracy))
  )
    return { problem: "invalid" };
  if ((await checksum(session.content)) !== session.checksum) {
    return { problem: "checksum" };
  }
  return { session };
}

/** What a checked file gives the store to restore. */
export function restoredSession(content: SessionContent): RestoredSession {
  const compatible = historicalIonizedControls(content);
  return {
    dataMode: content.dataMode,
    data: content.data,
    singleFile: content.singleFile,
    otherSource: content.otherSource,
    chartPanels: content.chartPanels,
    savedModelSettings: content.savedModelSettings,
    selection: content.selection,
    parameters: compatible.parameters,
    guessedParameters: content.guessedParameters ?? {},
    customBounds: compatible.customBounds,
    held: content.held,
    interpolationEnabled: content.interpolation.enabled,
    fitStart: content.fitStart,
    result: content.fit?.result ?? null,
    request: content.fit?.request ?? null,
  };
}

/** Restore controls without rewriting the saved fit or its original submitted inputs. */
export function historicalIonizedControls(content: SessionContent) {
  if (content.ionizedBInputs === true)
    return {
      parameters: content.parameters,
      customBounds: content.customBounds,
    };
  const ionized =
    (content.selection.model === "dpb"
      ? content.selection.scattering
      : content.savedModelSettings.dpb?.scattering) === "ionized";
  const parameters =
    ionized || content.parameters.dpb_s?.B !== undefined
      ? { ...content.parameters, dpb_s: { ...content.parameters.dpb_s, B: 1 } }
      : content.parameters;
  if (!ionized) return { parameters, customBounds: content.customBounds };
  const customBounds = { ...content.customBounds };
  for (const mode of ["dpb_s_rho", "dpb_s_rho_rh"]) {
    customBounds[mode] = {
      ...customBounds[mode],
      B: customBounds[mode]?.B ??
        (content.fit?.request?.fit_mode === mode
          ? content.fit.request.bounds?.B
          : undefined) ?? { lower: 0.9, upper: 1.1 },
    };
  }
  return { parameters, customBounds };
}
