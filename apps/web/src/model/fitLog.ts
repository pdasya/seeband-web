import { formatNumber } from "@/lib/numbers";
import { parameterSymbol, visibleParameters } from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import type { FitState, NetRange } from "@/session/store";
import { STRINGS } from "@/strings";

const { results: text, data: dataText } = STRINGS;
const { log } = text;

export interface LogStep {
  title: string;
  text: string;
}

/** The iterations a fit went through, as far as it went. */
function iterationsOf(fit: FitState): number | null {
  if (fit.status === "done") {
    return fit.result.iterations ?? null;
  }
  return fit.status === "stopped" || fit.status === "running"
    ? fit.iteration
    : null;
}

/** A relative change as a percent, to two figures, without the noise of binary fractions. */
function percentText(change: number | null): string {
  return change === null
    ? log.notFinite
    : `${formatNumber(Number((change * 100).toPrecision(2)))} %`;
}

/** A threshold as a percent, without the rounding error of the product. */
function thresholdText(threshold: number): string {
  return formatNumber(Number((threshold * 100).toPrecision(12)));
}

/**
 * How much each parameter of a legacy loop changed in its last iteration, as its stop rule
 * compared it, and those above the threshold, which kept the loop going. Empty for other fits.
 */
function changesText(fit: FitState, threshold: number | null): string {
  if (fit.status !== "done") {
    return "";
  }
  const changes = Object.entries(fit.result.last_changes ?? {});
  if (changes.length === 0) {
    return "";
  }
  const listed = changes
    .map(([name, change]) => `${parameterSymbol(name)} ${percentText(change)}`)
    .join(", ");
  const above =
    threshold === null
      ? []
      : changes.filter(([, change]) => change === null || change > threshold);
  const limit =
    fit.result.status === "iteration_limit" ? ` ${log.limitBands}` : "";
  return above.length === 0
    ? ` ${log.changes(listed)}${limit}`
    : ` ${log.changes(listed)} ${log.above(
        thresholdText(threshold ?? 0),
        above.map(([name]) => parameterSymbol(name)).join(", "),
      )}${limit}`;
}

function endOf(
  mode: FitModeDescription,
  fit: FitState,
  iterations: number | null,
): LogStep {
  const stopped = {
    title: log.stopped,
    text: iterations === null ? log.stoppedText : log.stoppedAt(iterations),
  };
  if (fit.status === "stopped") {
    return stopped;
  }
  const status = fit.status === "done" ? fit.result.status : null;
  if (status === "stopped") {
    return stopped;
  }
  const threshold = mode.threshold ?? null;
  if (status === "iteration_limit") {
    return {
      title: log.limit,
      text:
        log.limitText(mode.max_iterations ?? iterations ?? 0) +
        changesText(fit, threshold),
    };
  }
  if (status === "stalled") {
    return {
      title: STRINGS.status.stalled,
      text: STRINGS.fit.diagnostics.stalled,
    };
  }
  if (
    fit.status === "done" &&
    fit.result.algorithm === "verified-sequential-v2" &&
    status === "converged"
  ) {
    return {
      title: STRINGS.status.settled,
      text: STRINGS.fit.diagnostics.settled,
    };
  }
  if (!mode.iterative) {
    return { title: log.done, text: log.singlePass };
  }
  return {
    title: log.converged,
    text:
      fit.status !== "done" ||
      fit.result.algorithm !== "legacy-sequential-v1" ||
      mode.threshold === null ||
      mode.threshold === undefined
        ? log.convergedText
        : log.convergedBelow(thresholdText(mode.threshold), iterations) +
          changesText(fit, threshold),
  };
}

/**
 * What a fit did, from its start values to why it ended. The end names the stop rule, not what it
 * proves: a change of at most the threshold is not a fit that is sound. The steps are the solver
 * runs of the mode's description, so a new mode needs no change here. A stopped fit ran only its
 * loop.
 */
export function fitLog(
  mode: FitModeDescription,
  scattering: string | null,
  fit: FitState,
  startNet: NetRange | null,
  numerical = false,
  held: readonly string[] = [],
): LogStep[] {
  const iterations = iterationsOf(fit);
  // A held parameter keeps its value, so no step finds it.
  const fitted = new Set(
    visibleParameters(mode, scattering)
      .filter(({ role, name }) => role === "fitted" && !held.includes(name))
      .map(({ name }) => name),
  );
  const ended =
    fit.status === "done" &&
    fit.result.status !== "stopped" &&
    fit.result.status !== "failed";
  const start: LogStep = {
    title: log.start,
    text:
      startNet === null
        ? numerical
          ? log.fromNumerical
          : log.fromValues
        : log.fromNet(
            formatNumber(startNet.min_temperature_k),
            formatNumber(startNet.max_temperature_k),
          ),
  };
  const stages = mode.stages.flatMap((stage): LogStep[] => {
    const found = stage.parameters.filter((name) => fitted.has(name));
    if (found.length === 0 || (!ended && !stage.repeats)) {
      return [];
    }
    const symbols = found.map(parameterSymbol).join(", ");
    return [
      {
        title: log.stage(dataText.quantities[stage.quantity].symbol),
        text:
          stage.repeats && iterations !== null
            ? log.findsEach(symbols, iterations)
            : log.finds(symbols),
      },
    ];
  });
  return [start, ...stages, endOf(mode, fit, iterations)];
}
