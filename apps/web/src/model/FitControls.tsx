import type { KeyboardEvent } from "react";
import {
  AlertCircleIcon,
  PlayIcon,
  RotateCcwIcon,
  SparklesIcon,
  SquareIcon,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fitBadge,
  fitBlockerText,
  fitFailureText,
  missingDataText,
} from "@/model/fitStatus";
import { guessBadge, guessMessages } from "@/model/guessStatus";
import type { useFitControl } from "@/model/useFitControl";
import type { useGuess } from "@/model/useGuess";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const { fit: text } = STRINGS;

type Control = ReturnType<typeof useFitControl>;

/** The badge, which changes with each iteration, and one quiet line that a screen reader reads. */
export function FitStatusBadge({
  control,
  guess,
}: {
  control: Control;
  guess: ReturnType<typeof useGuess>;
}) {
  const badge =
    guessBadge(guess.outcome, control.fit) ??
    fitBadge(control.fit, control.iterative);
  // Before any fit there is no status to show, only what keeps one from running.
  const missing =
    badge.status === "manual" ? missingDataText(control.blocker) : null;
  return (
    <>
      {badge.status !== "manual" && <StatusBadge {...badge} />}
      {missing !== null && <Badge variant="warning">{missing}</Badge>}
      <span role="status" className="sr-only">
        {badge.status === "manual" ? "" : STRINGS.status[badge.status]}
      </span>
    </>
  );
}

function ignoreHeldKey(event: KeyboardEvent) {
  if (event.repeat) {
    event.preventDefault();
  }
}

export function FitActions({
  control,
  guess,
}: {
  control: Control;
  guess: ReturnType<typeof useGuess>;
}) {
  return (
    <>
      <Button variant="ghost" size="sm" onClick={control.reset}>
        <RotateCcwIcon aria-hidden="true" />
        {text.reset}
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={guess.disabled}
        title={guess.title}
        onClick={guess.run}
      >
        <SparklesIcon aria-hidden="true" />
        {text.guess}
      </Button>
      {control.active ? (
        <Button
          size="sm"
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
          size="sm"
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
export function FitMessages({
  control,
  guess,
}: {
  control: Control;
  guess: ReturnType<typeof useGuess>;
}) {
  const failure = fitFailureText(control.fit);
  return (
    <>
      {guessMessages(guess.outcome).map((message) => (
        <p
          key={message}
          aria-live="polite"
          className="m-0 text-xs text-muted-foreground"
        >
          {message}
        </p>
      ))}
      {control.blocker !== null &&
        control.blocker.reason !== "missing_data" &&
        !control.active && (
          <p className="m-0 text-xs text-muted-foreground">
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
