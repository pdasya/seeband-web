import { Badge } from "@/components/ui/badge";
import type { FoundStatus, ParameterStatus } from "@/model/resultSummary";
import { STRINGS } from "@/strings";
import { Subscripted } from "@/lib/subscripts";

const text = STRINGS.results.status;

/** No status is green: none of them says that a value is right. */
const FOUND_VARIANTS = {
  estimated: "neutral",
  at_bound: "warning",
  not_determined: "warning",
  did_not_move: "warning",
  not_assessed: "neutral",
  fixed: "neutral",
  held: "neutral",
} as const satisfies Record<FoundStatus, string>;

/** The words of a status, with those for fixed and held as everywhere else. */
export function foundText(status: FoundStatus): string {
  return status === "fixed" || status === "held"
    ? text[status]
    : text.found[status];
}

/**
 * Statuses that say something is wrong with a value, which the fit screen shows beside it. Not
 * assessed is left to the results page: after a stop it would stand beside every value.
 */
export function isWarning(status: ParameterStatus): boolean {
  return status.kind === "found" && FOUND_VARIANTS[status.status] === "warning";
}

/** How a fit found a parameter, as a badge with its words, so that it never rests on colour. */
export function ParameterStatusBadge({ status }: { status: ParameterStatus }) {
  switch (status.kind) {
    case "found":
      return (
        <Badge variant={FOUND_VARIANTS[status.status]}>
          {foundText(status.status)}
        </Badge>
      );
    case "free":
      return (
        <Badge variant="neutral">
          {status.afterFailure ? text.freeAfterFailure : text.free}
        </Badge>
      );
    case "fixed":
      return <Badge variant="neutral">{text.fixed}</Badge>;
    case "held":
      return <Badge variant="neutral">{text.held}</Badge>;
    default:
      return (
        <Badge variant="warning">
          <Subscripted
            text={text.needs(
              status.quantities
                .map((quantity) => STRINGS.data.quantities[quantity].symbol)
                .join(", "),
            )}
          />
        </Badge>
      );
  }
}
