import { Badge } from "@/components/ui/badge";
import { STRINGS } from "@/strings";

export type FitStatus = keyof typeof STRINGS.status;

const VARIANTS = {
  manual: "neutral",
  running: "info",
  converged: "success",
  iterationLimit: "warning",
  stopped: "neutral",
  failed: "destructive",
  suggested: "suggestion",
} as const satisfies Record<FitStatus, string>;

/** `converged` means that a fit ended normally, not that its result is sound. */
export function StatusBadge({
  status,
  detail,
}: {
  status: FitStatus;
  detail?: string;
}) {
  const text = STRINGS.status[status];
  return (
    <Badge variant={VARIANTS[status]} role="status">
      {detail === undefined ? text : `${text} ${detail}`}
    </Badge>
  );
}
