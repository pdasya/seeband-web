// @vitest-environment node
import { describe, expect, test } from "vitest";

import {
  fitBadge,
  fitBlockerText,
  fitFailureText,
  missingDataText,
} from "@/model/fitStatus";
import type { FitResult, FitState } from "@/session/store";

const done = (result: Partial<FitResult>): FitState => ({
  status: "done",
  result: {
    parameters: {},
    parameter_errors: {},
    at_bounds: [],
    known_issues: [],
    status: "converged",
    ...result,
  } as FitResult,
});

const running = (iteration: number | null): FitState => ({
  status: "running",
  iteration,
  lastParameters: null,
});

describe("fitBadge", () => {
  test.each<[FitState, boolean, object | null]>([
    [{ status: "idle" }, true, null],
    [
      { status: "waiting" },
      true,
      { status: "running", detail: "waiting in the queue" },
    ],
    [running(null), true, { status: "running" }],
    [running(3), true, { status: "running", detail: "iteration 3" }],
    [
      { status: "stopped", iteration: 3, lastParameters: null },
      true,
      { status: "stopped", detail: "at iteration 3" },
    ],
    [
      { status: "stopped", iteration: null, lastParameters: null },
      true,
      { status: "stopped" },
    ],
    [
      done({ iterations: 5 }),
      true,
      { status: "converged", detail: "in 5 iter." },
    ],
    [done({ iterations: null }), true, { status: "converged" }],
    [done({ status: "iteration_limit" }), true, { status: "iterationLimit" }],
    [done({ status: "failed" }), true, { status: "failed" }],
    [
      {
        status: "failed",
        failure: { code: "x", message: "m", details: [] },
      },
      true,
      { status: "failed" },
    ],
  ])("%j", (fit, iterative, badge) => {
    expect(fitBadge(fit, iterative)).toEqual(badge);
  });

  test("a single-pass mode shows no counter, whatever it receives", () => {
    expect(fitBadge(running(3), false)).toEqual({ status: "running" });
    expect(
      fitBadge(
        { status: "stopped", iteration: 3, lastParameters: null },
        false,
      ),
    ).toEqual({ status: "stopped" });
    expect(fitBadge(done({ iterations: 1 }), false)).toEqual({
      status: "converged",
    });
  });
});

describe("fitFailureText", () => {
  const failed = (code: string): FitState => ({
    status: "failed",
    failure: { code, message: "SECRET-VALUE", details: [] },
  });

  test("has none for a fit that did not fail", () => {
    expect(fitFailureText({ status: "idle" })).toBeNull();
    expect(fitFailureText(done({}))).toBeNull();
    expect(fitFailureText(done({ status: "iteration_limit" }))).toBeNull();
  });

  test("is in our words, with a text for an unknown code", () => {
    expect(fitFailureText(failed("fit_timeout"))).toContain("time limit");
    expect(fitFailureText(failed("stream_ended"))).toContain("connection");
    expect(fitFailureText(failed("fit_queue_full"))).toContain("Too many");
    expect(fitFailureText(failed("client_fit_limit"))).toContain(
      "too many fits running",
    );
    expect(fitFailureText(failed("invalid_fit"))).toContain("refused");
    expect(fitFailureText(failed("anything"))).toBe(
      "The fit failed on the server. Try again.",
    );
    expect(fitFailureText(failed("anything"))).not.toContain("SECRET");
  });

  test("a fit that ended with no result gives the API's fixed reason, and nothing else", () => {
    expect(
      fitFailureText(
        done({
          status: "failed",
          message: "The start values do not fit the bounds.",
        }),
      ),
    ).toBe("The start values do not fit the bounds.");
    expect(
      fitFailureText(done({ status: "failed", message: "SECRET-VALUE" })),
    ).toBe("The fit could not finish. Change the values, and try again.");
    expect(fitFailureText(done({ status: "failed" }))).toBe(
      "The fit could not finish. Change the values, and try again.",
    );
  });
});

describe("fitBlockerText, for bounds", () => {
  test("names each parameter as the user sees it", () => {
    expect(
      fitBlockerText({
        reason: "start_outside_bounds",
        parameters: ["band_gap", "B"],
      }),
    ).toBe("A fit cannot start outside its bounds: E_g, B.");
  });
});

describe("missingDataText", () => {
  test("names what is missing, and nothing for other blockers", () => {
    expect(
      missingDataText({ reason: "missing_data", quantities: ["resistivity"] }),
    ).toBe("Missing data: ρ");
    expect(missingDataText({ reason: "interpolating" })).toBeNull();
    expect(missingDataText(null)).toBeNull();
  });
});

describe("fitBlockerText", () => {
  test("names the quantities", () => {
    expect(
      fitBlockerText({
        reason: "missing_data",
        quantities: ["seebeck", "resistivity"],
      }),
    ).toBe("Missing data: S, ρ");
    expect(
      fitBlockerText({ reason: "no_points_in_range", quantities: ["hall"] }),
    ).toBe("No points in the fit range for R_H.");
  });
});
