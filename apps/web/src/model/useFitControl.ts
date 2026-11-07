import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";

import { modelsQuery } from "@/api/queries";
import { fitInputsKey, fitRequest } from "@/model/fitRequest";
import { runFit, stopFit } from "@/model/fitRun";
import { dropGuess } from "@/model/guessRun";
import { fitModeOf } from "@/model/selection";
import { isFitActive, useSessionStore } from "@/session/store";

/** Run, Stop and Reset for the fit screen, and what they depend on. */
export function useFitControl() {
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const fit = useSessionStore((state) => state.fit);
  const resetParameters = useSessionStore((state) => state.resetParameters);

  const mode = fitModeOf(
    models?.models.find(({ id }) => id === selection.model),
    selection.fitMode,
  );
  const prepared = useMemo(
    () =>
      fitRequest(
        { selection, parameters, data, interpolation },
        models?.models,
      ),
    [selection, parameters, data, interpolation, models],
  );
  const request = "request" in prepared ? prepared.request : null;
  const inputs = request === null ? null : fitInputsKey(request);
  const active = isFitActive(fit);

  // A change of data, mode or range makes the running fit one of something no longer on screen.
  // Leaving this screen is no such change, and a fit goes on.
  const lastInputs = useRef(inputs);
  useEffect(() => {
    if (lastInputs.current !== inputs) {
      lastInputs.current = inputs;
      if (isFitActive(useSessionStore.getState().fit)) {
        stopFit();
      }
    }
  }, [inputs]);

  return {
    fit,
    active,
    iterative: mode?.iterative === true,
    blocker: "blocked" in prepared ? prepared.blocked : null,
    run: () => {
      if (request !== null) {
        dropGuess();
        void runFit(request);
      }
    },
    stop: stopFit,
    reset: () => {
      if (active) {
        stopFit();
      }
      if (mode !== undefined) {
        resetParameters(mode.id);
      }
    },
  };
}
