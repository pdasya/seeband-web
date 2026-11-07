// @vitest-environment node
import { describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import type { CalcResponse } from "@/api/client";
import {
  chartTabView,
  derivedKind,
  needsMeasuredCurves,
} from "@/model/chartTabs";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import type { Quantity, SessionData } from "@/session/store";

const modes = (MODELS.models as ModelDescription[]).flatMap(
  ({ fit_modes }) => fit_modes,
);

function mode(id: string): FitModeDescription {
  const found = modes.find((candidate) => candidate.id === id);
  if (found === undefined) {
    throw new Error(id);
  }
  return found;
}

const NO_INTERPOLATION = {
  enabled: false,
  loading: false,
  values: {},
  failed: [],
  failure: null,
};

function loaded(...quantities: Quantity[]) {
  const data: Partial<Record<Quantity, SessionData>> = {};
  for (const quantity of quantities) {
    data[quantity] = {
      measurement: {
        temperature_k: [100],
        values: [2e-6],
        points: 1,
        min_temperature_k: 100,
        max_temperature_k: 100,
      },
      source: { kind: "file", name: "a" },
      extrapolated: false,
      text: "",
    } as unknown as SessionData;
  }
  return { data, interpolation: NO_INTERPOLATION, parameters: {} };
}

const answer = (curves: Record<string, (number | null)[]>): CalcResponse => ({
  temperature_k: [100],
  curves,
  known_issues: [],
  rmse: {},
});

describe("what a tab asks for", () => {
  test("derived kinds only where a mode offers them", () => {
    expect(derivedKind("seebeck", mode("dpb_s_rho"))).toBeNull();
    expect(derivedKind("chemical_potential", mode("spb_s"))).toBe(
      "chemical_potential",
    );
    expect(derivedKind("bands", mode("dpb_s"))).toBe("seebeck_by_band");
    expect(derivedKind("bands", mode("spb_s_rho"))).toBeNull();
    expect(derivedKind("bands", undefined)).toBeNull();
  });

  test("the total of S goes with contributions, and only there", () => {
    expect(needsMeasuredCurves("bands", mode("dpb_s"))).toBe(true);
    expect(needsMeasuredCurves("bands", mode("spb_s"))).toBe(false);
    expect(needsMeasuredCurves("chemical_potential", mode("dpb_s"))).toBe(
      false,
    );
    expect(needsMeasuredCurves("seebeck", mode("dpb_s"))).toBe(false);
  });
});

describe("tabs of quantities", () => {
  test("no data has an empty state of its own for R_H", () => {
    const view = chartTabView(
      "hall",
      mode("dpb_s_rho_rh"),
      loaded(),
      null,
      null,
    );

    expect(view.empty?.title).toBe("No R_H(T) data");
    expect(view.curves).toEqual([]);
    expect(
      chartTabView("seebeck", mode("dpb_s"), loaded(), null, null).empty?.title,
    ).toBe("No data for this quantity");
  });

  test("units are those of the axis", () => {
    const measured = answer({
      seebeck_v_per_k: [1e-4],
      resistivity_ohm_m: [2e-5],
      hall_m3_per_c: [3e-9],
    });
    const state = loaded("seebeck", "resistivity", "hall");
    const at = (tab: Quantity) =>
      chartTabView(tab, mode("dpb_s_rho_rh"), state, measured, null);

    expect(at("seebeck").yAxisTitle).toBe("S, µV/K");
    expect(at("seebeck").curves[0]?.values[0]).toBeCloseTo(100);
    expect(at("seebeck").measurements?.values[0]).toBeCloseTo(2);
    expect(at("resistivity").yAxisTitle).toBe("ρ, µΩ·m");
    expect(at("resistivity").curves[0]?.values[0]).toBeCloseTo(20);
    expect(at("hall").yAxisTitle).toBe("R_H, m³/C");
    expect(at("hall").curves[0]?.values[0]).toBe(3e-9);
    expect(at("hall").measurements?.values[0]).toBe(2e-6);
  });

  test("a gap in a curve stays one", () => {
    const view = chartTabView(
      "seebeck",
      mode("dpb_s"),
      loaded("seebeck"),
      answer({ seebeck_v_per_k: [null] }),
      null,
    );

    expect(view.curves[0]?.values).toEqual([null]);
  });

  test("data the mode does not use show as points, and it says so", () => {
    const view = chartTabView(
      "resistivity",
      mode("dpb_s"),
      loaded("resistivity"),
      answer({ seebeck_v_per_k: [1], resistivity_ohm_m: [1] }),
      null,
    );

    expect(view.empty).toBeNull();
    expect(view.curves).toEqual([]);
    expect(view.measurements).not.toBeNull();
    expect(view.note).toContain("not calculated in this fit mode");
  });

  test("interpolated values are apart from the measured", () => {
    const state = {
      ...loaded("resistivity"),
      interpolation: {
        ...NO_INTERPOLATION,
        enabled: true,
        values: {
          resistivity: {
            temperature_k: [100, 120],
            values: [1e-6, null],
            extrapolated: false,
            measured_points_in_range: 1,
            underdetermined: false,
          },
        },
      },
    };

    const view = chartTabView(
      "resistivity",
      mode("dpb_s_rho"),
      state,
      null,
      null,
    );

    expect(view.interpolated?.values[0]).toBeCloseTo(1);
    expect(view.interpolated?.values[1]).toBeNull();
    expect(view.measurements?.temperatureK).toEqual([100]);
  });
});

describe("the chemical potential", () => {
  const derived = answer({ chemical_potential_k: [-90] });

  test("needs no data, and draws in K with no scale", () => {
    const view = chartTabView(
      "chemical_potential",
      mode("spb_s"),
      loaded(),
      null,
      derived,
    );

    expect(view.empty).toBeNull();
    expect(view.yAxisTitle).toBe("μ, K");
    expect(view.curves[0]?.values).toEqual([-90]);
  });

  test("one band has one edge at 0", () => {
    const view = chartTabView(
      "chemical_potential",
      mode("spb_s"),
      loaded(),
      null,
      derived,
    );

    expect(view.referenceLines).toEqual([{ value: 0, label: "band edge" }]);
  });

  test("two bands have E_g from the current value, or its default", () => {
    const at = (band_gap?: number) =>
      chartTabView(
        "chemical_potential",
        mode("dpb_s"),
        {
          ...loaded(),
          parameters: band_gap === undefined ? {} : { dpb_s: { band_gap } },
        },
        null,
        derived,
      ).referenceLines;

    expect(at()).toEqual([
      { value: 0, label: "band 1 top" },
      { value: 1000, label: "band 2 bottom (E_g)" },
    ]);
    expect(at(750)[1]?.value).toBe(750);
  });

  test("a curve of another tab draws nothing", () => {
    const view = chartTabView(
      "chemical_potential",
      mode("dpb_s"),
      loaded(),
      null,
      answer({ seebeck_band_1_v_per_k: [1] }),
    );

    expect(view.curves).toEqual([]);
  });
});

describe("band contributions", () => {
  test("say DPB only in SPB, from the mode's reason", () => {
    const view = chartTabView("bands", mode("spb_s"), loaded(), null, null);

    expect(view.empty?.title).toBe("DPB only");
  });

  test("another reason has a general text", () => {
    const changed = {
      ...mode("dpb_s"),
      curves: mode("dpb_s").curves.map((curve) =>
        curve.kind === "seebeck_by_band"
          ? { ...curve, available: false, reason: "not_provided" }
          : curve,
      ),
    };

    expect(
      chartTabView("bands", changed, loaded(), null, null).empty?.title,
    ).toBe("Not available in this mode");
  });

  test("draw the total and each band, in µV/K", () => {
    const view = chartTabView(
      "bands",
      mode("dpb_s"),
      loaded(),
      answer({ seebeck_v_per_k: [1e-4] }),
      answer({
        seebeck_band_1_v_per_k: [2e-4],
        seebeck_band_2_v_per_k: [-1e-4],
      }),
    );

    expect(view.curves.map(({ label }) => label)).toEqual([
      "Total S",
      "band 1 contribution",
      "band 2 contribution",
    ]);
    expect(view.curves.map(({ dashed }) => dashed === true)).toEqual([
      false,
      true,
      true,
    ]);
    expect(view.curves[1]?.values[0]).toBeCloseTo(200);
    expect(view.curves[2]?.values[0]).toBeCloseTo(-100);
  });
});
