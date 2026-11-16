// @vitest-environment node
import { expect, test } from "vitest";

import {
  dataHash,
  readSessionFile,
  sessionFile,
  SESSION_VERSION,
  type SessionFile,
} from "@/session/sessionFile";
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

const REQUEST = {
  model: "dpb",
  fit_mode: "dpb_s",
  start: { m_eff: 1 },
  min_temperature_k: 50,
  max_temperature_k: 800,
  measurements: {},
} as never;

/** A session with data, settings, a held parameter, custom bounds and a finished fit. */
function session(): SessionState {
  const store = createSessionStore();
  store.setState({
    data: { seebeck: SEEBECK },
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

async function saved(): Promise<string> {
  const file = await sessionFile(session(), VERSIONS, () => REQUEST);
  return JSON.stringify(file);
}

test("a saved session loads back into a new one as it was, its fit not run again", async () => {
  const read = await readSessionFile(await saved());
  if (!("session" in read)) {
    throw new Error(read.problem);
  }
  const { session: file } = read;
  const store = createSessionStore();
  store.getState().restoreSession(
    {
      dataMode: file.dataMode,
      data: file.data,
      singleFile: file.singleFile,
      selection: file.selection,
      parameters: file.parameters,
      customBounds: file.customBounds,
      held: file.held,
      interpolationEnabled: file.interpolation.enabled,
      fitStart: file.fitStart,
      result: file.fit?.result ?? null,
    },
    {
      saved: file.saved,
      appVersion: file.appVersion,
      fitCoreVersion: "0.3.0",
      serverCoreVersion: "0.4.0",
    },
  );
  const before = session();
  const after = store.getState();

  for (const key of [
    "data",
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
  expect(after.restored?.fitCoreVersion).toBe("0.3.0");
  expect(file.fit?.request).toEqual(REQUEST);
  expect(file.version).toBe(SESSION_VERSION);
});

test("a new fit replaces what the file said of its fit", async () => {
  const store = createSessionStore();
  store.getState().restoreSession(
    {
      dataMode: "separate",
      data: {},
      singleFile: null,
      selection: store.getState().selection,
      parameters: {},
      customBounds: {},
      held: {},
      interpolationEnabled: false,
      fitStart: { values: null, net: null, numerical: false },
      result: RESULT,
    },
    {
      saved: "x",
      appVersion: "1",
      fitCoreVersion: "0.3.0",
      serverCoreVersion: null,
    },
  );
  store.getState().fitRequested("dpb_s", { m_eff: 1 });
  expect(store.getState().restored).toBeNull();
});

test("the request of a finished fit is that of its start values", async () => {
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
])("a file that is %s is refused", async (problem, text) => {
  expect(await readSessionFile(text)).toEqual({ problem });
});

test("a value changed in a saved file is refused, as its hash no longer matches", async () => {
  const file = JSON.parse(await saved()) as SessionFile;
  const changed = {
    ...file,
    data: {
      seebeck: {
        ...file.data.seebeck,
        measurement: {
          ...file.data.seebeck?.measurement,
          values: [1e-4, 2e-4, 4e-4],
        },
      },
    },
  };
  expect(await readSessionFile(JSON.stringify(changed))).toEqual({
    problem: "data_changed",
  });
});

test("a file too large is refused before it is parsed", async () => {
  expect(await readSessionFile(" ".repeat(30_000_001))).toEqual({
    problem: "too_large",
  });
});

test("the hash depends on the data, not on the rest of the session", async () => {
  const hash = await dataHash({ seebeck: SEEBECK });
  expect(hash).toMatch(/^[0-9a-f]{64}$/);
  expect(await dataHash({ seebeck: { ...SEEBECK, text: "other" } })).toBe(hash);
  expect(
    await dataHash({
      seebeck: {
        ...SEEBECK,
        measurement: { ...SEEBECK.measurement, values: [1e-4, 2e-4, 3.1e-4] },
      },
    }),
  ).not.toBe(hash);
});
