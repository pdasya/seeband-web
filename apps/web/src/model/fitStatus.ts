import type { FitBlocker } from "@/model/fitRequest";
import type { FitState, Quantity } from "@/session/store";
import type { FitStatus } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const { fit: text, data: dataText } = STRINGS;

export interface FitBadge {
  status: FitStatus;
  detail?: string;
}

function atIteration(iterative: boolean, iteration: number | null) {
  return iterative && iteration !== null ? iteration : null;
}

/** A single-pass mode has no iterations, so it never shows a counter. */
export function fitBadge(fit: FitState, iterative: boolean): FitBadge {
  switch (fit.status) {
    case "idle":
      return { status: "manual" };
    case "waiting":
      return { status: "running", detail: text.queued };
    case "running": {
      const iteration = atIteration(iterative, fit.iteration);
      return iteration === null
        ? { status: "running" }
        : { status: "running", detail: text.atIteration(iteration) };
    }
    case "stopped": {
      const iteration = atIteration(iterative, fit.iteration);
      return iteration === null
        ? { status: "stopped" }
        : { status: "stopped", detail: text.stoppedAt(iteration) };
    }
    case "failed":
      return { status: "failed" };
    case "done": {
      const { status, iterations } = fit.result;
      if (status === "iteration_limit") {
        return { status: "iterationLimit" };
      }
      if (status === "failed") {
        return { status: "failed" };
      }
      if (status === "stopped") {
        return { status: "stopped" };
      }
      const count = atIteration(iterative, iterations ?? null);
      return count === null
        ? { status: "converged" }
        : { status: "converged", detail: text.convergedIn(count) };
    }
    default:
      return { status: "manual" };
  }
}

/** What went wrong, in our own words, as the server's text is for developers. */
export function fitFailureText(fit: FitState): string | null {
  if (fit.status === "done") {
    if (fit.result.status !== "failed") {
      return null;
    }
    const fixed: Record<string, string> = text.resultFailures;
    return fixed[fit.result.message ?? ""] ?? text.resultFailed;
  }
  if (fit.status !== "failed") {
    return null;
  }
  const known: Record<string, string> = text.failures;
  return known[fit.failure.code] ?? text.failureOther;
}

function symbols(quantities: readonly Quantity[]): string {
  return quantities
    .map((quantity) => dataText.quantities[quantity].symbol)
    .join(", ");
}

/** Why Run fit cannot be pressed. */
export function fitBlockerText(blocker: FitBlocker): string {
  switch (blocker.reason) {
    case "no_mode":
      return text.blockers.noMode;
    case "interpolating":
      return text.blockers.interpolating;
    case "missing_data":
      return `${text.blockers.missingData} ${symbols(blocker.quantities)}.`;
    case "not_interpolated":
      return `${text.blockers.notInterpolated} ${symbols(blocker.quantities)}.`;
    case "no_points_in_range":
      return `${text.blockers.noPointsInRange} ${symbols(blocker.quantities)}.`;
    default:
      return text.blockers.noMode;
  }
}
