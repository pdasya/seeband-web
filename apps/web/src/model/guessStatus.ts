import { withDecimalComma, formatNumber } from "@/lib/numbers";
import type { FitBadge } from "@/model/fitStatus";
import type { FitState, GuessOutcome } from "@/session/store";
import { STRINGS } from "@/strings";

const { fit: text } = STRINGS;

function kelvin(value: number): string {
  return withDecimalComma(String(Math.round(value * 10) / 10));
}

/** The badge says where start values came from, until a fit takes over. */
export function guessBadge(
  outcome: GuessOutcome | null,
  fit: FitState,
): FitBadge | null {
  return outcome?.kind === "applied" && fit.status === "idle"
    ? {
        status: "suggested",
        detail: outcome.netRange
          ? text.guessNet(
              formatNumber(outcome.netRange.min_temperature_k),
              formatNumber(outcome.netRange.max_temperature_k),
            )
          : text.guessNumericalBadge,
      }
    : null;
}

export function guessMessages(outcome: GuessOutcome | null): string[] {
  if (outcome === null) {
    return [];
  }
  const warnings = outcome.warnings.flatMap((warning) => {
    const known: Record<string, string> = text.guessWarnings;
    const message = known[warning];
    return message === undefined ? [] : [message];
  });
  switch (outcome.kind) {
    case "unsupported":
      return [text.guessUnsupported[outcome.reason], ...warnings];
    case "applied":
      return outcome.netRange ? warnings : [text.guessNumerical, ...warnings];
    case "no_net":
      return [
        text.guessNoNet(
          kelvin(outcome.firstK),
          kelvin(outcome.lastK),
          outcome.available
            .map(
              ({ min_temperature_k: low, max_temperature_k: high }) =>
                `${formatNumber(low)}–${formatNumber(high)} K`,
            )
            .join(", "),
        ),
        ...warnings,
      ];
    case "not_finite":
      return [text.guessNotFinite, ...warnings];
    case "needs_mass":
      return [text.guessNeedsMass, ...warnings];
    case "failed":
      return [
        outcome.code === "rate_limited" ? text.guessLimited : text.guessFailed,
      ];
    default:
      return [];
  }
}
