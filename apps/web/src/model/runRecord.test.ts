// @vitest-environment node
import { expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import { exportHeader } from "@/model/exportFiles";
import { runLines, unitSummary } from "@/model/runRecord";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import {
  createSessionStore,
  type FitResult,
  type SessionData,
  type SessionState,
} from "@/session/store";

const modes = (MODELS.models as ModelDescription[]).flatMap(
  ({ fit_modes: fitModes }) => fitModes,
);
const MODE = modes.find(({ id }) => id === "dpb_s_rho") as FitModeDescription;

const MEASUREMENT = {
  temperature_k: [100, 200],
  values: [1e-4, 2e-4],
  points: 2,
  min_temperature_k: 100,
  max_temperature_k: 200,
};

/** S from a file in µV/K, chosen, with temperature in °C from its header, and a doubt. */
const SEEBECK: SessionData = {
  measurement: { ...MEASUREMENT, loaded_as: "seebeck" },
  source: { kind: "file", name: "s.txt" },
  extrapolated: false,
  text: "",
  readAs: [
    { column: 0, role: "temperature", unit: "C", unit_source: "header" },
    { column: 1, role: "seebeck", unit: "uV/K", unit_source: "chosen" },
  ],
  unitDoubts: [{ code: "implausible_magnitude", direction: "above" }],
  unitConfirmed: true,
};
const RESISTIVITY: SessionData = {
  measurement: { ...MEASUREMENT, loaded_as: "resistivity" },
  source: { kind: "file", name: "rho.txt" },
  extrapolated: false,
  text: "",
  readAs: [
    { column: 0, role: "temperature", unit: "K", unit_source: "default" },
    { column: 1, role: "resistivity", unit: "Ohm*m", unit_source: "default" },
  ],
};

const RESULT: FitResult = {
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50, A: 4e4, B: 1 },
  status: "converged",
  iterations: 3,
  algorithm: "legacy-sequential-v1",
  parameter_errors: {},
  parameter_status: {},
  at_bounds: [],
  known_issues: [],
  held: [],
  last_changes: {
    m_eff: 0.0213,
    band_gap: 0.0006,
    fermi_energy: 0,
    A: 0.08,
    B: null,
  },
};

function session(): SessionState {
  const store = createSessionStore();
  store.setState({
    data: { seebeck: SEEBECK, resistivity: RESISTIVITY },
    selection: {
      ...store.getState().selection,
      model: "dpb",
      fitMode: "dpb_s_rho",
      scattering: "acPh",
      minTemperatureK: 150,
      maxTemperatureK: 800,
    },
    fit: { status: "done", result: RESULT },
    fitStartValues: { m_eff: 1, band_gap: 1000, fermi_energy: -100 },
    fitStartNet: { min_temperature_k: 300, max_temperature_k: 800 },
    customBounds: { dpb_s_rho: { band_gap: { lower: 500, upper: 1500 } } },
    held: { dpb_s_rho: ["B"] },
  });
  return store.getState();
}

const RMSE = {
  seebeck: { value: 1.1e-6, unit: "V/K" },
  resistivity: { value: 22, unit: "%" },
};

test("a run names its files, columns, units and where each unit came from", () => {
  const lines = runLines(session(), MODE, RMSE, true);

  expect(lines).toContain("S: 2 measured points, 1 within the fit range");
  expect(lines.find((line) => line.startsWith("Values in use: "))).toMatch(
    /^Values in use: m₂\/m₁ = /,
  );
  expect(lines).toContain(
    'Input S: file "s.txt"; T in column 1, in °C (named in the file\'s header); S in column 2, in µV/K (chosen by the user)',
  );
  expect(lines).toContain(
    'Input ρ: file "rho.txt"; T in column 1, in K (SI, as nothing named a unit); ρ in column 2, in Ω·m (SI, as nothing named a unit)',
  );
  expect(lines.find((line) => line.startsWith("Unit in doubt for S"))).toMatch(
    /^Unit in doubt for S, and the user confirmed the values: /,
  );
});

test("a run names its start and its source, its bounds, the held and the RMSE", () => {
  const lines = runLines(session(), MODE, RMSE, true);

  expect(lines.find((line) => line.startsWith("Start values"))).toMatch(
    /^Start values, from the neural net's guess from its net for 300-800 K where it gave a value, else the fit screen: m₂\/m₁ = 1, E_g = 0\.08617\d* eV/,
  );
  const bounds = lines.find((line) => line.startsWith("Bounds: ")) ?? "";
  expect(bounds).toMatch(
    /E_g 0\.043\d* eV to 0\.129\d* eV \(set by the user\)/,
  );
  expect(bounds).not.toContain("B ");
  expect(lines).toContain("Held at their values: B");
  expect(lines).toContain("RMSE S of the fitted curve: 0.0000011 V/K");
  expect(lines).toContain("RMSE ρ of the fitted curve: 22 %");
});

test("a legacy loop names its stop rule, its limit and its last changes", () => {
  const lines = runLines(session(), MODE, null, true);

  expect(lines).toContain(
    "Stop rule: each parameter of the loop changed by at most 10 % in an iteration, within 1000 iterations",
  );
  expect(lines).toContain(
    "Relative changes the stop rule compared in the last iteration: m₂/m₁ 2.13 %, E_g 0.06 %, E_F 0 %, A 8 %, B not finite",
  );
  // The legacy loop narrows m₂/m₁ to the sign of its start, which its bounds alone do not say.
  expect(
    lines.some((line) => line.startsWith("The legacy loop also keeps m2/m1")),
  ).toBe(true);
});

test("with interpolation on, a quantity it failed for is named", () => {
  const state = session();
  const lines = runLines(
    {
      ...state,
      interpolation: {
        ...state.interpolation,
        enabled: true,
        failed: ["seebeck", "hall"],
      },
    },
    MODE,
    null,
    false,
  );
  expect(lines).toContain("Interpolation on");
  // A fit cannot use data whose interpolation failed; R_H is not in this mode.
  expect(lines).toContain(
    "Interpolation failed for S, so a fit cannot use their data until it works or is turned off",
  );
});

test("the export header carries what the run used", () => {
  const state = session();
  const header = exportHeader({
    appVersion: "1.0.0 (commit abc)",
    apiVersion: null,
    date: "2026-11-16",
    modelId: "dpb",
    modeLabel: "S+rho",
    selection: state.selection,
    degeneracy: true,
    fit: state.fit,
    demo: false,
    issues: [],
    run: runLines(state, MODE, RMSE, true),
  });
  expect(header[0]).toBe("SeeBand Web 1.0.0 (commit abc)");
  expect(header).toContain("Held at their values: B");
});

test("the results subtitle names each unit read, °C, and an open doubt", () => {
  const state = session();
  expect(unitSummary(state.data, MODE)).toEqual([
    "S in µV/K, T in °C, unit in doubt, confirmed",
    "ρ in Ω·m",
  ]);
  expect(
    unitSummary(
      { ...state.data, seebeck: { ...SEEBECK, unitConfirmed: false } },
      MODE,
    )[0],
  ).toBe("S in µV/K, T in °C, unit in doubt");
});
