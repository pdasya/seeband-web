// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import type { CalcResponse } from "@/api/client";
import {
  commented,
  csvField,
  csvFile,
  dataFile,
  exportHeader,
  graphFile,
  numberText,
  parametersCsv,
  parametersFile,
  table,
  zipEntries,
  type ExportContext,
} from "@/model/exportFiles";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import type { FitResult, FitState, SessionState } from "@/session/store";

const modes = (MODELS.models as ModelDescription[]).flatMap(
  ({ fit_modes: fitModes }) => fitModes,
);
const modeOf = (id: string) =>
  modes.find((mode) => mode.id === id) as FitModeDescription;

const RESULT: FitResult = {
  parameters: {},
  status: "converged",
  iterations: 2,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};
const DONE: FitState = { status: "done", result: RESULT };
const SELECTION = {
  model: "dpb",
  fitMode: "dpb_s_rho",
  scattering: "acPh",
  band1Degeneracy: 1,
  band2Degeneracy: 2,
  minTemperatureK: 50,
  maxTemperatureK: 800,
};
const CONTEXT: ExportContext = {
  appVersion: "1.2.3",
  apiVersion: "0.4.0",
  date: "2026-11-08T12:00:00.000Z",
  modelId: "dpb",
  modeLabel: "S + ρ",
  selection: SELECTION,
  degeneracy: true,
  fit: DONE,
  demo: false,
  issues: [],
};

describe("numbers and tables", () => {
  test("numbers keep a point and full precision, and leave out what is not finite", () => {
    expect(numberText(0.1 + 0.2)).toBe("0.30000000000000004");
    expect(numberText(-1.5e-7)).toBe("-1.5e-7");
    expect(numberText(null)).toBe("");
    expect(numberText(Number.NaN)).toBe("");
  });

  test("columns of other lengths leave empty fields, as the desktop's do", () => {
    expect(
      table([
        { legend: "a", values: [1, 2, 3] },
        { legend: "b", values: [4] },
        { legend: "c", values: [5, null] },
      ]),
    ).toBe("a\tb\tc\n1\t4\t5\n2\t\t\n3\t\t\n");
  });

  test("a header is comments, and no header is nothing", () => {
    expect(commented(["one", "two"])).toBe("# one\n# two\n");
    expect(commented([])).toBe("");
  });
});

describe("the header", () => {
  test("says what the file is of", () => {
    expect(exportHeader(CONTEXT)).toEqual([
      "SeeBand Web 1.2.3, API 0.4.0",
      "Exported 2026-11-08T12:00:00.000Z",
      "Model DPB, fit mode S + ρ",
      "Scattering acPh",
      "Fit range 50-800 K",
      "Band degeneracies N1 = 1, N2 = 2",
      "Fit converged, 2 iterations",
    ]);
  });

  test("demo data, known issues, no fit, no scattering and one band", () => {
    const lines = exportHeader({
      ...CONTEXT,
      apiVersion: null,
      demo: true,
      degeneracy: false,
      selection: { ...SELECTION, scattering: null },
      fit: { status: "idle" },
      issues: [
        {
          id: "dpb_hall_prefactor",
          text: "DPB R_H is half of what it should be.",
          severity: "unreliable",
          quantities: ["hall"],
          place: "curves",
        },
      ],
    });
    expect(lines[0]).toBe("SeeBand Web 1.2.3");
    expect(lines).toContain(
      "Demo data: synthetic, made with the DPB model and noise. Not a measurement.",
    );
    expect(lines.some((line) => line.startsWith("Scattering"))).toBe(false);
    expect(lines.some((line) => line.startsWith("Band degeneracies"))).toBe(
      false,
    );
    expect(lines).toContain("No fit: the values are those on the screen");
    expect(lines.at(-1)).toBe(
      "Unreliable: DPB R_H is half of what it should be. (dpb_hall_prefactor)",
    );
  });

  test("a stopped fit says after which iteration", () => {
    expect(
      exportHeader({
        ...CONTEXT,
        fit: { status: "stopped", iteration: 4, lastParameters: {} },
      }),
    ).toContain("Fit stopped, 4 iterations");
  });
});

const curves = (
  values: Record<string, number[]>,
  temperatureK = [100, 200],
): CalcResponse => ({
  temperature_k: temperatureK,
  curves: values,
  known_issues: [],
  rmse: {},
});

describe("the data file", () => {
  const session: Pick<SessionState, "data" | "interpolation"> = {
    data: {
      seebeck: {
        measurement: {
          temperature_k: [100, 150, 200],
          values: [1e-4, 1.5e-4, 2e-4],
          points: 3,
          min_temperature_k: 100,
          max_temperature_k: 200,
        },
        source: { kind: "file", name: "s.txt" },
        extrapolated: false,
        text: "",
      },
    },
    interpolation: {
      enabled: false,
      loading: false,
      values: {},
      failed: [],
      failure: null,
    },
  };

  test("has each quantity's data and curves, before and after the fit, in SI", () => {
    const file = dataFile(
      ["head"],
      modeOf("dpb_s_rho"),
      session,
      curves({ seebeck_v_per_k: [1, 2], resistivity_ohm_m: [3, 4] }),
      curves({ seebeck_v_per_k: [5, 6], resistivity_ohm_m: [7, 8] }),
    );
    const [comment, legends, ...rows] = file.split("\n").slice(0, -1);
    expect(comment).toBe("# head");
    expect(legends?.split("\t")).toEqual([
      "Temperature [K]",
      "Experimental Seebeck coefficient [V/K]",
      "Temperature [K]",
      "Pre-fit Seebeck coefficient [V/K]",
      "Temperature [K]",
      "Fit Seebeck coefficient [V/K]",
      "Temperature [K]",
      "Pre-fit electrical resistivity [Ohm*m]",
      "Temperature [K]",
      "Fit electrical resistivity [Ohm*m]",
    ]);
    expect(rows).toEqual([
      "100\t0.0001\t100\t1\t100\t5\t100\t3\t100\t7",
      "150\t0.00015\t200\t2\t200\t6\t200\t4\t200\t8",
      "200\t0.0002\t\t\t\t\t\t\t\t",
    ]);
  });

  test("with no fit, the curve of the values on the screen is the one before a fit", () => {
    const legends = dataFile(
      [],
      modeOf("dpb_s"),
      session,
      curves({ seebeck_v_per_k: [1, 2] }),
      null,
    ).split("\n")[0];
    expect(legends).not.toMatch(/Fit Seebeck/);
    expect(legends).toMatch(/Pre-fit Seebeck/);
  });

  test("interpolated values a fit used come after the measured ones", () => {
    const legends = dataFile(
      [],
      modeOf("dpb_s"),
      {
        ...session,
        interpolation: {
          ...session.interpolation,
          enabled: true,
          values: {
            seebeck: {
              temperature_k: [100, 120],
              values: [1e-4, 1.2e-4],
              extrapolated: false,
              measured_points_in_range: 2,
              underdetermined: false,
            },
          },
        },
      },
      null,
      null,
    ).split("\n")[0];
    expect(legends?.split("\t")).toEqual([
      "Temperature [K]",
      "Experimental Seebeck coefficient [V/K]",
      "Temperature [K]",
      "Interpolated Seebeck coefficient [V/K]",
    ]);
  });
});

describe("the parameters file", () => {
  test("has each value as the screen shows it, with its unit and status", () => {
    const file = parametersFile(
      [],
      modeOf("dpb_s_rho"),
      SELECTION,
      { band_gap: 900, fermi_energy: -50 },
      { status: "done", result: { ...RESULT, at_bounds: ["band_gap"] } },
    );
    const lines = file.split("\n").slice(0, -1);
    expect(lines[0]).toBe("Parameter\tValue\tStatus");
    expect(lines).toContain(
      "E_g (position of band 2) [K]\t900\tfitted, at bound",
    );
    expect(lines.find((line) => line.startsWith("E_F"))).toMatch(
      /\t-50\tfitted$/,
    );
    expect(lines.at(-1)).toBe("N1, N2 (band degeneracies)\t1, 2\tfixed");
  });

  test("a value the mode holds is fixed, and SPB has no degeneracies", () => {
    const lines = parametersFile(
      [],
      modeOf("spb_s_rho"),
      { ...SELECTION, scattering: "acPh" },
      undefined,
      DONE,
    ).split("\n");
    expect(lines.find((line) => line.startsWith("m"))).toMatch(/\tfixed$/);
    expect(lines.some((line) => line.startsWith("N1"))).toBe(false);
  });
});

describe("a graph file", () => {
  test("names each column with its unit, and keeps a name it does not know", () => {
    expect(
      graphFile(
        [],
        [100, 200],
        [
          { name: "chemical_potential_k", values: [-10, 20] },
          { name: "some_new_curve_per_s", values: [1, 2] },
        ],
      ),
    ).toBe(
      "Temperature [K]\tChemical potential [K]\tsome_new_curve_per_s\n100\t-10\t1\n200\t20\t2\n",
    );
  });
});

describe("the other formats", () => {
  const session: Pick<SessionState, "data" | "interpolation"> = {
    data: {
      seebeck: {
        measurement: {
          temperature_k: [100, 150],
          values: [1e-4, 1.5e-4],
          points: 2,
          min_temperature_k: 100,
          max_temperature_k: 150,
        },
        source: { kind: "file", name: "s.txt" },
        extrapolated: false,
        text: "",
      },
    },
    interpolation: {
      enabled: false,
      loading: false,
      values: {},
      failed: [],
      failure: null,
    },
  };
  const preFit = curves({ seebeck_v_per_k: [1, 2], resistivity_ohm_m: [3, 4] });
  const fitted = curves({ seebeck_v_per_k: [5, 6], resistivity_ohm_m: [7, 8] });

  test("CSV has a row for each point, with its quantity, curve and unit", () => {
    const lines = csvFile(
      ["head"],
      modeOf("dpb_s_rho"),
      session,
      preFit,
      fitted,
    )
      .split("\n")
      .slice(0, -1);
    expect(lines.slice(0, 4)).toEqual([
      "# head",
      "quantity,curve,temperature_k,value,unit",
      "seebeck,experimental,100,0.0001,V/K",
      "seebeck,experimental,150,0.00015,V/K",
    ]);
    expect(lines).toContain("seebeck,pre_fit,200,2,V/K");
    expect(lines).toContain("resistivity,fit,100,7,Ohm*m");
    expect(lines).toHaveLength(2 + 2 + 2 * 4);
  });

  test("ZIP has a plain table for each part, with names the parser reads", () => {
    const entries = zipEntries(
      ["head"],
      modeOf("dpb_s_rho"),
      session,
      preFit,
      fitted,
      "parameters",
      [
        {
          kind: "chemical_potential",
          result: curves({ chemical_potential_k: [1, 2] }),
        },
      ],
    );
    expect(Object.keys(entries).sort()).toEqual(
      [
        "metadata.txt",
        "parameters.txt",
        "data/seebeck.txt",
        "curves/pre-fit.txt",
        "curves/fit.txt",
        "graphs/chemical_potential.txt",
      ].sort(),
    );
    expect(entries["metadata.txt"]).toBe("head\n");
    expect(entries["data/seebeck.txt"]).toBe(
      "# head\nT [K]\tS [V/K]\n100\t0.0001\n150\t0.00015\n",
    );
    expect(entries["curves/fit.txt"]).toBe(
      "# head\nT [K]\tS [V/K]\trho [Ohm*m]\n100\t5\t7\n200\t6\t8\n",
    );
  });
});

describe("the parameters as CSV", () => {
  test("a field with a comma or quote is quoted", () => {
    expect(csvField("plain")).toBe("plain");
    expect(csvField("a, b")).toBe('"a, b"');
    expect(csvField('say "x"')).toBe('"say ""x"""');
  });

  test("has a row for each parameter, and N1 and N2 apart", () => {
    const lines = parametersCsv(
      ["head"],
      modeOf("dpb_s_rho"),
      SELECTION,
      { band_gap: 900 },
      { status: "done", result: { ...RESULT, at_bounds: ["band_gap"] } },
    )
      .split("\n")
      .slice(0, -1);
    expect(lines.slice(0, 2)).toEqual([
      "# head",
      "parameter,symbol,meaning,unit,value,status",
    ]);
    expect(lines).toContain(
      'band_gap,E_g,position of band 2,K,900,"fitted, at bound"',
    );
    expect(lines.find((line) => line.startsWith("m_eff,"))).toMatch(
      /^m_eff,m₂\/m₁,"band mass ratio m2\/m1, the sign sets the type of band 2",,/,
    );
    expect(lines.slice(-2)).toEqual([
      "band_1_degeneracy,N1,band degeneracies,,1,fixed",
      "band_2_degeneracy,N2,band degeneracies,,2,fixed",
    ]);
  });
});
