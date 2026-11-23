import { Badge } from "@/components/ui/badge";
import { STRINGS } from "@/strings";

export type FitStatus = keyof typeof STRINGS.status;

const VARIANTS = {
  running: "info",
  converged: "neutral",
  finished: "neutral",
  settled: "neutral",
  stalled: "warning",
  iterationLimit: "warning",
  stopped: "neutral",
  failed: "destructive",
  suggested: "suggestion",
} as const satisfies Record<FitStatus, string>;

/**
 * `converged` means that a fit stopped by its rule, not that its result is sound, so it is not
 * green.
 *
 */
export function StatusBadge({
  status,
  detail,
}: {
  status: FitStatus;
  detail?: string;
}) {
  const text = STRINGS.status[status];
  return (
    <Badge variant={VARIANTS[status]}>
      {detail === undefined ? text : `${text} ${detail}`}
    </Badge>
  );
}
