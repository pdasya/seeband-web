import { describe, expect, test } from "vitest";

import type { FitModeDescription } from "@/model/selection";
import { carriedNames, carryParameters } from "@/session/carry";

interface Spec {
  value: number;
  role?: "fitted" | "fixed";
  editable?: boolean;
  maximum?: number;
}

function mode(
  id: string,
  specs: Record<string, number | Spec>,
): FitModeDescription {
  return {
    id,
    parameters: Object.entries(specs).map(([name, spec]) => {
      const {
        value,
        role = "fitted",
        editable = true,
        maximum = 1e6,
      } = typeof spec === "number" ? { value: spec } : spec;
      return {
        name,
        role,
        bounds_editable: editable,
        core_range: { minimum: -1e6, maximum, step: 1, default: value },
      };
    }),
  } as unknown as FitModeDescription;
}

// As SPB: the mass is fixed in S and S + ρ, the modes start from other values, only S + ρ has A,
// and the user cannot bound E_F or A.
const S = mode("spb_s", {
  band_mass: { value: 1.01, role: "fixed" },
  fermi_energy: { value: 100, editable: false },
});
const S_RHO = mode("spb_s_rho", {
  band_mass: { value: -1, role: "fixed" },
  fermi_energy: { value: -100, editable: false },
  A: { value: 4e4, editable: false },
});
// As DPB, whose E_F and A the user can bound, and whose A ends at 10⁶.
const DPB = mode("dpb_s_rho", {
  m_eff: 1.01,
  band_gap: 1000,
  fermi_energy: -100,
  A: 4e4,
});
const DPB_S = mode("dpb_s", { band_gap: 1000, fermi_energy: -100 });

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

  test("leaves a default unset where the new mode has the same one", () => {
    const carried = carryParameters(
      { ...EMPTY, parameters: { dpb_s_rho: { band_gap: 800, A: 5e4 } } },
      DPB_S,
      DPB,
    );

    // An automatic guess takes an unset value for a default, and fills it.
    expect(carried.parameters.dpb_s_rho).toEqual({ A: 5e4 });
  });

  test("takes bounds and holds along between modes that let the user set them", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        parameters: { dpb_s_rho: { band_gap: 800, A: 5e4 } },
        customBounds: {
          dpb_s_rho: {
            band_gap: { lower: 500, upper: 900 },
            A: { lower: 1, upper: 9e4 },
          },
        },
        held: { dpb_s_rho: ["band_gap", "A"] },
        guessedParameters: { dpb_s_rho: { band_gap: 800 } },
      },
      DPB,
      DPB_S,
    );

    expect(carried.parameters.dpb_s).toEqual({ band_gap: 800 });
    expect(carried.customBounds.dpb_s).toEqual({
      band_gap: { lower: 500, upper: 900 },
    });
    expect(carried.held.dpb_s).toEqual(["band_gap"]);
    expect(carried.guessedParameters.dpb_s).toEqual({ band_gap: 800 });
  });

  test("drops the new mode's bounds and holds of a shared parameter the old one had not", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        customBounds: { dpb_s: { band_gap: { lower: 0, upper: 1 } } },
        held: { dpb_s: ["band_gap"] },
        guessedParameters: { dpb_s: { band_gap: 1 } },
      },
      DPB,
      DPB_S,
    );

    expect(carried.customBounds.dpb_s).toEqual({});
    expect(carried.held.dpb_s).toEqual([]);
    expect(carried.guessedParameters.dpb_s).toEqual({});
  });

  test("carries no bounds where the new mode does not let the user set them", () => {
    const carried = carryParameters(
      {
        ...EMPTY,
        parameters: { dpb_s_rho: { fermi_energy: 300 } },
        customBounds: {
          dpb_s_rho: { fermi_energy: { lower: 0, upper: 500 } },
        },
        held: { dpb_s_rho: ["fermi_energy"] },
      },
      DPB,
      S_RHO,
    );

    expect(carried.parameters.spb_s_rho).toMatchObject({ fermi_energy: 300 });
    expect(carried.customBounds.spb_s_rho).toBeUndefined();
    // E_F is fitted in SPB S + ρ, so its hold follows.
    expect(carried.held.spb_s_rho).toEqual(["fermi_energy"]);
  });

  test("holds no parameter the new mode does not fit", () => {
    const S_RHO_RH = mode("spb_s_rho_rh", { band_mass: 1, fermi_energy: 100 });
    const carried = carryParameters(
      { ...EMPTY, held: { spb_s_rho_rh: ["band_mass"] } },
      S_RHO_RH,
      S,
    );

    expect(carried.held.spb_s ?? []).toEqual([]);
  });

  test("leaves behind a value outside the new mode's range", () => {
    const carried = carryParameters(
      { ...EMPTY, parameters: { spb_s_rho_rh: { A: 3e6, fermi_energy: 50 } } },
      mode("spb_s_rho_rh", {
        fermi_energy: 100,
        A: { value: 4e4, maximum: 1e7 },
      }),
      DPB,
    );

    expect(carried.parameters.dpb_s_rho).toEqual({ fermi_energy: 50 });
  });

  test("keeps every object when nothing changes, so a recorded guess still holds", () => {
    const state = {
      ...EMPTY,
      parameters: {
        dpb_s: { band_gap: 800, fermi_energy: -50 },
        dpb_s_rho: { band_gap: 800, fermi_energy: -50, A: 5e4 },
      },
      guessedParameters: {
        dpb_s: { band_gap: 800, fermi_energy: -50 },
        dpb_s_rho: { band_gap: 800, fermi_energy: -50 },
      },
    };
    const carried = carryParameters(state, DPB_S, DPB);

    expect(carried.parameters).toBe(state.parameters);
    expect(carried.customBounds).toBe(state.customBounds);
    expect(carried.held).toBe(state.held);
    expect(carried.guessedParameters).toBe(state.guessedParameters);
  });

  test("changes nothing for the same mode", () => {
    const state = { ...EMPTY, parameters: { spb_s: { fermi_energy: 1 } } };
    expect(carryParameters(state, S, S)).toBe(state);
  });
});

describe("carriedNames", () => {
  test("names what a change of model takes along", () => {
    expect(carriedNames(EMPTY, S_RHO, DPB)).toEqual(["fermi_energy", "A"]);
    expect(carriedNames(EMPTY, S, S)).toEqual([]);
  });
});

test("converted mixed sessions retain the archived transport controls of each mode", () => {
  const rho = mode("dpb_s_rho", { band_gap: 1000, A: 100, B: 1, C: 1, D: 1 });
  const hall = { ...rho, id: "dpb_s_rho_rh" };
  const state = {
    ...EMPTY,
    selection: {
      model: "dpb",
      fitMode: "dpb_s_rho",
      band1Degeneracy: 1,
      band2Degeneracy: 1,
      minTemperatureK: 100,
      maxTemperatureK: 800,
      legacySource: "archived",
      parameterization: "explicit_density_v1" as const,
      scattering: "acPhDis",
    },
    parameters: {
      dpb_s_rho: { band_gap: 900, A: 200, B: 2, C: 3, D: 4 },
      dpb_s_rho_rh: { A: 500, B: 5, C: 6, D: 7 },
    },
    customBounds: { dpb_s_rho_rh: { C: { lower: 5, upper: 9 } } },
    held: { dpb_s_rho_rh: ["C"] },
  };
  const next = carryParameters(state, rho, hall);
  expect(next.parameters.dpb_s_rho_rh).toEqual({
    band_gap: 900,
    A: 500,
    B: 5,
    C: 6,
    D: 7,
  });
  expect(next.customBounds.dpb_s_rho_rh?.C).toEqual({ lower: 5, upper: 9 });
  expect(next.held.dpb_s_rho_rh).toEqual(["C"]);
});
