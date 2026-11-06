import type { components } from "@seeband/api-client";

import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { FileReadError } from "@/data/readFile";
import { STRINGS } from "@/strings";

type Issue = components["schemas"]["IssueResponse"];

// These name a column, and a file can have several of them.
const ABOUT_A_COLUMN: ReadonlySet<Issue["code"]> = new Set([
  "unit_differs",
  "repeated_header",
  "repeated_role",
]);

// These say something about usable data, not why a file gave none.
const ONLY_INFORMATION: ReadonlySet<Issue["code"]> = new Set([
  "few_rows",
  "unsorted_temperature",
  "duplicate_temperature",
  "preamble_skipped",
]);

// Both say that the slot's quantity is missing, which is said once.
const QUANTITY_MISSING: ReadonlySet<Issue["code"]> = new Set([
  "expected_not_found",
  "no_quantity",
]);

// These are about the choice of columns, and the rest about the file.
const ABOUT_THE_MAPPING: ReadonlySet<Issue["code"]> = new Set([
  "missing_temperature",
  "repeated_role",
]);

export function errorsAreAboutTheMapping(errors: readonly Issue[]): boolean {
  return errors.every(({ code }) => ABOUT_THE_MAPPING.has(code));
}

/** What may explain why no column holds a quantity, out of a file's warnings. */
export function explainingWarnings(warnings: readonly Issue[]): Issue[] {
  return warnings.filter(
    ({ code }) => !ONLY_INFORMATION.has(code) && !QUANTITY_MISSING.has(code),
  );
}

export function issueMessage(issue: Issue): string {
  const { data } = STRINGS;
  const text = data.issues[issue.code];
  if (issue.line !== undefined && issue.line !== null) {
    return `${data.line} ${String(issue.line)}: ${text}`;
  }
  if (
    ABOUT_A_COLUMN.has(issue.code) &&
    issue.column !== undefined &&
    issue.column !== null
  ) {
    return `${data.column} ${String(issue.column + 1)}: ${text}`;
  }
  return text;
}

const MAX_SHOWN_ERRORS = 3;

/**
 * Why a file gave no data. Errors say it, if there are any. Otherwise, it is that the quantity is
 * missing, along with what may explain that. Other warnings would only distract.
 */
export function noDataMessages(
  errors: readonly Issue[],
  warnings: readonly Issue[],
): string[] {
  const { data } = STRINGS;
  if (errors.length > 0) {
    const shown = errors.slice(0, MAX_SHOWN_ERRORS).map(issueMessage);
    const more = errors.length - shown.length;
    return more > 0 ? [...shown, `${data.andMore} ${String(more)}`] : shown;
  }
  const reasons = explainingWarnings(warnings);
  return [data.quantityNotFound, ...reasons.map(issueMessage)];
}

/** Says what went wrong in words, by code. It never shows an error's own text. */
export function failureMessage(error: unknown): string {
  const { data } = STRINGS;
  if (error instanceof FileReadError) {
    return data.fileProblems[error.problem];
  }
  if (!(error instanceof ApiError)) {
    return data.parseFailed;
  }
  switch (error.details[0]?.code ?? error.code) {
    case "invalid_interpolation_range":
      return data.interpolation.invalidRange;
    case "too_many_rows":
      return data.tooManyRows;
    case "request_too_large":
    case "string_too_long":
      return data.fileProblems.file_too_large;
    case "rate_limited":
      return data.rateLimited;
    case NETWORK_ERROR:
      return data.networkError;
    default:
      // This is the server's or a proxy's trouble, such as a 502, and the file may be fine.
      return error.status >= 500 ? data.serverUnavailable : data.parseFailed;
  }
}
