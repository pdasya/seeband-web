import type { components } from "@seeband/api-client";
import { parameterValues } from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import {
  historicalIonizedControls,
  type SessionContent,
  type SessionFile,
} from "@/session/sessionFile";

export type HallMassConvention = "single_valley" | "all_valley";

/** Keep final fit energies and final mass together; defaults only fill fixed inputs. */
export function legacyVector(
  content: SessionContent,
  description?: FitModeDescription,
): Record<string, number> {
  const mode = content.selection.fitMode ?? "dpb_s_rho";
  const defaults = description ? parameterValues(description, undefined) : {};
  if (content.fit === null)
    return {
      ...defaults,
      ...content.guessedParameters?.[mode],
      ...content.parameters[mode],
    };
  return Object.fromEntries(
    Object.entries({
      ...defaults,
      ...content.fit.request?.start,
      ...content.fit.result.parameters,
    }).filter((entry): entry is [string, number] => entry[1] !== null),
  );
}

export function convertedSession(
  session: SessionFile,
  point: components["schemas"]["ConvertedDpbPoint"],
  band1: number,
  band2: number,
  hallMassConvention?: HallMassConvention,
): SessionContent {
  const content = session.content;
  const mode = content.selection.fitMode ?? "dpb_s_rho";
  const ionized = content.selection.scattering === "ionized";
  const controls = historicalIonizedControls(content, true);
  // These transport controls keep their units when the band representation changes.
  const retained =
    content.selection.scattering === "acPhDis" ? ["A", "B", "C", "D"] : ["B"];
  const parameters = legacyControls(controls.parameters, retained);
  return {
    ionizedBInputs: true,
    ...content,
    selection: {
      ...content.selection,
      algorithm: "verified-sequential-v2",
      parameterization: "explicit_density_v1",
      bandConfiguration: point.band_configuration,
      netElectronDensityPerM3: point.net_electron_density_per_m3,
      band1Degeneracy: band1,
      band2Degeneracy: band2,
      fitAbsoluteMass: false,
      legacySource: historicalSource(
        session,
        hallMassConvention && {
          hallMassConvention,
          sourceValleyCount:
            content.fit?.request?.band_1_degeneracy ??
            content.selection.band1Degeneracy,
          singleValleyMass: point.parameters.m1,
          band1Degeneracy: band1,
          band2Degeneracy: band2,
        },
      ),
    },
    parameters: {
      ...withoutLegacyDpb(content.parameters),
      ...parameters,
      [mode]: {
        ...parameters[mode],
        ...point.parameters,
        ...(ionized && mode === "dpb_s"
          ? { B: controls.parameters.dpb_s?.B ?? 1 }
          : {}),
      },
    },
    guessedParameters: withoutLegacyDpb(content.guessedParameters ?? {}),
    customBounds: {
      ...withoutLegacyDpb(content.customBounds),
      ...legacyControls(controls.customBounds, retained),
    },
    held: {
      ...withoutLegacyDpb(content.held),
      ...Object.fromEntries(
        Object.entries(content.held)
          .filter(
            ([mode, held]) =>
              mode.startsWith("dpb_") &&
              held.some((name) => retained.includes(name)),
          )
          .map(([mode, held]) => [
            mode,
            held.filter((name) => retained.includes(name)),
          ]),
      ),
    },
    fit: null,
    fitStart: { values: null, net: null, numerical: false },
  };
}

function legacyControls<T>(
  modes: Record<string, Record<string, T>>,
  names: readonly string[],
): Record<string, Record<string, T>> {
  return Object.fromEntries(
    Object.entries(modes).flatMap(([mode, values]) => {
      const kept = Object.fromEntries(
        Object.entries(values).filter(([name]) => names.includes(name)),
      );
      return mode.startsWith("dpb_") && Object.keys(kept).length > 0
        ? [[mode, kept]]
        : [];
    }),
  );
}

export function withoutLegacyDpb<T>(
  modes: Record<string, T>,
): Record<string, T> {
  return Object.fromEntries(
    Object.entries(modes).filter(([mode]) => !mode.startsWith("dpb_")),
  );
}

/** Preserve the actual fit request, including interpolated points, independently of the raw files. */
export function historicalSource(
  session: SessionFile,
  migration?: {
    hallMassConvention: HallMassConvention;
    sourceValleyCount: number;
    singleValleyMass: number | undefined;
    band1Degeneracy: number;
    band2Degeneracy: number;
  },
): string {
  const { data, singleFile, otherSource, ...settings } = session.content;
  void singleFile;
  void otherSource;
  return JSON.stringify({
    format: session.format,
    version: session.version,
    saved: session.saved,
    appVersion: session.appVersion,
    apiVersion: session.apiVersion,
    migration,
    content: {
      ...settings,
      units: Object.fromEntries(
        Object.entries(data).map(([quantity, entry]) => [
          quantity,
          {
            loadedAs: entry.measurement.loaded_as,
            mapping: entry.mapping,
            readAs: entry.readAs,
          },
        ]),
      ),
    },
  });
}
