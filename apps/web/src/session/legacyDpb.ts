import type { components } from "@seeband/api-client";
import { parameterValues } from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import type { SessionContent, SessionFile } from "@/session/sessionFile";

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
): SessionContent {
  const content = session.content;
  const mode = content.selection.fitMode ?? "dpb_s_rho";
  return {
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
      legacySource: historicalSource(session),
    },
    parameters: {
      ...withoutLegacyDpb(content.parameters),
      [mode]: point.parameters,
    },
    guessedParameters: withoutLegacyDpb(content.guessedParameters ?? {}),
    customBounds: withoutLegacyDpb(content.customBounds),
    held: withoutLegacyDpb(content.held),
    fit: null,
    fitStart: { values: null, net: null, numerical: false },
  };
}

export function withoutLegacyDpb<T>(
  modes: Record<string, T>,
): Record<string, T> {
  return Object.fromEntries(
    Object.entries(modes).filter(([mode]) => !mode.startsWith("dpb_")),
  );
}

/** Original scale, fit and unit provenance; measurement arrays and file text remain in the session once. */
export function historicalSource(session: SessionFile): string {
  const { data, singleFile, otherSource, ...settings } = session.content;
  void singleFile;
  void otherSource;
  const historicalFit = contentFitWithoutMeasurements(session.content);
  return JSON.stringify({
    format: session.format,
    version: session.version,
    saved: session.saved,
    appVersion: session.appVersion,
    apiVersion: session.apiVersion,
    content: {
      ...settings,
      fit: historicalFit,
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

function contentFitWithoutMeasurements(content: SessionContent) {
  const fit = content.fit;
  return fit === null
    ? null
    : {
        ...fit,
        request:
          fit.request === null
            ? null
            : { ...fit.request, measurements: undefined },
      };
}
