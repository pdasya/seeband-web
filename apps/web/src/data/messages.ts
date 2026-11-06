import type { components } from "@seeband/api-client";

import { ApiError } from "@/api/errors";
import { FileReadError } from "@/data/readFile";
import { STRINGS } from "@/strings";

type Issue = components["schemas"]["IssueResponse"];

export function issueMessage(issue: Issue): string {
  const text = STRINGS.data.issues[issue.code];
  return issue.line === undefined || issue.line === null
    ? text
    : `${STRINGS.data.line} ${String(issue.line)}: ${text}`;
}

/** Says what went wrong in words, by code. It never shows an error's own text. */
export function failureMessage(error: unknown): string {
  const { data } = STRINGS;
  if (error instanceof FileReadError) {
    return data.fileProblems[error.problem];
  }
  if (error instanceof ApiError) {
    const code = error.details[0]?.code ?? error.code;
    switch (code) {
      case "too_many_rows":
        return data.tooManyRows;
      case "request_too_large":
        return data.fileProblems.file_too_large;
      case "rate_limited":
        return data.rateLimited;
      case "network_error":
        return data.networkError;
      default:
        return data.parseFailed;
    }
  }
  return data.parseFailed;
}
