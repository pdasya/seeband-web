import type { FitRequest } from "@/api/client";
import {
  QUANTITIES,
  type DataMode,
  type FitResult,
  type NetRange,
  type Quantity,
  type Selection,
  type SessionData,
  type SessionState,
  type SingleFile,
} from "@/session/store";

/**
 * A session as a file, which the user keeps and loads back: nothing is stored on the server.
 *
 * It holds the data as read, with their text and how each column was read, the choices of the fit
 * screen, and the last finished fit with the request that made it. Loading it gives the same
 * session back; a fit it holds is shown as it was, never run again by a newer model on its own.
 * Each version of the format has a migration to the next, so an old file still loads.
 */
export const SESSION_FORMAT = "seeband-session";
export const SESSION_VERSION = 1;
/** Files are measured in characters, which a JSON text of this size is far below in practice. */
export const MAX_SESSION_CHARACTERS = 30_000_000;

/** What a session file holds, in version 1. */
export interface SessionFileV1 {
  format: typeof SESSION_FORMAT;
  version: 1;
  /** When it was saved, as ISO 8601. */
  saved: string;
  /** The app's and the API's versions with their commits, as exports name them. */
  appVersion: string;
  apiVersion: string | null;
  /** SHA-256 of the measurements as the fit reads them, in hex, so that a changed file shows. */
  dataHash: string;
  dataMode: DataMode;
  data: Partial<Record<Quantity, SessionData>>;
  singleFile: Pick<SingleFile, "name" | "text" | "mapping" | "table"> | null;
  selection: Selection;
  parameters: SessionState["parameters"];
  customBounds: SessionState["customBounds"];
  held: SessionState["held"];
  interpolation: { enabled: boolean };
  /** The start of the last fit and where it came from. */
  fitStart: {
    values: Record<string, number> | null;
    net: NetRange | null;
    numerical: boolean;
  };
  /** The last finished fit, with the request that made it, or null with none. */
  fit: { request: FitRequest | null; result: FitResult } | null;
}

export type SessionFile = SessionFileV1;

/** Why a file cannot be loaded, as a code for a text. */
export type SessionFileProblem =
  | "too_large"
  | "not_json"
  | "not_a_session"
  | "newer_version"
  | "invalid"
  | "data_changed";

/**
 * Each migration takes a file of one version to the next. Version 1 is the first, so there are
 * none yet; a change of the format adds one here, and a test that an old file still loads.
 */
const MIGRATIONS: Readonly<
  Record<number, (old: Record<string, unknown>) => Record<string, unknown>>
> = {};

const hex = (bytes: ArrayBuffer) =>
  [...new Uint8Array(bytes)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");

/**
 * SHA-256 of the measurements, as JSON of [quantity, temperatures, values] in a fixed order, so the
 * same data give the same hash whatever else the file holds.
 */
export async function dataHash(
  data: Partial<Record<Quantity, SessionData>>,
): Promise<string> {
  const normalised = QUANTITIES.flatMap((quantity) => {
    const entry = data[quantity];
    return entry === undefined
      ? []
      : [
          [
            quantity,
            entry.measurement.loaded_as ?? quantity,
            entry.measurement.temperature_k,
            entry.measurement.values,
          ],
        ];
  });
  const bytes = new TextEncoder().encode(JSON.stringify(normalised));
  return hex(await crypto.subtle.digest("SHA-256", bytes));
}

/** The session as a file, with the request of its last fit if it has one. */
export async function sessionFile(
  state: SessionState,
  versions: { appVersion: string; apiVersion: string | null; saved: string },
  fitRequestOf: (state: SessionState) => FitRequest | null,
): Promise<SessionFile> {
  const done = state.fit.status === "done" ? state.fit.result : null;
  // The request of a finished fit is that of its start values, as a fit started from them.
  const request =
    done === null ||
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
  return {
    format: SESSION_FORMAT,
    version: SESSION_VERSION,
    saved: versions.saved,
    appVersion: versions.appVersion,
    apiVersion: versions.apiVersion,
    dataHash: await dataHash(state.data),
    dataMode: state.dataMode,
    data: state.data,
    singleFile:
      state.singleFile === null
        ? null
        : {
            name: state.singleFile.name,
            text: state.singleFile.text,
            mapping: state.singleFile.mapping,
            table: state.singleFile.table,
          },
    selection: state.selection,
    parameters: state.parameters,
    customBounds: state.customBounds,
    held: state.held,
    interpolation: { enabled: state.interpolation.enabled },
    fitStart: {
      values: state.fitStartValues,
      net: state.fitStartNet,
      numerical: state.fitStartNumerical,
    },
    fit: done === null ? null : { request, result: done },
  };
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isNumberArray = (value: unknown): value is (number | null)[] =>
  Array.isArray(value) &&
  value.every((item) => item === null || typeof item === "number");

const isNumberRecord = (value: unknown): value is Record<string, number> =>
  isObject(value) &&
  Object.values(value).every((item) => typeof item === "number");

function validData(value: unknown): boolean {
  if (!isObject(value)) {
    return false;
  }
  return Object.entries(value).every(([quantity, entry]) => {
    if (!QUANTITIES.includes(quantity as Quantity) || !isObject(entry)) {
      return false;
    }
    const { measurement, source, text } = entry;
    return (
      isObject(measurement) &&
      isNumberArray(measurement.temperature_k) &&
      isNumberArray(measurement.values) &&
      measurement.temperature_k.length === measurement.values.length &&
      isObject(source) &&
      (source.kind === "file" || source.kind === "demo") &&
      typeof text === "string"
    );
  });
}

/** Whether a parsed file of the current version has the shape the app reads. */
function validSession(
  value: Record<string, unknown>,
): value is SessionFile & Record<string, unknown> {
  const { selection, fitStart, interpolation, fit } = value;
  return (
    typeof value.saved === "string" &&
    typeof value.appVersion === "string" &&
    (value.apiVersion === null || typeof value.apiVersion === "string") &&
    typeof value.dataHash === "string" &&
    (value.dataMode === "separate" || value.dataMode === "single") &&
    validData(value.data) &&
    (value.singleFile === null ||
      (isObject(value.singleFile) &&
        typeof value.singleFile.name === "string" &&
        typeof value.singleFile.text === "string" &&
        Array.isArray(value.singleFile.mapping))) &&
    isObject(selection) &&
    typeof selection.band1Degeneracy === "number" &&
    typeof selection.band2Degeneracy === "number" &&
    isObject(value.parameters) &&
    Object.values(value.parameters).every(isNumberRecord) &&
    isObject(value.customBounds) &&
    isObject(value.held) &&
    Object.values(value.held).every(
      (names) =>
        Array.isArray(names) && names.every((name) => typeof name === "string"),
    ) &&
    isObject(interpolation) &&
    typeof interpolation.enabled === "boolean" &&
    isObject(fitStart) &&
    (fitStart.values === null || isNumberRecord(fitStart.values)) &&
    typeof fitStart.numerical === "boolean" &&
    (fit === null ||
      (isObject(fit) &&
        isObject(fit.result) &&
        typeof fit.result.status === "string" &&
        isObject(fit.result.parameters)))
  );
}

/**
 * A session from a file's text, or why it cannot be loaded. It checks the size, the format and its
 * version, migrates an older one, checks the shape, and that the data still have their hash, so a
 * file changed by hand, or broken, is refused rather than loaded wrong.
 */
export async function readSessionFile(
  text: string,
): Promise<{ session: SessionFile } | { problem: SessionFileProblem }> {
  if (text.length > MAX_SESSION_CHARACTERS) {
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
  let file = parsed;
  if (typeof file.version !== "number" || !Number.isInteger(file.version)) {
    return { problem: "invalid" };
  }
  if (file.version > SESSION_VERSION) {
    return { problem: "newer_version" };
  }
  while ((file.version as number) < SESSION_VERSION) {
    const migrate = MIGRATIONS[file.version as number];
    if (migrate === undefined) {
      return { problem: "invalid" };
    }
    file = migrate(file);
  }
  if (!validSession(file)) {
    return { problem: "invalid" };
  }
  if ((await dataHash(file.data)) !== file.dataHash) {
    return { problem: "data_changed" };
  }
  return { session: file };
}
