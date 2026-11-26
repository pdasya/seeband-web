// @vitest-environment node
import { expect, test } from "vitest";

import type { FitRequest } from "@/api/client";
import {
  checksum,
  readSessionFile,
  restoredSession,
  sessionFile,
  SESSION_VERSION,
  type SessionFile,
} from "@/session/sessionFile";
import { sha256, sha256Hex } from "@/session/sha256";
import {
  createSessionStore,
  type FitResult,
  type SessionData,
  type SessionState,
} from "@/session/store";

const SEEBECK: SessionData = {
  measurement: {
    temperature_k: [100, 200, 300],
    values: [1e-4, 2e-4, 3e-4],
    points: 3,
    min_temperature_k: 100,
    max_temperature_k: 300,
    loaded_as: "seebeck",
  },
  source: { kind: "file", name: "s.txt" },
  extrapolated: false,
  text: "T S\n100 100\n200 200\n300 300\n",
  mapping: [
    { column: 0, role: "temperature", unit: "K" },
    { column: 1, role: "seebeck", unit: "uV/K" },
  ],
  readAs: [
    { column: 0, role: "temperature", unit: "K", unit_source: "default" },
    { column: 1, role: "seebeck", unit: "uV/K", unit_source: "chosen" },
  ],
  unitDoubts: [{ code: "implausible_magnitude", direction: "above" }],
  unitConfirmed: true,
};

const RESULT: FitResult = {
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 },
  status: "converged",
  core_version: "0.3.0",
  algorithm: "legacy-sequential-v1",
  parameter_errors: {},
  parameter_status: { m_eff: "estimated" },
  at_bounds: [],
  known_issues: [],
  held: [],
};

const REQUEST: FitRequest = {
  model: "dpb",
  fit_mode: "dpb_s",
  start: { m_eff: 1 },
  min_temperature_k: 50,
  max_temperature_k: 800,
  measurements: { seebeck: { temperature_k: [100], values: [1e-4] } },
};

/** A session with data, settings, a held parameter, custom bounds and a finished fit. */
function session(): SessionState {
  const store = createSessionStore();
  store.setState({
    data: { seebeck: SEEBECK },
    otherSource: { data: { seebeck: SEEBECK }, singleFile: null },
    chartPanels: ["seebeck", "chemical_potential", "resistivity", "hall"],
    savedModelSettings: {
      spb: {
        fitMode: "spb_s",
        scattering: "acPh",
        band1Degeneracy: 1,
        band2Degeneracy: 1,
      },
    },
    selection: {
      ...store.getState().selection,
      algorithm: "legacy-sequential-v1",
      model: "dpb",
      fitMode: "dpb_s",
      scattering: null,
      band2Degeneracy: 3,
      minTemperatureK: 50,
      maxTemperatureK: 800,
    },
    parameters: { dpb_s: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 } },
    customBounds: { dpb_s: { band_gap: { lower: 500, upper: 1500 } } },
    held: { dpb_s: ["fermi_energy"] },
    interpolation: { ...store.getState().interpolation, enabled: true },
    fit: { status: "done", result: RESULT },
    fitStartValues: { m_eff: 1, band_gap: 1000, fermi_energy: -50 },
    fitStartNet: { min_temperature_k: 300, max_temperature_k: 800 },
  });
  return store.getState();
}

const VERSIONS = {
  appVersion: "1.0.0 (commit abc)",
  apiVersion: "1.0.0 (commit def)",
  saved: "2026-11-16T12:00:00.000Z",
};

async function saved(state = session()): Promise<string> {
  return JSON.stringify(await sessionFile(state, VERSIONS, () => REQUEST));
}

async function opened(text: string): Promise<SessionFile> {
  const read = await readSessionFile(text);
  if (!("session" in read)) {
    throw new Error(read.problem);
  }
  return read.session;
}

function restoredInto(file: SessionFile) {
  const store = createSessionStore();
  store.getState().restoreSession(restoredSession(file.content), {
    saved: file.saved,
    appVersion: file.appVersion,
    fitCoreVersion: "0.3.0",
    serverCoreVersion: "0.4.0",
  });
  return store;
}

test("a saved session loads back into a new one as it was, its fit not run again", async () => {
  const after = restoredInto(await opened(await saved())).getState();
  const before = session();

  for (const key of [
    "data",
    "otherSource",
    "chartPanels",
    "savedModelSettings",
    "selection",
    "parameters",
    "customBounds",
    "held",
    "fit",
    "fitStartValues",
    "fitStartNet",
    "fitStartNumerical",
  ] as const) {
    expect(after[key], key).toEqual(before[key]);
  }
  expect(after.interpolation.enabled).toBe(true);
  expect(after.restored?.request).toEqual(REQUEST);
});

test("saved guess origins survive restoration while legacy starts remain manual", async () => {
  const before = session();
  before.guessedParameters = { dpb_s: { band_gap: 900 } };
  const file = await sessionFile(before, VERSIONS, () => REQUEST);
  const after = restoredInto(await opened(JSON.stringify(file))).getState();
  expect(after.guessedParameters).toEqual({ dpb_s: { band_gap: 900 } });

  delete file.content.guessedParameters;
  file.checksum = await checksum(file.content);
  const legacy = restoredInto(await opened(JSON.stringify(file))).getState();
  expect(legacy.parameters).toEqual(before.parameters);
  expect(legacy.guessedParameters).toEqual({});
});

test("saving a restored session again keeps the request of its fit as it was", async () => {
  const store = restoredInto(await opened(await saved()));
  // Today the request could not be built, as interpolation is on its way after a restore.
  const again = await sessionFile(store.getState(), VERSIONS, () => null);
  expect(again.content.fit?.request).toEqual(REQUEST);
});

test("the request of a new fit is that of its start values", async () => {
  const seen: SessionState[] = [];
  await sessionFile(session(), VERSIONS, (state) => {
    seen.push(state);
    return REQUEST;
  });
  expect(seen[0]?.parameters.dpb_s).toEqual({
    m_eff: 1,
    band_gap: 1000,
    fermi_energy: -50,
  });
});

test("a restored fit that no longer matches its inputs goes, and says so", async () => {
  const store = restoredInto(await opened(await saved()));
  store.getState().restoredFitStale();
  expect(store.getState().fit.status).toBe("idle");
  expect(store.getState().restored?.stale).toBe(true);
});

test("a new fit replaces what the file said of its fit", async () => {
  const store = restoredInto(await opened(await saved()));
  store.getState().fitRequested("dpb_s", { m_eff: 1 });
  expect(store.getState().restored).toBeNull();
});

test.each([
  ["not_json", "{"],
  ["not_a_session", JSON.stringify({ format: "other" })],
  [
    "newer_version",
    JSON.stringify({ format: "seeband-session", version: SESSION_VERSION + 1 }),
  ],
  [
    "invalid",
    JSON.stringify({ format: "seeband-session", version: SESSION_VERSION }),
  ],
  // An older version with no migration to it is not one this app wrote.
  ["invalid", JSON.stringify({ format: "seeband-session", version: 0 })],
])("a file that is %s is refused", async (problem, text) => {
  expect(await readSessionFile(text)).toEqual({ problem });
});

/** A saved file with one change made to its content, its checksum worked out again. */
async function edited(
  change: (content: Record<string, unknown>) => void,
): Promise<string> {
  const file = JSON.parse(await saved()) as {
    content: Record<string, unknown>;
    checksum: string;
  };
  change(file.content);
  file.checksum = await checksum(file.content as never);
  return JSON.stringify(file);
}

test.each([
  [
    "a fit result with no known issues",
    (content: Record<string, unknown>) => {
      delete (content.fit as { result: Record<string, unknown> }).result
        .known_issues;
    },
  ],
  [
    "a fit range as text",
    (content: Record<string, unknown>) => {
      (content.selection as Record<string, unknown>).minTemperatureK = "10";
    },
  ],
  [
    "a bound that is not a number",
    (content: Record<string, unknown>) => {
      content.customBounds = { dpb_s: { band_gap: { lower: "a", upper: 1 } } };
    },
  ],
  [
    "a quantity the app has not",
    (content: Record<string, unknown>) => {
      content.data = { thermopower: SEEBECK };
    },
  ],
])("a file with %s is refused, though its checksum fits", async (_, change) => {
  expect(await readSessionFile(await edited(change))).toEqual({
    problem: "invalid",
  });
});

test("a number too large for a double is refused, not read as Infinity", async () => {
  const text = (await saved()).replace('"band_gap":900', '"band_gap":1e999');
  expect(text).toContain("1e999");
  expect(await readSessionFile(text)).toEqual({ problem: "invalid" });
});

test("a change to the content shows, the units' confirmation included", async () => {
  const file = JSON.parse(await saved()) as {
    content: { data: { seebeck: { unitConfirmed: boolean } } };
  };
  file.content.data.seebeck.unitConfirmed = false;
  expect(await readSessionFile(JSON.stringify(file))).toEqual({
    problem: "checksum",
  });
});

test("a file too large is refused before it is parsed", async () => {
  expect(await readSessionFile(" ".repeat(50_000_001))).toEqual({
    problem: "too_large",
  });
});

test("the plain SHA-256 gives the browser's digest, at each length its padding turns on", async () => {
  for (const length of [0, 3, 55, 56, 63, 64, 65, 1000]) {
    const bytes = new Uint8Array(length).map((_, i) => (i * 7 + 3) % 256);
    const browser = new Uint8Array(
      await crypto.subtle.digest("SHA-256", bytes),
    );
    expect([...sha256(bytes)], String(length)).toEqual([...browser]);
  }
  expect(await sha256Hex(new TextEncoder().encode("abc"))).toBe(
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
});

test("explicit density session preserves representation and historical provenance", async () => {
  const state = session();
  state.selection = {
    ...state.selection,
    parameterization: "explicit_density_v1",
    bandConfiguration: "cb_cb",
    netElectronDensityPerM3: 2e24,
    fitAbsoluteMass: true,
    legacySource: '{"version":1,"original":"kept"}',
  };
  const file = await sessionFile(
    state,
    { appVersion: "test", apiVersion: "test", saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  const read = await readSessionFile(JSON.stringify(file));
  expect("session" in read).toBe(true);
  if ("session" in read)
    expect(restoredSession(read.session.content).selection).toEqual(
      state.selection,
    );
});

test("version 2 requires a coherent explicit representation and rejects v1 explicit payloads", async () => {
  const state = session();
  state.selection = {
    ...state.selection,
    parameterization: "explicit_density_v1",
    bandConfiguration: "vb_cb",
    netElectronDensityPerM3: 0,
  };
  const file = await sessionFile(
    state,
    { appVersion: "test", apiVersion: null, saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  expect(file.version).toBe(4);
  expect(
    await readSessionFile(JSON.stringify({ ...file, version: 1 })),
  ).toEqual({ problem: "invalid" });
  delete file.content.selection.bandConfiguration;
  file.checksum = await checksum(file.content);
  expect(await readSessionFile(JSON.stringify(file))).toEqual({
    problem: "invalid",
  });
});

test("explicit DPB identity survives saving while SPB is selected", async () => {
  const state = session();
  state.selection = {
    ...state.selection,
    model: "spb",
    fitMode: "spb_s",
    parameterization: "explicit_density_v1",
    bandConfiguration: "cb_cb",
    netElectronDensityPerM3: 3e24,
  };
  state.parameters.dpb_s_rho = { mass_ratio: 2, band_offset_k: 600, m1: 1.7 };
  const file = await sessionFile(
    state,
    { appVersion: "test", apiVersion: null, saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  expect(file.version).toBe(4);
  const read = await readSessionFile(JSON.stringify(file));
  if (!("session" in read))
    throw new Error("Explicit inactive DPB session was rejected");
  expect(read.session.content.parameters.dpb_s_rho).toEqual({
    mass_ratio: 2,
    band_offset_k: 600,
    m1: 1.7,
  });
  expect(read.session.content.selection.bandConfiguration).toBe("cb_cb");
});

test.each([undefined, "p" as const])(
  "Fermi session round-trip retains E_F, bounds, holds and optional legacy sign %s",
  async (carrierType) => {
    const state = session();
    state.selection = {
      ...state.selection,
      parameterization: "explicit_fermi_v1",
      bandConfiguration: "vb_cb",
      ...(carrierType === undefined ? {} : { carrierType }),
    };
    state.parameters.dpb_s_rho = { fermi_energy: -140 };
    state.customBounds.dpb_s_rho = {
      fermi_energy: { lower: -500, upper: 200 },
    };
    state.held.dpb_s_rho = ["fermi_energy"];
    const file = await sessionFile(
      state,
      { appVersion: "test", apiVersion: null, saved: "2026-11-20T00:00:00Z" },
      () => null,
    );
    expect(file.version).toBe(4);
    const read = await readSessionFile(JSON.stringify(file));
    if (!("session" in read)) throw new Error("Fermi session rejected");
    const restored = restoredSession(read.session.content);
    expect(restored.selection).toEqual(state.selection);
    expect(restored.parameters.dpb_s_rho).toEqual({ fermi_energy: -140 });
    expect(restored.customBounds.dpb_s_rho).toEqual(
      state.customBounds.dpb_s_rho,
    );
    expect(restored.held.dpb_s_rho).toEqual(["fermi_energy"]);
    expect(restored.selection).not.toHaveProperty("netElectronDensityPerM3");
    if (carrierType === undefined)
      expect(restored.selection).not.toHaveProperty("carrierType");
    else expect(restored.selection.carrierType).toBe(carrierType);
  },
);

test("historical ionized controls preserve rho bounds and holds and ignore dormant S-only B", async () => {
  const state = session();
  state.selection = {
    ...state.selection,
    model: "dpb",
    scattering: "ionized",
    fitMode: "dpb_s_rho",
  };
  state.parameters = { dpb_s: { B: 7 }, dpb_s_rho: { B: 1.05 } };
  state.held = { dpb_s_rho: ["B"] };
  state.customBounds = {};
  const file = await sessionFile(
    state,
    { appVersion: "old", apiVersion: "old", saved: "2026-11-20" },
    () => null,
  );
  const oldContent = JSON.stringify(file.content);
  const loaded = await readSessionFile(JSON.stringify(file));
  expect("session" in loaded).toBe(true);
  const restored = restoredSession(file.content);
  expect(restored.parameters.dpb_s?.B).toBe(1);
  expect(restored.parameters.dpb_s_rho?.B).toBe(1.05);
  expect(restored.customBounds.dpb_s_rho?.B).toEqual({
    lower: 0.9,
    upper: 1.1,
  });
  expect(restored.held.dpb_s_rho).toEqual(["B"]);
  expect(JSON.stringify(file.content)).toBe(oldContent);
  file.content.customBounds = {
    dpb_s_rho: { B: { lower: 0.95, upper: 1.07 } },
  };
  expect(restoredSession(file.content).customBounds.dpb_s_rho?.B).toEqual({
    lower: 0.95,
    upper: 1.07,
  });
});

test("new explicit sessions retain user S-only B and wide rho defaults on reopen", async () => {
  const state = session();
  state.selection = {
    ...state.selection,
    model: "dpb",
    parameterization: "explicit_density_v1",
    bandConfiguration: "vb_cb",
    netElectronDensityPerM3: 1e24,
    scattering: "ionized",
    fitMode: "dpb_s",
  };
  state.parameters = { dpb_s: { B: 9 } };
  state.customBounds = {};
  const file = await sessionFile(
    state,
    { appVersion: "new", apiVersion: "new", saved: "2026-11-20" },
    () => null,
  );
  expect(file.version).toBe(4);
  const loaded = await readSessionFile(JSON.stringify(file));
  if (!("session" in loaded)) throw new Error(loaded.problem);
  const restored = restoredSession(loaded.session.content);
  expect(restored.parameters.dpb_s?.B).toBe(9);
  expect(restored.customBounds).toEqual({});
  expect(
    await readSessionFile(JSON.stringify({ ...file, version: 3 })),
  ).toEqual({ problem: "invalid" });
});

test.each([
  ["spb", "ionized"],
  ["spb", "dis"],
  ["dpb", "acPh"],
  ["dpb", "acPhDis"],
] as const)(
  "v2 restores DPB bounds with %s selected and %s scattering",
  async (model, scattering) => {
    const state = session();
    state.selection = {
      ...state.selection,
      model,
      scattering,
      fitMode: model === "dpb" ? "dpb_s_rho" : "spb_s",
      parameterization: "explicit_density_v1",
      bandConfiguration: "vb_cb",
      netElectronDensityPerM3: 1e24,
    };
    state.savedModelSettings = {
      dpb: {
        fitMode: "dpb_s_rho",
        scattering,
        band1Degeneracy: 1,
        band2Degeneracy: 1,
      },
    };
    state.parameters = { dpb_s: { B: 7 }, dpb_s_rho: { B: 1.03 } };
    state.customBounds = { dpb_s_rho_rh: { B: { lower: 0.97, upper: 1.03 } } };
    const file = await sessionFile(
      state,
      { appVersion: "old", apiVersion: "old", saved: "2026-11-20" },
      () => null,
    );
    file.version = 2;
    delete file.content.ionizedBInputs;
    file.content.fit = {
      result: RESULT,
      request: {
        ...REQUEST,
        fit_mode: "dpb_s",
        bounds: { B: { lower: 3, upper: 4 } },
      },
    };
    file.checksum = await checksum(file.content);
    const loaded = await readSessionFile(JSON.stringify(file));
    if (!("session" in loaded)) throw new Error(loaded.problem);
    const restored = restoredSession(loaded.session.content);
    expect(restored.parameters.dpb_s?.B).toBe(1);
    expect(restored.parameters.dpb_s_rho?.B).toBe(1.03);
    expect(restored.customBounds.dpb_s_rho?.B).toEqual({
      lower: 0.9,
      upper: 1.1,
    });
    expect(restored.customBounds.dpb_s_rho_rh?.B).toEqual({
      lower: 0.97,
      upper: 1.03,
    });
    expect(restored.request).toEqual(file.content.fit.request);
    const inconsistent = { ...file, version: 4 };
    expect(await readSessionFile(JSON.stringify(inconsistent))).toEqual({
      problem: "invalid",
    });
  },
);
