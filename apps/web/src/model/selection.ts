import type { components } from "@seeband/api-client";

import type { ModelSettings } from "@/session/store";

type Schemas = components["schemas"];
export type ModelDescription = Schemas["ModelResponse"];
export type FitModeDescription = Schemas["FitModeResponse"];

// The design's first state. If a model goes, the first of the descriptions takes over.
const FIRST_MODEL = "dpb";
const FIRST_FIT_MODE = "dpb_s_rho";

export function firstModel(
  models: readonly ModelDescription[],
): ModelDescription | undefined {
  return models.find((model) => model.id === FIRST_MODEL) ?? models[0];
}

export function fitModeOf(
  model: ModelDescription | undefined,
  id: string | null,
): FitModeDescription | undefined {
  return model?.fit_modes.find((mode) => mode.id === id);
}

function usableMode(
  model: ModelDescription,
  id: string | null | undefined,
): FitModeDescription | undefined {
  const named = model.fit_modes.find((mode) => mode.id === id);
  return named !== undefined && !named.disabled ? named : undefined;
}

/**
 * Settings that a model can really use: those given where they still hold, and otherwise its own
 * defaults. A disabled mode is never chosen. With no mode that can run, the fit mode is null.
 */
export function settingsFor(
  model: ModelDescription,
  wanted?: Partial<ModelSettings>,
): ModelSettings {
  const mode =
    usableMode(model, wanted?.fitMode) ??
    usableMode(model, FIRST_FIT_MODE) ??
    model.fit_modes.find((candidate) => !candidate.disabled);
  const scattering =
    wanted?.scattering != null && mode?.scattering.includes(wanted.scattering)
      ? wanted.scattering
      : (mode?.default_scattering ?? null);
  return {
    fitMode: mode?.id ?? null,
    scattering,
    band1Degeneracy:
      mode?.degeneracy == null
        ? 1
        : (wanted?.band1Degeneracy ?? mode.degeneracy.band_1_default),
    band2Degeneracy:
      mode?.degeneracy == null
        ? 1
        : mode.degeneracy.band_2_default == null
          ? 1
          : (wanted?.band2Degeneracy ?? mode.degeneracy.band_2_default),
  };
}
