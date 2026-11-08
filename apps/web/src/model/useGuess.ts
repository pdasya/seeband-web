import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { modelsQuery } from "@/api/queries";
import { guessModel, isNewLoad, runGuess } from "@/model/guessRun";
import { currentGuess, isFitActive, useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const { fit: text } = STRINGS;

/** The Initial guess button, and the guess that each new file of S starts, as on the desktop. */
export function useGuess() {
  const { data: models } = useQuery(modelsQuery);
  const measurement = useSessionStore(
    (state) => state.data.seebeck?.measurement,
  );
  const selected = useSessionStore((state) => state.selection.model);
  const model = guessModel(models?.models, selected ?? "");
  const active = useSessionStore((state) => isFitActive(state.fit));
  const pending = useSessionStore((state) => state.guessPending);
  const guess = useSessionStore((state) =>
    state.guess?.model === selected ? currentGuess(state) : null,
  );

  useEffect(() => {
    // Without the descriptions it cannot run yet, so this load still counts when they come.
    if (
      model !== undefined &&
      isNewLoad(measurement, model.id) &&
      measurement
    ) {
      void runGuess(model, measurement);
    }
  }, [model, measurement]);

  const offered = model !== undefined && selected === model.id;
  const title = !offered
    ? text.guessUnavailable
    : measurement === undefined
      ? text.guessNeedsData
      : text.guessHint;

  return {
    title,
    disabled: !offered || measurement === undefined || active || pending,
    run: () => {
      if (model !== undefined && measurement !== undefined) {
        void runGuess(model, measurement);
      }
    },
    outcome: offered ? guess : null,
  };
}
