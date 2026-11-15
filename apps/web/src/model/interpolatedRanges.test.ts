// @vitest-environment node
import { describe, expect, test } from "vitest";

import { flagsOf } from "@/data/InterpolationSwitch";
import { limitedRanges } from "@/model/interpolatedRanges";
import type { InterpolatedQuantities } from "@/session/store";

const result = (
  extra: Partial<NonNullable<InterpolatedQuantities["seebeck"]>> = {},
) => ({
  temperature_k: [50, 400, 750],
  values: [1, 2, 3],
  extrapolated: false,
  range_limited: true,
  measured_points_in_range: 3,
  underdetermined: false,
  ...extra,
});

describe("limitedRanges", () => {
  test("names each quantity the data narrowed, with the range a fit uses", () => {
    const interpolation = {
      enabled: true,
      loading: false,
      values: {
        seebeck: result(),
        resistivity: result({ range_limited: false }),
      },
    };
    expect(limitedRanges(interpolation, ["seebeck", "resistivity"])).toEqual([
      { quantity: "seebeck", minK: 50, maxK: 750 },
    ]);
    // A quantity the mode does not use is left out.
    expect(limitedRanges(interpolation, ["resistivity"])).toEqual([]);
  });

  test("says nothing with interpolation off, or while new values are on their way", () => {
    const values = { seebeck: result() };
    expect(
      limitedRanges({ enabled: false, loading: false, values }, ["seebeck"]),
    ).toEqual([]);
    expect(
      limitedRanges({ enabled: true, loading: true, values }, ["seebeck"]),
    ).toEqual([]);
  });
});

describe("flagsOf", () => {
  test("a refused quantity says why, and a lost request says only that it failed", () => {
    expect(
      flagsOf("seebeck", {
        values: {},
        failed: ["seebeck"],
        failureReasons: { seebeck: "overlap_too_short" },
      }),
    ).toEqual([
      "S: its measured range overlaps the fit range too little to interpolate, so a fit cannot use it.",
    ]);
    expect(flagsOf("seebeck", { values: {}, failed: ["seebeck"] })).toEqual([
      "S: could not be interpolated, so a fit cannot use it.",
    ]);
  });

  test("a narrowed range names the range a fit uses", () => {
    expect(
      flagsOf("seebeck", { values: { seebeck: result() }, failed: [] }),
    ).toEqual([
      "S: the measured range limits interpolation to 50–750 K, and a fit uses only that.",
    ]);
  });

  test("with no measured point in the window, the polynomial alone sets every value", () => {
    const flags = flagsOf("seebeck", {
      values: {
        seebeck: result({ range_limited: false, measured_points_in_range: 0 }),
      },
      failed: [],
    });
    expect(flags).toEqual([
      "S: no measured point lies in the fit range, so every value comes from the polynomial alone, which can be far off between measurements.",
    ]);
  });
});
