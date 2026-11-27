import type { FitModeDescription, ModelDescription } from "@/model/selection";
// @vitest-environment node
import { expect, test } from "vitest";
import { convertedSession, legacyVector } from "./legacyDpb";
import { sessionFile, readSessionFile, restoredSession } from "./sessionFile";
import { createSessionStore } from "./store";
import { MODELS } from "../../e2e/support/models";

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
      carrierType: "p",
      netElectronDensityPerM3: 9e23,
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
  if (!file.content.fit.request)
    throw new Error("Expected a recorded fit request");
  const sparseTransport = {
    ...file.content,
    parameters: { dpb_s_rho_rh: { A: 1000, B: 2, C: 3 } },
    guessedParameters: { dpb_s_rho_rh: { D: 4 } },
    fit: {
      ...file.content.fit,
      request: { ...file.content.fit.request, start: { A: 2000, B: 5 } },
      result: { ...file.content.fit.result, parameters: { A: 3000 } },
    },
  };
  expect(legacyVector(sparseTransport)).toMatchObject({
    A: 3000,
    B: 5,
    C: 3,
    D: 4,
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
    80,
    "single_valley",
  );
  expect(converted.selection.algorithm).toBe("verified-sequential-v2");
  expect(converted.parameters.spb_s).toEqual({ band_mass: 3 });
  expect(converted.customBounds).toEqual({
    dpb_s_rho: { B: { lower: 0.9, upper: 1.1 } },
    dpb_s_rho_rh: { B: { lower: 0.9, upper: 1.1 } },
  });
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
  expect(converted.selection.parameterization).toBe("explicit_fermi_v1");
  expect(converted.selection.netElectronDensityPerM3).toBeUndefined();
  expect(converted.selection.carrierType).toBeUndefined();
  expect(converted.parameters.dpb_s_rho_rh).toEqual({
    mass_ratio: 2,
    band_offset_k: 600,
    m1: 1.7,
    fermi_energy: 80,
  });
});

test("ionized conversion preserves rho B holds and historical bounds", async () => {
  const store = createSessionStore();
  store.setState({
    selection: {
      ...store.getState().selection,
      model: "dpb",
      scattering: "ionized",
      fitMode: "dpb_s_rho",
    },
    parameters: { dpb_s_rho: { B: 1.04 } },
    customBounds: { dpb_s_rho: { B: { lower: 0.95, upper: 1.08 } } },
    held: { dpb_s_rho: ["B"] },
  });
  const file = await sessionFile(
    store.getState(),
    { appVersion: "old", apiVersion: "old", saved: "2026-11-20" },
    () => null,
  );
  const point = {
    parameterization: "explicit_density_v1" as const,
    band_configuration: "vb_cb" as const,
    net_electron_density_per_m3: 1e24,
    parameters: { mass_ratio: 2, band_offset_k: 600, m1: 1, B: 1.04 },
  };
  const converted = convertedSession(file, point, 1, 1, -175);
  expect(converted.parameters.dpb_s_rho?.B).toBe(1.04);
  expect(converted.customBounds.dpb_s_rho?.B).toEqual({
    lower: 0.95,
    upper: 1.08,
  });
  expect(converted.held.dpb_s_rho).toEqual(["B"]);
  expect(converted.ionizedBInputs).toBe(true);
  file.content.customBounds = {};
  file.content.held = {};
  expect(
    convertedSession(file, point, 1, 1, -175).customBounds.dpb_s_rho?.B,
  ).toEqual({ lower: 0.9, upper: 1.1 });
  expect(
    convertedSession(file, point, 1, 1, -175).held.dpb_s_rho,
  ).toBeUndefined();
});

test.each(["ionized", "acPh"])(
  "historical %s conversion preserves B controls when switching fit modes",
  async (scattering) => {
    const store = createSessionStore();
    store.setState({
      selection: {
        ...store.getState().selection,
        model: "dpb",
        scattering,
        fitMode: "dpb_s_rho",
      },
      parameters: {
        dpb_s: { B: 20, band_gap: 300 },
        dpb_s_rho: { B: 1.04, band_gap: 400 },
        dpb_s_rho_rh: { B: 0.98, band_gap: 500 },
      },
      customBounds: {
        dpb_s: { B: { lower: 0.8, upper: 1.2 } },
        dpb_s_rho: { B: { lower: 0.95, upper: 1.08 } },
        dpb_s_rho_rh: { B: { lower: 0.92, upper: 1.06 } },
      },
      held: {
        dpb_s: ["B", "band_gap"],
        dpb_s_rho: ["band_gap"],
        dpb_s_rho_rh: ["B", "band_gap"],
      },
    });
    const file = await sessionFile(
      store.getState(),
      { appVersion: "old", apiVersion: "old", saved: "2026-11-20" },
      () => null,
    );
    file.version = 1;
    delete file.content.ionizedBInputs;
    const converted = convertedSession(
      file,
      {
        parameterization: "explicit_density_v1",
        band_configuration: "vb_cb",
        net_electron_density_per_m3: 1e24,
        parameters: { mass_ratio: 2, band_offset_k: 600, m1: 1, B: 1.02 },
      },
      1,
      1,
      -175,
    );
    store.getState().restoreSession(restoredSession(converted), {
      saved: file.saved,
      appVersion: file.appVersion,
      fitCoreVersion: null,
      serverCoreVersion: null,
    });
    const descriptions = (MODELS.models as ModelDescription[]).flatMap(
      (model) => model.fit_modes,
    );
    const description = (id: string | null) => {
      const found = descriptions.find((mode) => mode.id === id);
      if (!found) throw new Error(String(id));
      return found;
    };
    for (const [mode, b] of [
      ["dpb_s_rho_rh", 0.98],
      ["dpb_s_rho", 1.02],
      ["dpb_s", 1],
      ["dpb_s_rho_rh", 0.98],
      ["dpb_s_rho", 1.02],
    ] as const) {
      store
        .getState()
        .chooseFitMode(
          { fitMode: mode },
          description(store.getState().selection.fitMode),
          description(mode),
        );
      const state = store.getState();
      expect(state.parameters[mode]?.B).toBe(b);
      expect(state.customBounds[mode]).toEqual(file.content.customBounds[mode]);
      expect(state.held[mode] ?? []).toEqual(mode === "dpb_s_rho" ? [] : ["B"]);
      expect(state.parameters[mode]?.band_gap).toBeUndefined();
    }
    expect(converted.parameters.dpb_s_rho).toEqual({
      mass_ratio: 2,
      band_offset_k: 600,
      m1: 1,
      B: 1.02,
      fermi_energy: -175,
    });
    store.getState().setSelection({ legacySource: "" });
    store
      .getState()
      .chooseFitMode(
        { fitMode: "dpb_s_rho_rh" },
        description("dpb_s_rho"),
        description("dpb_s_rho_rh"),
      );
    expect(store.getState().parameters.dpb_s_rho_rh?.B).toBe(1.02);
    expect(store.getState().customBounds.dpb_s_rho_rh?.B).toEqual({
      lower: 0.95,
      upper: 1.08,
    });
    expect(store.getState().held.dpb_s_rho_rh).toEqual([]);
  },
);

test.each(["acPh", "dis", "ionized", "acPhDis"])(
  "conversion with %s retains archived transport drafts, bounds and held settings across DPB modes",
  async (scattering) => {
    const store = createSessionStore();
    store.setState({
      selection: {
        ...store.getState().selection,
        model: "dpb",
        scattering,
        fitMode: "dpb_s",
      },
      parameters: {
        dpb_s: { B: 7 },
        dpb_s_rho: { A: 1000, B: 2, C: 3, D: 4 },
        dpb_s_rho_rh: { A: 2000, B: 5, C: 6, D: 7 },
      },
      customBounds: {
        dpb_s_rho: {
          A: { lower: 900, upper: 1200 },
          B: { lower: 1, upper: 3 },
          C: { lower: 2, upper: 4 },
          D: { lower: 3, upper: 5 },
        },
      },
      held: { dpb_s_rho: ["A", "C", "D", "fermi_energy"] },
    });
    const file = await sessionFile(
      store.getState(),
      { appVersion: "old", apiVersion: "old", saved: "2026-11-20" },
      () => null,
    );
    const converted = convertedSession(
      file,
      {
        parameterization: "explicit_density_v1",
        band_configuration: "vb_cb",
        net_electron_density_per_m3: 1e24,
        parameters: { mass_ratio: 2, band_offset_k: 600, m1: 1, B: 7 },
      },
      1,
      1,
      -175,
    );
    expect(converted.selection.scattering).toBe(scattering);
    expect(converted.parameters.dpb_s?.B).toBe(
      scattering === "acPhDis" ? 7 : 1,
    );
    expect(converted.parameters.dpb_s_rho).toEqual({
      A: 1000,
      B: 2,
      C: 3,
      D: 4,
    });
    expect(converted.parameters.dpb_s_rho_rh).toEqual({
      A: 2000,
      B: 5,
      C: 6,
      D: 7,
    });
    expect(converted.customBounds.dpb_s_rho).toEqual(
      file.content.customBounds.dpb_s_rho,
    );

    expect(converted.held.dpb_s_rho).toEqual(["A", "C", "D"]);
  },
);
