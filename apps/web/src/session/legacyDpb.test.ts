import type { FitModeDescription } from "@/model/selection";
// @vitest-environment node
import { expect, test } from "vitest";
import { convertedSession, legacyVector } from "./legacyDpb";
import { sessionFile, readSessionFile, restoredSession } from "./sessionFile";
import { createSessionStore } from "./store";

test("conversion keeps historical bounds and results as provenance, with fresh explicit fit controls", async () => {
  const store = createSessionStore();
  store.setState({
    selection: {
      ...store.getState().selection,
      model: "dpb",
      algorithm: "legacy-sequential-v1",
      fitMode: "dpb_s_rho_rh",
      band1Degeneracy: 2,
      band2Degeneracy: 6,
    },
    parameters: {
      spb_s: { band_mass: 3 },
      dpb_s_rho_rh: { m_eff: 3, band_gap: 300, fermi_energy: 50, m1: 9 },
    },
    customBounds: { dpb_s_rho_rh: { fermi_energy: { lower: 0, upper: 100 } } },
    held: { dpb_s_rho_rh: ["fermi_energy"] },
  });
  const file = await sessionFile(
    store.getState(),
    { appVersion: "old", apiVersion: "old", saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  file.content.interpolation.enabled = true;
  file.content.fit = {
    request: {
      model: "dpb",
      fit_mode: "dpb_s_rho_rh",
      scattering: "acPh",
      start: { m1: 9, m_eff: 3, band_gap: 300, fermi_energy: 50 },
      min_temperature_k: 150,
      max_temperature_k: 300,
      measurements: {
        resistivity: {
          temperature_k: [150, 225, 300],
          values: [0.001, 0.002, 0.003],
        },
        hall: { temperature_k: [150, 225, 300], values: [1e-8, 2e-8, 3e-8] },
        seebeck: {
          temperature_k: [150, 225, 300],
          values: [0.0001, 0.00015, 0.0002],
        },
      },
    },
    result: {
      status: "converged",
      parameters: { m_eff: 2, band_gap: 600, fermi_energy: 80, m1: 1.7 },
      at_bounds: [],
      known_issues: [],
      parameter_errors: {},
      held: [],
      parameter_status: {},
    },
  };
  expect(legacyVector(file.content)).toEqual({
    m_eff: 2,
    band_gap: 600,
    fermi_energy: 80,
    m1: 1.7,
  });
  const sparse = {
    ...file.content,
    fit: null,
    parameters: { dpb_s_rho_rh: { band_gap: 900 } },
    guessedParameters: { dpb_s_rho_rh: { m_eff: 3 } },
  };
  const description = {
    parameters: [
      { name: "m_eff", core_range: { default: 1 } },
      { name: "band_gap", core_range: { default: 600 } },
      { name: "fermi_energy", core_range: { default: 80 } },
    ],
  } as FitModeDescription;
  expect(legacyVector(sparse, description)).toEqual({
    m_eff: 3,
    band_gap: 900,
    fermi_energy: 80,
  });
  const converted = convertedSession(
    file,
    {
      parameterization: "explicit_density_v1",
      band_configuration: "vb_cb",
      net_electron_density_per_m3: -2e24,
      parameters: { mass_ratio: 2, band_offset_k: 600, m1: 1.7 },
    },
    2,
    6,
    "single_valley",
  );
  expect(converted.selection.algorithm).toBe("verified-sequential-v2");
  expect(converted.parameters.spb_s).toEqual({ band_mass: 3 });
  expect(converted.customBounds).toEqual({});
  expect(converted.held).toEqual({});
  expect(converted.fit).toBeNull();
  expect(
    JSON.parse(converted.selection.legacySource ?? "null").content.fit,
  ).toEqual(file.content.fit);
  store.getState().restoreSession(restoredSession(converted), {
    saved: file.saved,
    appVersion: file.appVersion,
    fitCoreVersion: null,
    serverCoreVersion: null,
  });
  const reopened = await readSessionFile(
    JSON.stringify(await sessionFile(store.getState(), file, () => null)),
  );
  if ("problem" in reopened) throw new Error(reopened.problem);
  const archived = JSON.parse(
    reopened.session.content.selection.legacySource ?? "null",
  );
  expect(archived.content.fit.request).toEqual(file.content.fit.request);
  expect(archived.migration).toEqual({
    hallMassConvention: "single_valley",
    sourceValleyCount: 2,
    singleValleyMass: 1.7,
    band1Degeneracy: 2,
    band2Degeneracy: 6,
  });
  expect(converted.selection.netElectronDensityPerM3).toBe(-2e24);
  expect(converted.parameters.dpb_s_rho_rh).toEqual({
    mass_ratio: 2,
    band_offset_k: 600,
    m1: 1.7,
  });
});
