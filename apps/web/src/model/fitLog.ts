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
  if (status === "iteration_limit") {
    return {
      title: log.limit,
      text: log.limitText(mode.max_iterations ?? iterations ?? 0),
    };
  }
  if (!mode.iterative) {
    return { title: log.done, text: log.singlePass };
  }
  return {
    title: log.converged,
    text:
      mode.threshold === null || mode.threshold === undefined
        ? log.convergedText
        : log.convergedBelow(formatNumber(mode.threshold * 100), iterations),
  };
}

/**
 * What a fit did, from its start values to why it ended. The steps are the solver runs of the
 * mode's description, so a new mode needs no change here. A stopped fit ran only its loop.
 */
export function fitLog(
  mode: FitModeDescription,
  scattering: string | null,
  fit: FitState,
  startNet: NetRange | null,
): LogStep[] {
  const iterations = iterationsOf(fit);
  const fitted = new Set(
    visibleParameters(mode, scattering)
      .filter(({ role }) => role === "fitted")
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
        ? log.fromValues
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
