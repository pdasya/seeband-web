import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { apiClient, type DemoResponse } from "@/api/client";
import { parameterValues } from "@/model/parameters";
import { demoQuery, useModels } from "@/api/queries";
import {
  offersExplicitDpb,
  settingsFor,
  type ModelDescription,
} from "@/model/selection";
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
export async function applyDemo(
  demo: DemoResponse,
  models: readonly ModelDescription[],
  signal?: AbortSignal,
) {
  const state = useSessionStore.getState();
  if (holdsFiles(state) || readsFiles(state)) {
    return;
  }
  const model = models.find(({ id }) => id === demo.model);
  let converted: {
    configuration: Awaited<
      ReturnType<typeof apiClient.migrateDpb>
    >["band_configuration"];
    mass: number;
    fermiEnergy: number;
  } | null = null;
  let band1 = 1;
  let band2 = 1;
  if (model && offersExplicitDpb(model)) {
    // This project-owned synthetic source supplies its absolute scale; measurements never do.
    const legacy = await apiClient.getModels(signal);
    const mode = legacy.models
      .find(({ id }) => id === demo.model)
      ?.fit_modes.find(({ id }) => id === demo.fit_mode);
    if (!mode) throw new Error("Synthetic source mode unavailable");
    const values = {
      ...parameterValues(mode, undefined),
      ...demo.true_parameters,
    };
    const mass = values.m1;
    if (mass === undefined || mass <= 0)
      throw new Error("Synthetic source mass unavailable");
    const fermiEnergy = values.fermi_energy;
    if (fermiEnergy === undefined)
      throw new Error("Synthetic source Fermi energy unavailable");
    band1 = mode.degeneracy?.band_1_default ?? 1;
    band2 = mode.degeneracy?.band_2_default ?? 1;
    const point = await apiClient.migrateDpb(
      {
        parameters: values,
        m1: mass,
        band_1_degeneracy: band1,
        band_2_degeneracy: band2,
      },
      signal,
    );
    if (point.parameters.m1 === undefined)
      throw new Error("Converted synthetic source mass unavailable");
    converted = {
      configuration: point.band_configuration,
      mass: point.parameters.m1,
      fermiEnergy,
    };
  }
  const current = useSessionStore.getState();
  if (
    signal?.aborted ||
    holdsFiles(current) ||
    readsFiles(current) ||
    current.data !== state.data ||
    current.selection !== state.selection ||
    current.parameters !== state.parameters ||
    current.customBounds !== state.customBounds ||
    current.held !== state.held ||
    current.interpolation !== state.interpolation
  )
    return;
  // Interpolating a table needs its text, so the demo's slots must be the ones on screen.
  state.setDataMode("separate");
  if (model !== undefined) {
    state.setSelection({
      model: model.id,
      ...settingsFor(model, {
        fitMode: demo.fit_mode,
        scattering: demo.scattering,
      }),
      ...(converted
        ? {
            parameterization: "explicit_fermi_v1" as const,
            bandConfiguration: converted.configuration,
            netElectronDensityPerM3: undefined,
            carrierType: undefined,
            legacySource: undefined,
            band1Degeneracy: band1,
            band2Degeneracy: band2,
            fitAbsoluteMass: false,
            algorithm: "verified-sequential-v2" as const,
          }
        : {}),
    });
    if (converted) {
      const { mass, fermiEnergy } = converted;
      for (const mode of model.fit_modes)
        state.setParameters(mode.id, {
          ...Object.fromEntries(
            Object.entries(state.parameters[mode.id] ?? {}).filter(([name]) =>
              mode.parameters.some((parameter) => parameter.name === name),
            ),
          ),
          m1: mass,
          fermi_energy: fermiEnergy,
        });
    }
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
  const [initializationFailed, setInitializationFailed] = useState(false);
  const wanted = params.get("demo") === "1";
  const { data: models, isError: modelsFailed } = useModels();
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
      const controller = new AbortController();
      void applyDemo(demo, descriptions, controller.signal)
        .then(() => {
          if (controller.signal.aborted) return;
          setParams(
            (current) => {
              const next = new URLSearchParams(current);
              next.delete("demo");
              return next;
            },
            { replace: true },
          );
        })
        .catch(() => {
          if (!controller.signal.aborted) setInitializationFailed(true);
        });
      return () => controller.abort();
    }
    return undefined;
  }, [wanted, selected, demo, descriptions, setParams]);

  // With no descriptions it cannot open a fit, however the demo's own request went.
  const failed = wanted && (demoFailed || modelsFailed || initializationFailed);
  return { wanted, loading: wanted && !failed, failed };
}
