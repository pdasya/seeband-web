// @vitest-environment node
import { describe, expect, test } from "vitest";

import { ApiError } from "@/api/errors";
import {
  errorsAreAboutTheMapping,
  failureMessage,
  issueMessage,
  noDataMessages,
} from "@/data/messages";
import { FileReadError } from "@/data/readFile";
import { STRINGS } from "@/strings";

const { data } = STRINGS;

describe("issueMessage", () => {
  test("names the line", () => {
    expect(issueMessage({ code: "not_numeric", line: 3, column: 1 })).toBe(
      `Line 3: ${data.issues.not_numeric}`,
    );
  });

  test("names the column, from 1, where a file can have several", () => {
    expect(issueMessage({ code: "unit_differs", column: 2 })).toBe(
      `Column 3: ${data.issues.unit_differs}`,
    );
  });

  test("leaves out a column that does not help", () => {
    expect(issueMessage({ code: "unsorted_temperature", column: 0 })).toBe(
      data.issues.unsorted_temperature,
    );
  });
});

describe("errorsAreAboutTheMapping", () => {
  test("only the mapping's own errors count", () => {
    expect(
      errorsAreAboutTheMapping([
        { code: "missing_temperature" },
        { code: "repeated_role", column: 1 },
      ]),
    ).toBe(true);
    expect(
      errorsAreAboutTheMapping([
        { code: "missing_temperature" },
        { code: "not_numeric", line: 2 },
      ]),
    ).toBe(false);
  });
});

describe("noDataMessages", () => {
  test("errors alone say why, with warnings left out", () => {
    expect(
      noDataMessages(
        [{ code: "not_numeric", line: 3 }],
        [{ code: "few_rows" }, { code: "no_quantity" }],
      ),
    ).toEqual([`Line 3: ${data.issues.not_numeric}`]);
  });

  test("warnings do not use up the room for errors", () => {
    const errors = Array.from({ length: 5 }, (_, index) => ({
      code: "not_numeric" as const,
      line: index + 2,
    }));

    const messages = noDataMessages(errors, [{ code: "few_rows" }]);

    expect(messages).toHaveLength(4);
    expect(messages.at(-1)).toBe(`${data.andMore} 2`);
  });

  test("a wrong quantity says so once, with no talk of a neural net", () => {
    expect(
      noDataMessages(
        [],
        [
          { code: "few_rows" },
          { code: "expected_not_found" },
          { code: "no_quantity" },
        ],
      ),
    ).toEqual([data.quantityNotFound]);
  });

  test("what may explain a missing quantity stays", () => {
    expect(
      noDataMessages(
        [],
        [{ code: "unit_differs", column: 1 }, { code: "no_quantity" }],
      ),
    ).toEqual([data.quantityNotFound, `Column 2: ${data.issues.unit_differs}`]);
  });
});

describe("failureMessage", () => {
  test.each([
    ["a bad gateway", new ApiError(502, "unexpected_response", "x")],
    ["a timeout", new ApiError(504, "calculation_timeout", "x")],
    ["a worker that died", new ApiError(503, "calculation_unavailable", "x")],
    ["an internal error", new ApiError(500, "internal_error", "x")],
  ])("%s does not blame the file", (_, error) => {
    expect(failureMessage(error)).toBe(data.serverUnavailable);
  });

  test.each([
    [
      "too many rows",
      new ApiError(422, "invalid_parse_request", "x", [
        { location: ["body"], code: "too_many_rows", message: "x" },
      ]),
      data.tooManyRows,
    ],
    [
      "a text too long",
      new ApiError(422, "validation_error", "x", [
        { location: ["body"], code: "string_too_long", message: "x" },
      ]),
      data.fileProblems.file_too_large,
    ],
    [
      "a body too large",
      new ApiError(413, "request_too_large", "x"),
      data.fileProblems.file_too_large,
    ],
    ["a limit", new ApiError(429, "rate_limited", "x"), data.rateLimited],
    ["no server", new ApiError(0, "network_error", "x"), data.networkError],
    ["another refusal", new ApiError(422, "other", "x"), data.parseFailed],
    [
      "a local problem",
      new FileReadError("wrong_file_type"),
      data.fileProblems.wrong_file_type,
    ],
    ["anything else", new Error("SECRET-VALUE"), data.parseFailed],
  ])("%s has its message", (_, error, expected) => {
    expect(failureMessage(error)).toBe(expected);
  });
});
