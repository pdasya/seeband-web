// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import type { CalcRequest } from "@/api/client";
import {
  bandDiagramRequest,
  bandDiagramScope,
  calcRequest,
  requestScope,
  rmseGaps,
} from "@/model/liveCurves";
import type { ModelDescription } from "@/model/selection";
import type { SessionData } from "@/session/store";

const models = MODELS.models as ModelDescription[];

const REQUEST: CalcRequest = {
  model: "dpb",
  fit_mode: "dpb_s_rho",
  scattering: "acPh",
  parameters: { m_eff: 1 },
  min_temperature_k: 50,
  max_temperature_k: 800,
};

describe("requestScope", () => {
  test("is the same for other values of one curve", () => {
    const scope = requestScope(REQUEST);

    expect(requestScope({ ...REQUEST, parameters: { m_eff: 2 } })).toBe(scope);
    expect(requestScope({ ...REQUEST, min_temperature_k: 60 })).toBe(scope);
    expect(requestScope({ ...REQUEST, band_2_degeneracy: 2 })).toBe(scope);
    expect(
      requestScope({
        ...REQUEST,
        measurements: { seebeck: { temperature_k: [100], values: [1] } },
      }),
    ).toBe(scope);
  });

  test("differs for another curve", () => {
    const scope = requestScope(REQUEST);

    for (const other of [
      { model: "spb" },
      { fit_mode: "dpb_s" },
      { scattering: "dis" },
      { scattering: null },
      { kind: "chemical_potential" as const },
    ]) {
      expect(requestScope({ ...REQUEST, ...other })).not.toBe(scope);
    }
  });

  test("the default kind is the measured one", () => {
    expect(requestScope({ ...REQUEST, kind: "measured" })).toBe(
      requestScope(REQUEST),
    );
  });
});

const STATE = {
  selection: {
    model: "dpb",
    fitMode: "dpb_s_rho",
    scattering: "acPh",
    band1Degeneracy: 1,
    band2Degeneracy: 1,
    minTemperatureK: 50,
    maxTemperatureK: 800,
  },
  parameters: {},
  data: {},
  interpolation: {
    enabled: false,
    loading: false,
    values: {},
    failed: [],
    failure: null,
  },
};

const seebeck = {
  measurement: {
    temperature_k: [100],
    values: [1e-4],
    points: 1,
    min_temperature_k: 100,
    max_temperature_k: 100,
  },
  extrapolated: false,
} as unknown as SessionData;

describe("rmseGaps", () => {
  test("says whether data of this mode are loaded", () => {
    expect(rmseGaps(STATE, models).hasData).toBe(false);
    expect(rmseGaps({ ...STATE, data: { seebeck } }, models).hasData).toBe(
      true,
    );
    expect(
      rmseGaps({ ...STATE, data: { hall: seebeck } }, models).hasData,
    ).toBe(false);
  });
});

describe("calcRequest", () => {
  test("asks with no data only when told to", () => {
    expect(calcRequest(STATE, models)).toBeNull();
    expect(calcRequest(STATE, models, true)?.fit_mode).toBe("dpb_s_rho");
  });
});

describe("bandDiagramRequest", () => {
  test("holds the mode's values and degeneracies, and needs no data", () => {
    const request = bandDiagramRequest(
      {
        ...STATE,
        data: {},
        parameters: { dpb_s_rho: { band_gap: 500 } },
        selection: {
          ...STATE.selection,
          band1Degeneracy: 2,
          band2Degeneracy: 3,
        },
      },
      models,
    );

    expect(request).toMatchObject({
      model: "dpb",
      fit_mode: "dpb_s_rho",
      band_1_degeneracy: 2,
      band_2_degeneracy: 3,
    });
    expect(request?.parameters.band_gap).toBe(500);
    expect(request?.parameters.m_eff).toBe(1.01);
  });

  test("is null with no mode, or a disabled one", () => {
    expect(bandDiagramRequest(STATE, undefined)).toBeNull();
    expect(
      bandDiagramRequest(
        {
          ...STATE,
          selection: {
            ...STATE.selection,
            model: "spb",
            fitMode: "spb_s_rho_rh",
          },
        },
        models.map((model) => ({
          ...model,
          fit_modes: model.fit_modes.map((mode) =>
            mode.id === "spb_s_rho_rh" ? { ...mode, disabled: true } : mode,
          ),
        })),
      ),
    ).toBeNull();
  });
});

describe("bandDiagramScope", () => {
  test("follows the model and mode, not the values", () => {
    const base = {
      model: "dpb",
      fit_mode: "dpb_s",
      parameters: { m_eff: 1 },
    };
    expect(bandDiagramScope({ ...base, parameters: { m_eff: 2 } })).toBe(
      bandDiagramScope(base),
    );
    expect(bandDiagramScope({ ...base, band_2_degeneracy: 2 })).toBe(
      bandDiagramScope(base),
    );
    expect(bandDiagramScope({ ...base, fit_mode: "dpb_s_rho" })).not.toBe(
      bandDiagramScope(base),
    );
    expect(bandDiagramScope({ ...base, model: "spb" })).not.toBe(
      bandDiagramScope(base),
    );
  });
});
