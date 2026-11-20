import { formatNumber } from "@/lib/numbers";
import type { FitBlocker } from "@/model/fitRequest";
import { parameterSymbol } from "@/model/parameters";
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

/**
 * A single-pass mode has no iterations, so it never shows a counter. Before a fit there is no status.
 * `threshold` is the stop rule of an iterative legacy fit, a relative change, which its badge names:
 * a fit that met it has only stopped by its rule, which is not a sign that the result is sound.
 */
export function fitBadge(
  fit: FitState,
  iterative: boolean,
  threshold: number | null = null,
): FitBadge | null {
  switch (fit.status) {
    case "idle":
      return null;
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
      if (status === "stalled") {
        return { status: "stalled" };
      }
      if (status === "iteration_limit") {
        return { status: "iterationLimit" };
      }
      if (status === "failed") {
        return { status: "failed" };
      }
      if (status === "stopped") {
        return { status: "stopped" };
      }
      if (fit.result.algorithm === "verified-sequential-v2") {
        return { status: "settled" };
      }
      if (!iterative) {
        return { status: "finished" };
      }
      const count = atIteration(iterative, iterations ?? null);
      const rule =
        iterative && threshold !== null
          ? text.stopRule(
              // As a percent, without the rounding error of the product.
              formatNumber(Number((threshold * 100).toPrecision(12))),
            )
          : null;
      const detail = [rule, count === null ? null : text.convergedIn(count)]
        .filter((part) => part !== null)
        .join(" ");
      return detail === ""
        ? { status: "converged" }
        : { status: "converged", detail };
    }
    default:
      return null;
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

/** The data that a fit mode still lacks, in place of a status while nothing has been fitted. */
export function missingDataText(blocker: FitBlocker | null): string | null {
  return blocker?.reason === "missing_data"
    ? text.missingData(symbols(blocker.quantities))
    : null;
}

/** Why Run fit cannot be pressed. The panel shows missing data as a badge instead. */
export function fitBlockerText(blocker: FitBlocker): string {
  switch (blocker.reason) {
    case "no_mode":
      return text.blockers.noMode;
    case "invalid_density":
      return STRINGS.explicitDpb.densityRequired;
    case "interpolating":
      return text.blockers.interpolating;
    case "missing_data":
      return text.missingData(symbols(blocker.quantities));
    case "unit_in_doubt":
      return text.blockers.unitInDoubt(symbols(blocker.quantities));
    case "not_interpolated":
      return `${text.blockers.notInterpolated} ${symbols(blocker.quantities)}.`;
    case "no_points_in_range":
      return `${text.blockers.noPointsInRange} ${symbols(blocker.quantities)}.`;
    case "all_held":
      return text.blockers.allHeld;
    case "start_outside_bounds":
      return `${text.blockers.startOutsideBounds} ${blocker.parameters.map(parameterSymbol).join(", ")}.`;
    default:
      return text.blockers.noMode;
  }
}
