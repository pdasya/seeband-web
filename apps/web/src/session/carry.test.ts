import { describe, expect, test } from "vitest";

import type { FitModeDescription } from "@/model/selection";
import { carryParameters } from "@/session/carry";

function mode(
  id: string,
  defaults: Record<string, number>,
): FitModeDescription {
  return {
    id,
    parameters: Object.entries(defaults).map(([name, value]) => ({
      name,
      core_range: { minimum: -1e6, maximum: 1e6, step: 1, default: value },
    })),
  } as unknown as FitModeDescription;
}

// As SPB: the modes start from other values, and only S + ρ has A.
const S = mode("spb_s", { band_mass: 1.01, fermi_energy: 100 });
const S_RHO = mode("spb_s_rho", { band_mass: -1, fermi_energy: -100, A: 4e4 });

const EMPTY = {
  parameters: {},
  customBounds: {},
  held: {},
  guessedParameters: {},
};

describe("carryParameters", () => {
  test("takes the shown value of each shared parameter, set or default", () => {
    const carried = carryParameters(
      { ...EMPTY, parameters: { spb_s: { fermi_energy: 250 } } },
      S,
      S_RHO,
    );

    expect(carried.parameters.spb_s_rho).toEqual({
      band_mass: 1.01,
      fermi_energy: 250,
    });
    expect(carried.parameters.spb_s).toEqual({ fermi_energy: 250 });
    // A carried default is no one's choice, so an automatic guess may replace it.
    expect(carried.guessedParameters.spb_s_rho).toEqual({ band_mass: 1.01 });
  });

  test("leaves a parameter only the new mode has as it was there", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        parameters: { spb_s_rho: { A: 5e4, band_mass: -2 } },
        customBounds: { spb_s_rho: { A: { lower: 1, upper: 9e4 } } },
        held: { spb_s_rho: ["A", "band_mass"] },
      },
      S,
      S_RHO,
    );

    expect(carried.parameters.spb_s_rho).toEqual({
      A: 5e4,
      band_mass: 1.01,
      fermi_energy: 100,
    });
    expect(carried.customBounds.spb_s_rho).toEqual({
      A: { lower: 1, upper: 9e4 },
    });
    expect(carried.held.spb_s_rho).toEqual(["A"]);
  });

  test("takes bounds, holds and guess marks of shared parameters along", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        parameters: { spb_s_rho: { band_mass: -3, A: 5e4 } },
        customBounds: {
          spb_s_rho: {
            band_mass: { lower: -5, upper: 5 },
            fermi_energy: { lower: -50, upper: 50 },
          },
        },
        held: { spb_s_rho: ["band_mass", "A"] },
        guessedParameters: { spb_s_rho: { band_mass: -3 } },
      },
      S_RHO,
      S,
    );

    expect(carried.parameters.spb_s).toEqual({
      band_mass: -3,
      fermi_energy: -100,
    });
    expect(carried.customBounds.spb_s).toEqual({
      band_mass: { lower: -5, upper: 5 },
      fermi_energy: { lower: -50, upper: 50 },
    });
    expect(carried.held.spb_s).toEqual(["band_mass"]);
    expect(carried.guessedParameters.spb_s).toEqual({
      band_mass: -3,
      fermi_energy: -100,
    });
  });

  test("drops bounds and holds of the new mode that the old one did not have", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        customBounds: { spb_s_rho: { fermi_energy: { lower: 0, upper: 1 } } },
        held: { spb_s_rho: ["fermi_energy"] },
        guessedParameters: { spb_s_rho: { fermi_energy: 1 } },
      },
      S,
      S_RHO,
    );

    expect(carried.customBounds.spb_s_rho).toEqual({});
    expect(carried.held.spb_s_rho).toEqual([]);
    // Only the defaults carried from S, which a guess may replace, not the old estimate.
    expect(carried.guessedParameters.spb_s_rho).toEqual({
      band_mass: 1.01,
      fermi_energy: 100,
    });
  });

  test("leaves a default unset where the new mode has the same one", () => {
    const DPB_S = mode("dpb_s", { band_gap: 1000, fermi_energy: -100 });
    const DPB_S_RHO = mode("dpb_s_rho", {
      band_gap: 1000,
      fermi_energy: -100,
      A: 4e4,
    });
    const carried = carryParameters(
      { ...EMPTY, parameters: { dpb_s_rho: { band_gap: 800, A: 5e4 } } },
      DPB_S,
      DPB_S_RHO,
    );

    // An automatic guess takes an unset value for a default, and fills it.
    expect(carried.parameters.dpb_s_rho).toEqual({ A: 5e4 });
  });

  test("takes E_F and A from SPB to DPB, and leaves the band mass", () => {
    const DPB = mode("dpb_s_rho", {
      m_eff: 1.01,
      band_gap: 1000,
      fermi_energy: -100,
      A: 4e4,
    });
    const carried = carryParameters(
      {
        ...EMPTY,
        parameters: { spb_s_rho: { band_mass: 2, fermi_energy: 300, A: 6e4 } },
      },
      S_RHO,
      DPB,
    );

    expect(carried.parameters.dpb_s_rho).toEqual({
      fermi_energy: 300,
      A: 6e4,
    });
  });

  test("changes nothing for the same mode", () => {
    const state = { ...EMPTY, parameters: { spb_s: { fermi_energy: 1 } } };
    expect(carryParameters(state, S, S)).toBe(state);
  });
});
