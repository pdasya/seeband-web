// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import {
  editableParameters,
  withCustomRange,
  coreToDisplay,
  displayToCore,
  parameterValues,
  shortened,
  steppedDisplayValue,
  tidy,
  typedDisplayValue,
  visibleParameters,
  type ParameterDescription,
} from "@/model/parameters";
import type { FitModeDescription, ModelDescription } from "@/model/selection";

const models = MODELS.models as ModelDescription[];

function mode(id: string): FitModeDescription {
  const found = models
    .flatMap((model) => model.fit_modes)
    .find((candidate) => candidate.id === id);
  if (found === undefined) {
    throw new Error(id);
  }
  return found;
}

function parameter(modeId: string, name: string): ParameterDescription {
  const found = mode(modeId).parameters.find((p) => p.name === name);
  if (found === undefined) {
    throw new Error(name);
  }
  return found;
}

const names = (modeId: string, scattering: string | null) =>
  visibleParameters(mode(modeId), scattering).map(({ name }) => name);

describe("visibleParameters", () => {
  test("follow the scattering type", () => {
    expect(names("dpb_s_rho", "acPh")).toEqual([
      "m_eff",
      "band_gap",
      "fermi_energy",
      "A",
      "B",
    ]);
    expect(names("dpb_s_rho", "dis")).toEqual([
      "m_eff",
      "band_gap",
      "fermi_energy",
      "F",
      "G",
    ]);
    expect(names("dpb_s_rho", "acPhDis")).toEqual([
      "m_eff",
      "band_gap",
      "fermi_energy",
      "A",
      "B",
      "C",
      "D",
    ]);
  });

  test("a mode with no choice of scattering shows all its parameters", () => {
    expect(names("spb_s", null)).toEqual(["band_mass", "fermi_energy"]);
    expect(names("dpb_s", null)).toEqual(["m_eff", "band_gap", "fermi_energy"]);
  });

  test("m1 is there only with R_H", () => {
    expect(names("dpb_s_rho_rh", "acPh")).toContain("m1");
    expect(names("dpb_s_rho", "acPh")).not.toContain("m1");
  });
});

describe("parameterValues", () => {
  test("holds every parameter of a mode, in core units, whatever the scattering", () => {
    const values = parameterValues(mode("spb_s_rho"), undefined);

    expect(Object.keys(values)).toEqual([
      "band_mass",
      "fermi_energy",
      "A",
      "C",
      "F",
    ]);
    expect(values.C).toBe(100);
    expect(values.band_mass).toBe(-1);
  });

  test("keeps what was set, including zero", () => {
    expect(parameterValues(mode("dpb_s"), { band_gap: 0 })).toEqual({
      m_eff: 1.01,
      band_gap: 0,
      fermi_energy: -100,
    });
  });
});

describe("conversion", () => {
  test("is direct where the two scales agree", () => {
    const mass = parameter("dpb_s", "m_eff");

    expect(coreToDisplay(mass, 1.01)).toBe(1.01);
    expect(displayToCore(mass, 1.01)).toBe(1.01);
  });

  test("follows the scales where they differ, as for C in SPB", () => {
    const c = parameter("spb_s_rho", "C");

    expect(coreToDisplay(c, c.core_range.default)).toBe(
      c.display_range.default,
    );
    expect(coreToDisplay(c, c.core_range.maximum)).toBe(
      c.display_range.maximum,
    );
    expect(displayToCore(c, 1.5)).toBe(150);
  });

  test("every default and limit of the contract converts to the other range", () => {
    for (const model of models) {
      for (const { parameters } of model.fit_modes) {
        for (const p of parameters) {
          for (const key of ["minimum", "maximum", "default"] as const) {
            expect(tidy(coreToDisplay(p, p.core_range[key]))).toBe(
              tidy(p.display_range[key]),
            );
            expect(tidy(displayToCore(p, p.display_range[key]))).toBe(
              tidy(p.core_range[key]),
            );
          }
        }
      }
    }
  });
});

describe("displayToCore on whole control units", () => {
  test("gives what the desktop's slider sends, for every position of every parameter", () => {
    const wrong: string[] = [];
    for (const model of models) {
      for (const { id, parameters } of model.fit_modes) {
        // Energies shown in eV have a test of their own below.
        for (const p of parameters.filter(
          ({ display_factor: factor }) => factor === 1,
        )) {
          const { minimum, maximum } = p.value_range;
          const stride = Math.max(1, Math.floor((maximum - minimum) / 5000));
          for (let units = minimum; units <= maximum; units += stride) {
            const display = tidy(
              p.display_scale < 1
                ? units / Math.round(1 / p.display_scale)
                : units * p.display_scale,
            );
            const expected =
              p.fit_scale < 1
                ? units / Math.round(1 / p.fit_scale)
                : units * p.fit_scale;
            if (displayToCore(p, display) !== expected) {
              wrong.push(`${id} ${p.name} ${String(units)}`);
            }
          }
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  test("an energy in eV comes back to the same kelvin", () => {
    const energies = models.flatMap(({ fit_modes: modes }) =>
      modes.flatMap(({ parameters }) =>
        parameters.filter(({ display_unit: unit }) => unit === "eV"),
      ),
    );
    expect(energies.length).toBeGreaterThan(0);
    const wrong: string[] = [];
    for (const p of energies) {
      const { minimum, maximum } = p.core_range;
      for (let kelvin = minimum; kelvin <= maximum; kelvin += 1) {
        if (displayToCore(p, coreToDisplay(p, kelvin)) !== kelvin) {
          wrong.push(`${p.name} ${String(kelvin)}`);
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  test("keeps 2.55 from becoming 254.99999999999997", () => {
    expect(displayToCore(parameter("spb_s_rho", "C"), 2.55)).toBe(255);
    expect(displayToCore(parameter("spb_s_rho", "C"), 1.15)).toBe(115);
  });

  test("a value between units stays between them", () => {
    expect(displayToCore(parameter("spb_s_rho", "C"), 1.234)).toBe(123.4);
  });
});

describe("shortened", () => {
  test("keeps 6 digits, and leaves what fits", () => {
    expect(shortened(1.25646323123)).toBe(1.25646);
    expect(shortened(651.553903512)).toBe(651.554);
    expect(shortened(1000000)).toBe(1000000);
    expect(shortened(1.01)).toBe(1.01);
    expect(shortened(0)).toBe(0);
  });
});

describe("typedDisplayValue", () => {
  const mass = parameter("spb_s", "band_mass");

  test("takes a number within the range, between steps too", () => {
    expect(typedDisplayValue(mass, "-3")).toBe(-3);
    expect(typedDisplayValue(mass, "3")).toBe(3);
    expect(typedDisplayValue(mass, "1.2345")).toBe(1.2345);
    expect(typedDisplayValue(mass, "1,2345")).toBe(1.2345);
  });

  test("refuses anything else", () => {
    for (const text of ["", " ", "3.01", "-3.01", "abc", "1e400"]) {
      expect(typedDisplayValue(mass, text)).toBeNull();
    }
  });

  test("takes a bound in eV as the screen shows it, as that bound", () => {
    const gap = parameter("dpb_s", "band_gap");
    expect(typedDisplayValue(gap, "0,26")).toBe(gap.display_range.maximum);
    expect(typedDisplayValue(gap, "-0,26")).toBe(gap.display_range.minimum);
    expect(typedDisplayValue(gap, "0,27")).toBeNull();
  });
});

describe("steppedDisplayValue", () => {
  test("moves by the step, stays in the range, and keeps off a grid", () => {
    const mass = parameter("dpb_s", "m_eff");

    expect(steppedDisplayValue(mass, 1.01, 1)).toBe(1.02);
    expect(steppedDisplayValue(mass, 1.234, -1)).toBe(1.224);
    expect(steppedDisplayValue(mass, 2.995, 1)).toBe(3);
    expect(steppedDisplayValue(mass, -3, -10)).toBe(-3);
  });

  test("G with R_H moves by its large step from a default off that step", () => {
    const g = parameter("dpb_s_rho_rh", "G");

    expect(steppedDisplayValue(g, 1, 1)).toBe(2);
    expect(steppedDisplayValue(g, 1, -1)).toBe(0.5);
  });
});

describe("editableParameters", () => {
  const modeOf = (id: string) =>
    models
      .flatMap(({ fit_modes: modes }) => modes)
      .find((mode) => mode.id === id) as FitModeDescription;
  const names = (id: string, scattering: string | null) =>
    editableParameters(modeOf(id), scattering).map(
      ({ parameter }) => parameter.name,
    );

  test("holds what is fitted, with editable bounds, in this scattering", () => {
    expect(names("dpb_s_rho", "dis")).toEqual([
      "m_eff",
      "band_gap",
      "fermi_energy",
      "F",
      "G",
    ]);
  });

  test("leaves out fixed bounds, and what a fit does not change", () => {
    expect(names("spb_s_rho", "acPh")).toEqual(["fermi_energy"]);
    expect(names("spb_s", null)).toEqual(["fermi_energy"]);
  });

  test("gives the bounds of the description", () => {
    const [first] = editableParameters(modeOf("spb_s"), null);
    expect(first?.bounds).toEqual({ lower: -3000, upper: 3000 });
  });
});

describe("withCustomRange", () => {
  const parameter = models
    .flatMap(({ fit_modes: modes }) => modes)
    .flatMap(({ parameters }) => parameters)
    .find(({ name }) => name === "band_gap") as ParameterDescription;

  test("leaves a parameter with no bounds of the user's as it is", () => {
    expect(withCustomRange(parameter, undefined)).toBe(parameter);
  });

  test("sets the range the control uses, and only that", () => {
    const next = withCustomRange(parameter, { lower: 500, upper: 4000 });
    // In eV, as an energy is shown: 500 K and 4000 K.
    expect(next.display_range).toMatchObject({
      minimum: 0.04308666631,
      maximum: 0.34469333048,
    });
    expect(next.display_range.step).toBe(parameter.display_range.step);
    expect(next.core_range).toEqual(parameter.core_range);
    expect(parameter.display_range.maximum).toBe(0.25851999786);
  });
});
