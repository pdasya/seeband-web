// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS, SYNTHETIC_SEEBECK_ISSUE } from "../../e2e/support/models";

import {
  fitEndNote,
  fitIterations,
  hasFittedValues,
  parameterRows,
  quantityMark,
  resultIssues,
  resultRows,
} from "@/model/resultSummary";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import type { FitResult } from "@/session/store";
import { STRINGS } from "@/strings";

const models = MODELS.models as ModelDescription[];
const allModes = models.flatMap(({ fit_modes: modes }) => modes);
const modelOf = (id: string) =>
  models.find((model) => model.id === id) as ModelDescription;
const modeOf = (id: string) =>
  allModes.find((mode) => mode.id === id) as FitModeDescription;

const RESULT: FitResult = {
  parameters: {},
  status: "converged",
  iterations: 4,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};
const done = (result: Partial<FitResult>) =>
  ({ status: "done", result: { ...RESULT, ...result } }) as const;
const NO_FLAGS = { fit: [], measured: [], derived: [] };

describe("fitIterations", () => {
  test("comes from the state a fit is in", () => {
    expect(fitIterations({ status: "idle" })).toBeNull();
    expect(fitIterations({ status: "waiting" })).toBeNull();
    expect(
      fitIterations({ status: "running", iteration: 2, lastParameters: null }),
    ).toBe(2);
    expect(
      fitIterations({ status: "stopped", iteration: 3, lastParameters: null }),
    ).toBe(3);
    expect(fitIterations(done({}))).toBe(4);
    expect(fitIterations(done({ iterations: null }))).toBeNull();
  });
});

describe("fitEndNote", () => {
  test("says nothing of a fit that converged, or has not ended", () => {
    expect(fitEndNote(done({}), 20)).toBeNull();
    expect(fitEndNote({ status: "idle" }, 20)).toBeNull();
    expect(
      fitEndNote({ status: "running", iteration: 1, lastParameters: null }, 20),
    ).toBeNull();
  });

  test("names the limit, if it is known", () => {
    expect(fitEndNote(done({ status: "iteration_limit" }), 20)).toContain(
      "limit of 20 iterations",
    );
    expect(fitEndNote(done({ status: "iteration_limit" }), null)).toContain(
      "its iteration limit",
    );
  });

  test("tells last values from start values", () => {
    expect(
      fitEndNote(
        { status: "stopped", iteration: null, lastParameters: null },
        20,
      ),
    ).toContain("the values it started from");
    expect(
      fitEndNote(
        { status: "stopped", iteration: 1, lastParameters: { A: 1 } },
        20,
      ),
    ).toContain("its last values");
    expect(fitEndNote(done({ status: "stopped" }), 20)).toContain(
      "its last values",
    );
  });

  test("a failure of either kind is no fitted result", () => {
    const text =
      "The fit failed, so these are not a fitted result: they are its start values or those of its last iteration.";
    expect(fitEndNote(done({ status: "failed" }), 20)).toBe(text);
    expect(
      fitEndNote(
        {
          status: "failed",
          failure: { code: "x", message: "x", details: [] },
        },
        20,
      ),
    ).toBe(text);
  });
});

describe("parameterRows", () => {
  test("shows the scattering's parameters, saved or default", () => {
    const rows = parameterRows(
      modeOf("dpb_s_rho"),
      "dis",
      { band_gap: 554 },
      { status: "idle" },
    );
    const names = rows.map(({ name }) => name);
    expect(names).toContain("F");
    expect(names).not.toContain("A");
    expect(rows.find(({ name }) => name === "band_gap")).toMatchObject({
      symbol: "E_g",
      value: "0,05 eV",
      bounds: "-0,26 … 0,26",
      atBound: false,
    });
  });

  test("converts values and bounds to what the user sees", () => {
    const row = parameterRows(
      modeOf("spb_s_rho"),
      "acPhDis",
      { C: 150 },
      { status: "idle" },
    ).find(({ name }) => name === "C");
    expect(row).toMatchObject({ value: "1,5", bounds: "0,00001 … 10" });
  });

  test("shows bounds of the user's in place of the description's", () => {
    const rows = parameterRows(
      modeOf("dpb_s_rho"),
      "acPh",
      undefined,
      { status: "idle" },
      { band_gap: { lower: 500, upper: 1500 } },
    );
    expect(rows.find(({ name }) => name === "band_gap")?.bounds).toBe(
      "0,04 … 0,13",
    );
    expect(rows.find(({ name }) => name === "fermi_energy")?.bounds).toBe(
      "-0,26 … 0,26",
    );
  });

  test("a value with no fit bounds says it is not fitted", () => {
    const row = parameterRows(modeOf("spb_s"), null, undefined, {
      status: "idle",
    }).find(({ name }) => name === "band_mass");
    expect(row?.bounds).toBe("not fitted");
    expect(row?.value).toMatch(/ mₑ$/);
  });

  test("marks a bound only on a result that fitted something", () => {
    const at = (fit: Parameters<typeof parameterRows>[3]) =>
      parameterRows(modeOf("dpb_s_rho"), "acPh", undefined, fit)
        .filter(({ atBound }) => atBound)
        .map(({ name }) => name);
    expect(at(done({ at_bounds: ["band_gap"] }))).toEqual(["band_gap"]);
    expect(
      at(done({ status: "iteration_limit", at_bounds: ["band_gap"] })),
    ).toEqual(["band_gap"]);
    expect(at(done({ status: "failed", at_bounds: ["band_gap"] }))).toEqual([]);
    expect(at({ status: "idle" })).toEqual([]);
  });
});

describe("resultIssues", () => {
  const original = modeOf("dpb_s_rho_rh");
  const mode = {
    ...original,
    known_issues: [...original.known_issues, SYNTHETIC_SEEBECK_ISSUE],
  };

  test("every known error of every mode has its own text", () => {
    const known: Record<string, string> = STRINGS.fit.knownIssueTexts;
    for (const { known_issues: issues } of allModes) {
      for (const { message_key: key } of issues) {
        expect(known[key], key).toBeDefined();
      }
    }
  });

  test("texts name no ids", () => {
    for (const text of Object.values(STRINGS.fit.knownIssueTexts)) {
      expect(text).not.toMatch(/[a-z]+_[a-z]+/);
    }
  });

  test("one from several sources comes once, with no flags none", () => {
    expect(resultIssues(mode, NO_FLAGS)).toEqual([]);
    expect(
      resultIssues(mode, {
        fit: [SYNTHETIC_SEEBECK_ISSUE.id],
        measured: [SYNTHETIC_SEEBECK_ISSUE.id],
        derived: [SYNTHETIC_SEEBECK_ISSUE.id],
      }),
    ).toHaveLength(1);
  });

  test("goes to the quantity its column names", () => {
    const [issue] = resultIssues(mode, {
      ...NO_FLAGS,
      measured: [SYNTHETIC_SEEBECK_ISSUE.id],
    });
    expect(issue).toMatchObject({
      quantities: ["seebeck"],
      place: "curves",
      severity: "unreliable",
    });
  });

  test("goes to every quantity when it names no column", () => {
    const [issue] = resultIssues(mode, {
      ...NO_FLAGS,
      measured: ["negative_m_eff_weight"],
    });
    expect(issue?.quantities).toEqual(["seebeck", "resistivity", "hall"]);
    expect(issue?.severity).toBe("caution");
  });

  test("a fit's flag marks the curves drawn from its values too", () => {
    const [issue] = resultIssues(mode, {
      ...NO_FLAGS,
      fit: [SYNTHETIC_SEEBECK_ISSUE.id],
    });
    expect(issue?.quantities).toEqual(["seebeck"]);
    expect(issue?.place).toBe("curves");
  });

  test("with no measured curve, a fit's flag goes with the fitted values", () => {
    const [issue] = resultIssues(mode, {
      ...NO_FLAGS,
      fit: ["dpb_loop_degeneracy"],
    });
    expect(issue?.quantities).toEqual([]);
    expect(issue?.place).toBe("fit");
  });

  test("the curves of the open tab mark no RMSE", () => {
    const [issue] = resultIssues(mode, {
      ...NO_FLAGS,
      derived: [SYNTHETIC_SEEBECK_ISSUE.id],
    });
    expect(issue?.quantities).toEqual([]);
    expect(issue?.place).toBe("curves");
  });

  test("an id not in the description still shows, as unreliable", () => {
    const [issue] = resultIssues(undefined, {
      ...NO_FLAGS,
      measured: ["new_one"],
    });
    expect(issue).toMatchObject({
      text: STRINGS.fit.knownIssueOther,
      severity: "unreliable",
      quantities: [],
    });
  });
});

describe("quantityMark", () => {
  const issue = (severity: "unreliable" | "caution") =>
    ({
      id: severity,
      text: "",
      severity,
      quantities: ["seebeck"],
      place: "curves",
    }) as const;

  test("gives the worst on that quantity", () => {
    expect(quantityMark([], "seebeck")).toBeNull();
    expect(quantityMark([issue("caution")], "hall")).toBeNull();
    expect(quantityMark([issue("caution")], "seebeck")).toBe("caution");
    expect(
      quantityMark([issue("caution"), issue("unreliable")], "seebeck"),
    ).toBe("unreliable");
  });
});

describe("hasFittedValues", () => {
  test("only a fit that gave values", () => {
    expect(hasFittedValues(done({}))).toBe(true);
    expect(hasFittedValues(done({ status: "iteration_limit" }))).toBe(true);
    expect(hasFittedValues(done({ status: "failed" }))).toBe(false);
    expect(
      hasFittedValues({
        status: "stopped",
        iteration: 2,
        lastParameters: { band_gap: 900 },
      }),
    ).toBe(true);
    expect(
      hasFittedValues({
        status: "stopped",
        iteration: null,
        lastParameters: null,
      }),
    ).toBe(false);
    expect(hasFittedValues({ status: "idle" })).toBe(false);
    expect(
      hasFittedValues({
        status: "running",
        iteration: 1,
        lastParameters: null,
      }),
    ).toBe(false);
  });
});

describe("resultRows", () => {
  const selection = (scattering: string | null) => ({
    scattering,
    band1Degeneracy: 2,
    band2Degeneracy: 1,
  });
  const rowsOf = (model: string, mode: string, scattering: string | null) =>
    resultRows(
      modelOf(model),
      modeOf(mode),
      selection(scattering),
      undefined,
      done({}),
    );
  const statuses = (rows: ReturnType<typeof rowsOf>) =>
    Object.fromEntries(
      rows.map(({ name, status }) => [
        name,
        status.kind === "needs"
          ? `needs ${status.quantities.join(",")}`
          : status.kind,
      ]),
    );

  test("DPB S + ρ: fitted values, fixed degeneracies, and m₁ needs R_H", () => {
    const rows = rowsOf("dpb", "dpb_s_rho", "acPh");
    expect(statuses(rows)).toEqual({
      m_eff: "fitted",
      band_gap: "fitted",
      fermi_energy: "fitted",
      A: "fitted",
      B: "fitted",
      degeneracy: "fixed",
      m1: "needs hall",
    });
    expect(rows.find(({ name }) => name === "degeneracy")).toMatchObject({
      symbol: "N₁, N₂",
      value: "2, 1",
      bounds: "",
    });
    expect(rows.find(({ name }) => name === "m1")).toMatchObject({
      symbol: "m₁",
      value: "",
      bounds: "",
    });
    expect(rows.find(({ name }) => name === "band_gap")?.meaning).not.toBe("");
  });

  test("DPB S: what needs ρ or R_H, and nothing that depends on a scattering", () => {
    expect(statuses(rowsOf("dpb", "dpb_s", null))).toEqual({
      m_eff: "fitted",
      band_gap: "fitted",
      fermi_energy: "fitted",
      degeneracy: "fixed",
      m1: "needs resistivity,hall",
    });
  });

  test("the scattering in use decides what another mode would add", () => {
    expect(statuses(rowsOf("dpb", "dpb_s_rho", "dis")).m1).toBe("needs hall");
    expect(statuses(rowsOf("dpb", "dpb_s_rho", "dis")).F).toBe("fitted");
  });

  test("names the fewest data that find a parameter, in any order of modes", () => {
    const dpb = modelOf("dpb");
    // Backwards, so that the mode with R_H comes first, and with a scattering, so that A counts.
    const reversed = { ...dpb, fit_modes: [...dpb.fit_modes].reverse() };
    const rows = resultRows(
      reversed,
      modeOf("dpb_s"),
      selection("acPh"),
      undefined,
      done({}),
    );
    expect(statuses(rows)).toMatchObject({
      A: "needs resistivity",
      B: "needs resistivity",
      m1: "needs resistivity,hall",
    });
    expect(statuses(rows)).not.toHaveProperty("C");
  });

  test("a mode that cannot run makes nothing needed", () => {
    const dpb = modelOf("dpb");
    const withoutHall = {
      ...dpb,
      fit_modes: dpb.fit_modes.map((mode) =>
        mode.id === "dpb_s_rho_rh" ? { ...mode, disabled: true } : mode,
      ),
    };
    const rows = resultRows(
      withoutHall,
      modeOf("dpb_s_rho"),
      selection("acPh"),
      undefined,
      done({}),
    );
    expect(statuses(rows)).not.toHaveProperty("m1");
  });

  test("with all data, nothing is needed", () => {
    const rows = rowsOf("dpb", "dpb_s_rho_rh", "acPh");
    expect(rows.filter(({ status }) => status.kind === "needs")).toEqual([]);
  });

  test("SPB: a mass the mode does not fit is fixed, with no bounds", () => {
    const rows = rowsOf("spb", "spb_s_rho", "acPh");
    expect(rows.find(({ name }) => name === "band_mass")).toMatchObject({
      status: { kind: "fixed" },
      bounds: "",
    });
    expect(rows.some(({ name }) => name === "degeneracy")).toBe(false);
    expect(rows.filter(({ status }) => status.kind === "needs")).toEqual([]);
  });
});
