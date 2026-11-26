import assert from "node:assert/strict";
import { visibleParameters } from "@/model/parameters";
import {
  calcRequest,
  bandDiagramRequest,
  requestScope,
} from "@/model/liveCurves";
// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import {
  fitInputsKey,
  fitRequest,
  startsOutsideBounds,
} from "@/model/fitRequest";
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
  held: {},
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
      ["A", "B", "F", "G", "band_gap", "fermi_energy", "m_eff"].sort(),
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

  test("holds the parameters held for the mode, and none of another scattering type", () => {
    const answer = fitRequest(
      { ...STATE, held: { dpb_s_rho: ["band_gap", "F"], dpb_s: ["m_eff"] } },
      models,
    );

    expect("request" in answer && answer.request.held).toEqual(["band_gap"]);
  });

  test("leaves held out with none held, so a fit is the desktop's", () => {
    const answer = fitRequest(STATE, models);

    expect(answer).toHaveProperty("request");
    expect("request" in answer && answer.request).not.toHaveProperty("held");
  });

  test("with every fitted parameter held, there is nothing to fit", () => {
    const all = ["m_eff", "band_gap", "fermi_energy", "A", "B"];

    expect(blocked({ held: { dpb_s_rho: all } })).toEqual({
      blocked: { reason: "all_held" },
    });
  });

  test("the order of the clicks does not change the request", () => {
    const one = fitRequest(
      { ...STATE, held: { dpb_s_rho: ["fermi_energy", "band_gap"] } },
      models,
    );
    const other = fitRequest(
      { ...STATE, held: { dpb_s_rho: ["band_gap", "fermi_energy"] } },
      models,
    );
    if (!("request" in one) || !("request" in other)) {
      throw new Error("blocked");
    }

    expect(one.request.held).toEqual(["band_gap", "fermi_energy"]);
    expect(fitInputsKey(one.request)).toBe(fitInputsKey(other.request));
  });

  test("a change of what is held is a change of the fit", () => {
    const free = fitRequest(STATE, models);
    const held = fitRequest(
      { ...STATE, held: { dpb_s_rho: ["band_gap"] } },
      models,
    );
    if (!("request" in free) || !("request" in held)) {
      throw new Error("blocked");
    }

    expect(fitInputsKey(held.request)).not.toBe(fitInputsKey(free.request));
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

  test("data whose unit is in doubt wait for a fix or a confirmation", () => {
    const doubted = {
      ...entry([100]),
      unitDoubts: [{ code: "implausible_magnitude", direction: "above" }],
    } as SessionData;
    const data = { seebeck: entry([100, 900]), resistivity: doubted };

    expect(blocked({ data } as never)).toEqual({
      blocked: { reason: "unit_in_doubt", quantities: ["resistivity"] },
    });
    // Confirmed by the user, the same data fit.
    const confirmed = {
      ...data,
      resistivity: { ...doubted, unitConfirmed: true },
    };
    expect("request" in blocked({ data: confirmed } as never)).toBe(true);
    // A doubt about data the mode does not use stops nothing.
    expect(
      "request" in blocked({ data: { ...STATE.data, hall: doubted } } as never),
    ).toBe(true);
  });

  test("a disabled or unknown mode cannot run", () => {
    const withDisabledMode = models.map((model) => ({
      ...model,
      fit_modes: model.fit_modes.map((mode) =>
        mode.id === "spb_s_rho_rh" ? { ...mode, disabled: true } : mode,
      ),
    }));
    expect(
      fitRequest(
        {
          ...STATE,
          selection: {
            ...STATE.selection,
            model: "spb",
            fitMode: "spb_s_rho_rh",
          },
        },
        withDisabledMode,
      ),
    ).toEqual({ blocked: { reason: "no_mode" } });
    for (const selection of [
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

  const outside = (bounds: object, extra: object = {}) => {
    const answer = withBounds({ dpb_s_rho: { band_gap: bounds } }, extra);
    if (!("request" in answer)) {
      throw new Error("blocked");
    }
    return startsOutsideBounds(answer.request);
  };

  test("name a start outside them, at either end", () => {
    expect(outside({ lower: 1500, upper: 2000 })).toEqual(["band_gap"]);
    expect(outside({ lower: 100, upper: 500 })).toEqual(["band_gap"]);
  });

  test("let a start on them through, as a bound is inside its range", () => {
    expect(outside({ lower: 1000, upper: 2000 })).toEqual([]);
    expect(outside({ lower: 100, upper: 1000 })).toEqual([]);
  });

  test("check the value set, not the default", () => {
    expect(
      outside(
        { lower: 1500, upper: 2000 },
        { parameters: { dpb_s_rho: { band_gap: 1700 } } },
      ),
    ).toEqual([]);
  });

  test("do not check a start with no bounds of the user's", () => {
    const answer = withBounds({}, { parameters: { dpb_s_rho: { m_eff: 6 } } });
    expect("request" in answer && startsOutsideBounds(answer.request)).toEqual(
      [],
    );
  });

  test("a start outside them leaves the same inputs, for a fit that runs", () => {
    const key = (parameters: object) => {
      const answer = withBounds(
        { dpb_s_rho: { m_eff: { lower: 0.5, upper: 3 } } },
        { parameters },
      );
      if (!("request" in answer)) {
        throw new Error("blocked");
      }
      return fitInputsKey(answer.request);
    };
    expect(key({ dpb_s_rho: { m_eff: 4 } })).toBe(
      key({ dpb_s_rho: { m_eff: 1 } }),
    );
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

test("algorithm defaults for older state and separates request identities", () => {
  const verified = fitRequest(STATE, models);
  const legacy = fitRequest(
    {
      ...STATE,
      selection: { ...STATE.selection, algorithm: "legacy-sequential-v1" },
    },
    models,
  );
  if (!("request" in verified) || !("request" in legacy))
    throw new Error("blocked");
  expect(verified.request.algorithm).toBe("verified-sequential-v2");
  expect(legacy.request.algorithm).toBe("legacy-sequential-v1");
  expect(fitInputsKey(verified.request)).not.toBe(fitInputsKey(legacy.request));
});

test("explicit fit, calculation and diagram agree on band identity, SI density and absolute mass", () => {
  const legacy = models.find((model) => model.id === "dpb");
  if (!legacy) throw new Error("Missing DPB fixture");
  const base = legacy.fit_modes.find((mode) => mode.id === "dpb_s_rho");
  if (!base) throw new Error("Missing mode fixture");
  const mass = base.parameters.find((parameter) => parameter.name === "m_eff");
  if (!mass) throw new Error("Missing mass fixture");
  const mode = {
    ...base,
    parameters: [
      ...base.parameters
        .filter((parameter) => parameter.name !== "fermi_energy")
        .map((parameter) => ({
          ...parameter,
          name:
            parameter.name === "m_eff"
              ? "mass_ratio"
              : parameter.name === "band_gap"
                ? "band_offset_k"
                : parameter.name,
        })),
      { ...mass, name: "m1" },
    ],
  };
  const explicitModels = [{ ...legacy, fit_modes: [mode] }];
  const state = {
    ...STATE,
    selection: {
      ...STATE.selection,
      algorithm: "legacy-sequential-v1" as const,
      parameterization: "explicit_density_v1" as const,
      bandConfiguration: "cb_cb" as const,
      netElectronDensityPerM3: 2e24,
    },
    parameters: { dpb_s_rho: { mass_ratio: 2, band_offset_k: -600, m1: 1.7 } },
  };
  const built = fitRequest(state, explicitModels);
  expect("request" in built).toBe(true);
  if (!("request" in built)) return;
  const identity = {
    parameterization: "explicit_density_v1",
    band_configuration: "cb_cb",
    net_electron_density_per_m3: 2e24,
    band_1_degeneracy: 2,
    band_2_degeneracy: 3,
  };
  expect(built.request).toMatchObject(identity);
  expect(built.request.algorithm).toBe("verified-sequential-v2");
  expect(built.request.held).toContain("m1");
  expect(built.request.start).toMatchObject({
    mass_ratio: 2,
    band_offset_k: -600,
    m1: 1.7,
  });
  expect(built.request.start).not.toHaveProperty("fermi_energy");
  for (const parameter of visibleParameters(mode, "acPh").filter(
    (parameter) => parameter.role === "fitted" && parameter.name !== "m1",
  ))
    expect(built.request.bounds).toHaveProperty(parameter.name);
  expect(built.request.bounds).not.toHaveProperty("m1");
  const calc = calcRequest(state, explicitModels);
  if (!calc) throw new Error("Missing calculation request");
  expect(calc).toMatchObject(identity);
  expect(bandDiagramRequest(state, explicitModels)).toMatchObject(identity);
  expect(requestScope({ ...calc, net_electron_density_per_m3: 3e24 })).not.toBe(
    requestScope(calc),
  );
});

test.each(["cb_cb", "vb_vb"] as const)(
  "zero density suspends %s fit and plots",
  (configuration) => {
    const selection = {
      ...STATE.selection,
      parameterization: "explicit_density_v1" as const,
      bandConfiguration: configuration,
      netElectronDensityPerM3: 0,
    };
    const state = { ...STATE, selection };
    expect(fitRequest(state, models)).toEqual({
      blocked: { reason: "invalid_density" },
    });
    expect(calcRequest(state, models)).toBeNull();
    expect(bandDiagramRequest(state, models)).toBeNull();
    const intrinsic = {
      ...state,
      selection: { ...selection, bandConfiguration: "vb_cb" as const },
    };
    expect(calcRequest(intrinsic, models)?.net_electron_density_per_m3).toBe(0);
    expect(
      bandDiagramRequest(intrinsic, models)?.net_electron_density_per_m3,
    ).toBe(0);
  },
);

test("Fermi fits and live curves retain E_F and bounds without a carrier-sign constraint", () => {
  const state = {
    ...STATE,
    selection: {
      ...STATE.selection,
      parameterization: "explicit_fermi_v1" as const,
      bandConfiguration: "vb_cb" as const,
    },
    parameters: { dpb_s_rho: { fermi_energy: -140 } },
    customBounds: { dpb_s_rho: { fermi_energy: { lower: -500, upper: 100 } } },
  };
  const built = fitRequest(state, models);
  if (!("request" in built)) throw new Error("Fermi fit blocked");
  expect(built.request).toMatchObject({
    parameterization: "explicit_fermi_v1",
    start: { fermi_energy: -140 },
    bounds: { fermi_energy: { lower: -500, upper: 100 } },
  });
  expect(built.request).not.toHaveProperty("net_electron_density_per_m3");
  expect(built.request).not.toHaveProperty("carrier_type");
  const calc = calcRequest(state, models);
  if (!calc) throw new Error("Fermi calc blocked");
  expect(calc).toMatchObject({
    parameters: { fermi_energy: -140 },
  });
  expect(bandDiagramRequest(state, models)).toMatchObject({
    parameters: { fermi_energy: -140 },
  });
  expect(requestScope({ ...calc, carrier_type: "n" })).not.toBe(
    requestScope(calc),
  );
});

test("virgin Fermi starts agree across fits, live curves and mode switches while custom bounds stay intact", () => {
  const base = {
    ...STATE,
    selection: {
      ...STATE.selection,
      parameterization: "explicit_fermi_v1" as const,
      bandConfiguration: "vb_cb" as const,
    },
    parameters: {},
    customBounds: { dpb_s_rho: { fermi_energy: { lower: -500, upper: 2000 } } },
  };
  const fit = fitRequest(base, models);
  if (!("request" in fit)) throw new Error("Virgin fit blocked");
  expect(fit.request.start.fermi_energy).toBe(-100);
  expect(fit.request.bounds?.fermi_energy).toEqual({
    lower: -500,
    upper: 2000,
  });
  expect(calcRequest(base, models)?.parameters.fermi_energy).toBe(-100);
  expect(bandDiagramRequest(base, models)?.parameters.fermi_energy).toBe(-100);
  const full = {
    ...base,
    selection: {
      ...base.selection,
      fitMode: "dpb_s_rho_rh",
      bandConfiguration: "cb_cb" as const,
    },
  };
  expect(bandDiagramRequest(full, models)?.parameters.fermi_energy).toBe(100);
  const valence = {
    ...base,
    selection: {
      ...base.selection,
      bandConfiguration: "vb_vb" as const,
    },
  };
  expect(calcRequest(valence, models)?.parameters.fermi_energy).toBe(900);
  expect(base.parameters).toEqual({});
  const manual = { ...base, parameters: { dpb_s_rho: { fermi_energy: -140 } } };
  const request = fitRequest(manual, models);
  if (!("request" in request)) throw new Error("Manual fit blocked");
  expect(request.request.start.fermi_energy).toBe(-140);
  expect(request.request.bounds?.fermi_energy).toEqual({
    lower: -500,
    upper: 2000,
  });
});

test("ionized structural B is sent to fits and live curves without optimizer controls", () => {
  const source = models.find((model) => model.id === "dpb");
  assert(source);
  const s = source.fit_modes.find((mode) => mode.id === "dpb_s");
  assert(s);
  const rho = source.fit_modes.find((mode) => mode.id === "dpb_s_rho");
  assert(rho);
  const b = rho.parameters.find((parameter) => parameter.name === "B");
  assert(b);
  const structural = {
    ...b,
    scattering: ["ionized"],
    role: "fixed" as const,
    fit_bounds: null,
    bounds_editable: false,
  };
  const described = [
    {
      ...source,
      fit_modes: [
        {
          ...s,
          scattering: ["acPh", "ionized"],
          parameter_overrides: { ionized: [structural] },
        },
      ],
    },
  ];
  const state = {
    ...STATE,
    selection: {
      ...STATE.selection,
      fitMode: "dpb_s",
      scattering: "ionized",
      parameterization: "explicit_density_v1" as const,
      bandConfiguration: "vb_cb" as const,
      netElectronDensityPerM3: 1e24,
    },
    parameters: { dpb_s: { B: 9 } },
    customBounds: { dpb_s: { B: { lower: 0.9, upper: 1.1 } } },
    held: { dpb_s: ["B"] },
  };
  const answer = fitRequest(state, described);
  if (!("request" in answer)) throw new Error(answer.blocked.reason);
  expect(answer.request.start.B).toBe(9);
  expect(answer.request.bounds?.B).toBeUndefined();
  expect(answer.request.held ?? []).not.toContain("B");
  expect(calcRequest(state, described)?.parameters.B).toBe(9);
});

test("ionized rho requests use the server B bounds, user bounds, or a hold", () => {
  const source = models.find((model) => model.id === "dpb");
  assert(source);
  const mode = source.fit_modes.find((mode) => mode.id === "dpb_s_rho");
  assert(mode);
  const b = mode.parameters.find((parameter) => parameter.name === "B");
  assert(b);
  const wide = { lower: 0, upper: 10000 };
  const described = [
    {
      ...source,
      fit_modes: [
        {
          ...mode,
          parameter_overrides: { ionized: [{ ...b, fit_bounds: wide }] },
        },
      ],
    },
  ];
  const state = {
    ...STATE,
    selection: {
      ...STATE.selection,
      scattering: "ionized",
      parameterization: "explicit_density_v1" as const,
      bandConfiguration: "vb_cb" as const,
      netElectronDensityPerM3: 1e24,
    },
    parameters: { dpb_s_rho: { B: 9 } },
  };
  const bounds = (customBounds = {}, held = {}) => {
    const answer = fitRequest({ ...state, customBounds, held }, described);
    if (!("request" in answer)) throw new Error(answer.blocked.reason);
    return answer.request;
  };
  expect(bounds().bounds?.B).toEqual(wide);
  expect(
    bounds({ dpb_s_rho: { B: { lower: 2, upper: 20 } } }).bounds?.B,
  ).toEqual({ lower: 2, upper: 20 });
  const held = bounds({}, { dpb_s_rho: ["B"] });
  expect(held.start.B).toBe(9);
  expect(held.held).toContain("B");
  expect(held.bounds?.B).toBeUndefined();
});
