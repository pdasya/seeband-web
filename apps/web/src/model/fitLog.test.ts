// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import { fitLog } from "@/model/fitLog";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import type { FitResult, FitState } from "@/session/store";

const modes = (MODELS.models as ModelDescription[]).flatMap(
  ({ fit_modes: fitModes }) => fitModes,
);
const modeOf = (id: string) =>
  modes.find((mode) => mode.id === id) as FitModeDescription;

const RESULT: FitResult = {
  parameters: {},
  status: "converged",
  iterations: 3,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};
const done = (result: Partial<FitResult> = {}): FitState => ({
  status: "done",
  result: { ...RESULT, ...result },
});
const NET = { min_temperature_k: 300, max_temperature_k: 800 };

describe("fitLog", () => {
  test("an iterative fit: start, each stage of its loop, the stage after, and convergence", () => {
    expect(fitLog(modeOf("dpb_s_rho_rh"), "acPh", done(), NET)).toEqual([
      {
        title: "Start values",
        text: "The neural net's guess, from its net for 300–800 K",
      },
      {
        title: "Fit to S",
        text: "Finds m₂/m₁, E_g, E_F, in each of 3 iterations",
      },
      { title: "Fit to ρ", text: "Finds A, B, in each of 3 iterations" },
      { title: "Fit to R_H", text: "Finds m₁" },
      {
        title: "Converged",
        text: "The fit met its stop rule, a change of at most 10 %, in iteration 3.",
      },
    ]);
  });

  test("the scattering decides what the ρ fit finds", () => {
    const steps = fitLog(modeOf("dpb_s_rho"), "dis", done(), null);
    expect(steps[0]?.text).toBe("The values on the fit screen");
    expect(steps[2]).toEqual({
      title: "Fit to ρ",
      text: "Finds F, G, in each of 3 iterations",
    });
  });

  test("a single pass runs each stage once, and says that it does not iterate", () => {
    expect(
      fitLog(
        modeOf("spb_s_rho"),
        "acPhDis",
        done({ iterations: null }),
        null,
      ).slice(1),
    ).toEqual([
      { title: "Fit to S", text: "Finds E_F" },
      { title: "Fit to ρ", text: "Finds A, C" },
      { title: "Done", text: "One pass: this fit mode does not iterate." },
    ]);
  });

  test("a mass the mode does not fit is left out", () => {
    const steps = fitLog(
      modeOf("spb_s"),
      null,
      done({ iterations: null }),
      null,
    );
    expect(steps.map(({ title }) => title)).toEqual([
      "Start values",
      "Fit to S",
      "Done",
    ]);
    expect(steps[1]?.text).toBe("Finds E_F");
  });

  test("the iteration limit says so, with the limit", () => {
    const steps = fitLog(
      modeOf("dpb_s_rho"),
      "acPh",
      done({ status: "iteration_limit", iterations: 1000 }),
      null,
    );
    expect(steps.at(-1)).toEqual({
      title: "Iteration limit",
      text: "The fit reached its limit of 1000 iterations before every parameter settled.",
    });
  });

  test("a stopped fit ran its loop only, and says where it stopped", () => {
    const stopped: FitState = {
      status: "stopped",
      iteration: 4,
      lastParameters: { band_gap: 900 },
    };
    expect(
      fitLog(modeOf("dpb_s_rho_rh"), "acPh", stopped, null)
        .slice(1)
        .map(({ title, text }) => `${title}: ${text}`),
    ).toEqual([
      "Fit to S: Finds m₂/m₁, E_g, E_F, in each of 4 iterations",
      "Fit to ρ: Finds A, B, in each of 4 iterations",
      "Stopped: Stopped by the user after iteration 4.",
    ]);
  });

  test("one iteration is not plural", () => {
    expect(
      fitLog(modeOf("dpb_s_rho"), "acPh", done({ iterations: 1 }), null)[1]
        ?.text,
    ).toBe("Finds m₂/m₁, E_g, E_F, in each of 1 iteration");
  });

  test("a threshold is a percent with no rounding error", () => {
    const mode = { ...modeOf("dpb_s_rho"), threshold: 0.07 };
    expect(fitLog(mode, "acPh", done(), null).at(-1)?.text).toBe(
      "The fit met its stop rule, a change of at most 7 %, in iteration 3.",
    );
  });
});
