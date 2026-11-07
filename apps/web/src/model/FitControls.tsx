import type { KeyboardEvent } from "react";
import {
  AlertCircleIcon,
  PlayIcon,
  RotateCcwIcon,
  SquareIcon,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { fitBadge, fitBlockerText, fitFailureText } from "@/model/fitStatus";
import type { useFitControl } from "@/model/useFitControl";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const { fit: text } = STRINGS;

type Control = ReturnType<typeof useFitControl>;

/** The badge, which changes with each iteration, and one quiet line that a screen reader reads. */
export function FitStatusBadge({ control }: { control: Control }) {
  const badge = fitBadge(control.fit, control.iterative);
  return (
    <>
      <StatusBadge {...badge} />
      <span role="status" className="sr-only">
        {control.fit.status === "idle" ? "" : STRINGS.status[badge.status]}
      </span>
    </>
  );
}

function ignoreHeldKey(event: KeyboardEvent) {
  if (event.repeat) {
    event.preventDefault();
  }
}

export function FitActions({ control }: { control: Control }) {
  return (
    <>
      <Button variant="ghost" onClick={control.reset}>
        <RotateCcwIcon aria-hidden="true" />
        {text.reset}
      </Button>
      {control.active ? (
        <Button
          onClick={(event) => {
            // Run turns into this in place, so the rest of a double click must not stop the fit.
            if (event.detail <= 1) {
              control.stop();
            }
          }}
          onKeyDown={ignoreHeldKey}
        >
          <SquareIcon aria-hidden="true" />
          {text.stop}
        </Button>
      ) : (
        <Button
          disabled={control.blocker !== null}
          onClick={control.run}
          onKeyDown={ignoreHeldKey}
        >
          <PlayIcon aria-hidden="true" />
          {text.run}
        </Button>
      )}
    </>
  );
}

/** Why a fit cannot start, or what went wrong with the last one. */
export function FitMessages({ control }: { control: Control }) {
  const failure = fitFailureText(control.fit);
  return (
    <>
      {control.blocker !== null && !control.active && (
        <p className="m-0 text-right text-xs text-muted-foreground">
          {fitBlockerText(control.blocker)}
        </p>
      )}
      {failure !== null && (
        <Alert variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      )}
    </>
  );
}
