import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useSearchParams } from "react-router";

import type { DemoResponse } from "@/api/client";
import { demoQuery, modelsQuery } from "@/api/queries";
import { settingsFor, type ModelDescription } from "@/model/selection";
import {
  holdsFiles,
  QUANTITIES,
  readsFiles,
  useSessionStore,
  type Measurement,
  type Quantity,
  type SessionData,
} from "@/session/store";

/** The rows as a file would hold them, since interpolating sends a file's text to the API again. */
export function demoText({ temperature_k: rows, values }: Measurement): string {
  return rows.map((row, index) => `${row} ${values[index]}`).join("\n");
}

/** What the demo puts in each slot, labelled as demo data. */
export function demoEntries(demo: DemoResponse): [Quantity, SessionData][] {
  return QUANTITIES.flatMap((quantity) => {
    const measurement = demo.measurements[quantity];
    return measurement === undefined
      ? []
      : [
          [
            quantity,
            {
              measurement,
              source: { kind: "demo", messageKey: demo.message_key },
              extrapolated: false,
              text: demoText(measurement),
            },
          ] as [Quantity, SessionData],
        ];
  });
}

/** Opens the fit the demo was made for. Files of the user's are never replaced, or mixed with it. */
function applyDemo(demo: DemoResponse, models: readonly ModelDescription[]) {
  const state = useSessionStore.getState();
  if (holdsFiles(state) || readsFiles(state)) {
    return;
  }
  // Interpolating a table needs its text, so the demo's slots must be the ones on screen.
  state.setDataMode("separate");
  const model = models.find(({ id }) => id === demo.model);
  if (model !== undefined) {
    state.setSelection({
      model: model.id,
      ...settingsFor(model, {
        fitMode: demo.fit_mode,
        scattering: demo.scattering,
      }),
    });
  }
  for (const [quantity, data] of demoEntries(demo)) {
    state.setData(quantity, data);
  }
}

/**
 * Loads the demo when the address asks for it, as the link from Overview does. The address then
 * drops that, so that coming back cannot replace what the user did since. After a failure it stays,
 * so that a reload tries again.
 */
export function useDemoData() {
  const [params, setParams] = useSearchParams();
  const wanted = params.get("demo") === "1";
  const { data: models, isError: modelsFailed } = useQuery(modelsQuery);
  const { data: demo, isError: demoFailed } = useQuery({
    ...demoQuery,
    enabled: wanted,
  });
  const descriptions = models?.models;
  // The model panel sets the first selection, which would replace this one if it came after it.
  const selected = useSessionStore((state) => state.selection.model !== null);

  useEffect(() => {
    if (
      wanted &&
      selected &&
      demo !== undefined &&
      descriptions !== undefined
    ) {
      applyDemo(demo, descriptions);
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.delete("demo");
          return next;
        },
        { replace: true },
      );
    }
  }, [wanted, selected, demo, descriptions, setParams]);

  // With no descriptions it cannot open a fit, however the demo's own request went.
  const failed = wanted && (demoFailed || modelsFailed);
  return { wanted, loading: wanted && !failed, failed };
}
