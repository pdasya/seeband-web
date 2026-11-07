// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import { fitInputsKey, fitRequest } from "@/model/fitRequest";
import type { ModelDescription } from "@/model/selection";
import type { SessionData } from "@/session/store";

const models = MODELS.models as ModelDescription[];

const entry = (temperature_k: number[], extrapolated = false) =>
  ({
    measurement: {
      temperature_k,
      values: temperature_k.map(() => 1e-4),
      points: temperature_k.length,
    },
    extrapolated,
  }) as unknown as SessionData;

const STATE = {
  selection: {
    model: "dpb",
    fitMode: "dpb_s_rho",
    scattering: "acPh",
    band1Degeneracy: 2,
    band2Degeneracy: 3,
    minTemperatureK: 50,
    maxTemperatureK: 800,
  },
  parameters: {},
  customBounds: {},
  data: { seebeck: entry([100, 900]), resistivity: entry([100]) },
  interpolation: {
    enabled: false,
    loading: false,
    values: {},
    failed: [],
    failure: null,
  },
};

const blocked = (state: Partial<typeof STATE> & object) =>
  fitRequest({ ...STATE, ...state } as typeof STATE, models);

describe("fitRequest", () => {
  test("holds all of a mode's data, every parameter and the degeneracies", () => {
    const answer = fitRequest(STATE, models);
    if (!("request" in answer)) {
      throw new Error("blocked");
    }

    expect(answer.request).toMatchObject({
      model: "dpb",
      fit_mode: "dpb_s_rho",
      scattering: "acPh",
      min_temperature_k: 50,
      max_temperature_k: 800,
      band_1_degeneracy: 2,
      band_2_degeneracy: 3,
      extrapolated: false,
    });
    expect(Object.keys(answer.request.start).sort()).toEqual(
      [
        "A",
        "B",
        "C",
        "D",
        "F",
        "G",
        "band_gap",
        "fermi_energy",
        "m_eff",
      ].sort(),
    );
    expect(answer.request.measurements.seebeck?.temperature_k).toEqual([
      100, 900,
    ]);
    expect(answer.request).not.toHaveProperty("bounds");
  });

  test("starts from the values set", () => {
    const answer = fitRequest(
      { ...STATE, parameters: { dpb_s_rho: { m_eff: 2 } } },
      models,
    );

    expect("request" in answer && answer.request.start.m_eff).toBe(2);
  });

  test("says that interpolated values are extrapolated", () => {
    const answer = fitRequest(
      {
        ...STATE,
        interpolation: {
          ...STATE.interpolation,
          enabled: true,
          values: {
            seebeck: {
              temperature_k: [100],
              values: [1],
              extrapolated: true,
            },
            resistivity: {
              temperature_k: [100],
              values: [1],
              extrapolated: false,
            },
          } as never,
        },
      },
      models,
    );

    expect("request" in answer && answer.request.extrapolated).toBe(true);
    expect("request" in answer && answer.request.measurements.seebeck).toEqual({
      temperature_k: [100],
      values: [1],
    });
  });

  test("names what is missing", () => {
    expect(blocked({ data: { seebeck: entry([100]) } as never })).toEqual({
      blocked: { reason: "missing_data", quantities: ["resistivity"] },
    });
  });

  test("a disabled or unknown mode cannot run", () => {
    for (const selection of [
      { ...STATE.selection, model: "spb", fitMode: "spb_s_rho_rh" },
      { ...STATE.selection, fitMode: "nope" },
      { ...STATE.selection, minTemperatureK: null },
    ]) {
      expect(blocked({ selection: selection as never })).toEqual({
        blocked: { reason: "no_mode" },
      });
    }
  });

  test("names a quantity with no points in the range", () => {
    expect(
      blocked({
        data: { seebeck: entry([100]), resistivity: entry([900]) } as never,
      }),
    ).toEqual({
      blocked: { reason: "no_points_in_range", quantities: ["resistivity"] },
    });
  });

  test("waits for interpolated values, and names those that failed", () => {
    expect(
      blocked({
        interpolation: {
          ...STATE.interpolation,
          enabled: true,
          loading: true,
        } as never,
      }),
    ).toEqual({ blocked: { reason: "interpolating" } });
    expect(
      blocked({
        interpolation: {
          ...STATE.interpolation,
          enabled: true,
          values: {
            seebeck: { temperature_k: [100], values: [1], extrapolated: false },
          },
        } as never,
      }),
    ).toEqual({
      blocked: { reason: "not_interpolated", quantities: ["resistivity"] },
    });
  });
});

describe("bounds of the user's", () => {
  const withBounds = (
    customBounds: Record<string, Record<string, object>>,
    extra: object = {},
  ) => fitRequest({ ...STATE, customBounds, ...extra } as never, models);
  const GAP = { band_gap: { lower: 500, upper: 1500 } };

  test("are left out with none, and sent as they are with some", () => {
    const none = fitRequest(STATE, models);
    expect("request" in none && "bounds" in none.request).toBe(false);

    const answer = withBounds({ dpb_s_rho: GAP });
    expect("request" in answer && answer.request.bounds).toEqual(GAP);
  });

  test("of another mode do not go with this one", () => {
    const answer = withBounds({ dpb_s: GAP });
    expect("request" in answer && "bounds" in answer.request).toBe(false);
  });

  test("of another scattering neither go nor stop it", () => {
    const answer = withBounds({
      dpb_s_rho: { G: { lower: 1.5, upper: 2 } },
    });
    expect("request" in answer && "bounds" in answer.request).toBe(false);
  });

  test("stop a fit from a start outside them, at either end, and name it", () => {
    const outside = {
      blocked: { reason: "start_outside_bounds", parameters: ["band_gap"] },
    };
    expect(
      withBounds({ dpb_s_rho: { band_gap: { lower: 1500, upper: 2000 } } }),
    ).toEqual(outside);
    expect(
      withBounds({ dpb_s_rho: { band_gap: { lower: 100, upper: 500 } } }),
    ).toEqual(outside);
  });

  test("let a start on them through, as a bound is inside its range", () => {
    for (const bounds of [
      { lower: 1000, upper: 2000 },
      { lower: 100, upper: 1000 },
    ]) {
      expect(withBounds({ dpb_s_rho: { band_gap: bounds } })).toHaveProperty(
        "request",
      );
    }
  });

  test("check the value set, not the default", () => {
    expect(
      withBounds(
        { dpb_s_rho: { band_gap: { lower: 1500, upper: 2000 } } },
        { parameters: { dpb_s_rho: { band_gap: 1700 } } },
      ),
    ).toHaveProperty("request");
  });
});

describe("fitInputsKey", () => {
  const key = (state: typeof STATE) => {
    const answer = fitRequest(state, models);
    if (!("request" in answer)) {
      throw new Error("blocked");
    }
    return fitInputsKey(answer.request);
  };

  test("follows bounds, as a fit would use them", () => {
    expect(
      key({
        ...STATE,
        customBounds: {
          dpb_s_rho: { band_gap: { lower: 500, upper: 1500 } },
        },
      } as never),
    ).not.toBe(key(STATE));
  });

  test("does not follow the start values, which a fit itself moves", () => {
    expect(
      key({ ...STATE, parameters: { dpb_s_rho: { m_eff: 2 } } } as never),
    ).toBe(key(STATE));
  });

  test("follows everything else", () => {
    for (const selection of [
      { ...STATE.selection, scattering: "dis" },
      { ...STATE.selection, maxTemperatureK: 700 },
      { ...STATE.selection, band1Degeneracy: 5 },
      { ...STATE.selection, fitMode: "dpb_s_rho_rh" },
    ]) {
      const data =
        selection.fitMode === "dpb_s_rho_rh"
          ? { ...STATE.data, hall: entry([100]) }
          : STATE.data;
      expect(key({ ...STATE, selection, data } as never)).not.toBe(key(STATE));
    }
    expect(
      key({
        ...STATE,
        data: { ...STATE.data, seebeck: entry([200]) },
      } as never),
    ).not.toBe(key(STATE));
  });
});
