import { Badge } from "@/components/ui/badge";
import { STRINGS } from "@/strings";

export type FitStatus = keyof typeof STRINGS.status;

const VARIANTS = {
  running: "info",
  converged: "success",
  iterationLimit: "warning",
  stopped: "neutral",
  failed: "destructive",
  suggested: "suggestion",
} as const satisfies Record<FitStatus, string>;

/**
 * `converged` means that a fit ended normally, not that its result is sound.
 *
 * It is not a live region: with an iteration in `detail`, a screen reader would read out each one.
 * FS8 decides what to announce.
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
