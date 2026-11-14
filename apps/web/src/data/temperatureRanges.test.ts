// @vitest-environment node
import { describe, expect, test } from "vitest";

import { temperatureMismatches } from "@/data/temperatureRanges";

function range(min: number, max: number) {
  return { min_temperature_k: min, max_temperature_k: max };
}

describe("temperatureMismatches", () => {
  test("finds a file in °C read as K beside one in K", () => {
    // 27–527 °C is 300.15–800.15 K.
    expect(
      temperatureMismatches({
        seebeck: range(300, 800),
        resistivity: range(27, 527),
      }),
    ).toEqual([{ kind: "shifted", first: "seebeck", second: "resistivity" }]);
  });

  test("allows set points a few kelvin apart", () => {
    expect(
      temperatureMismatches({ seebeck: range(30, 520), hall: range(300, 800) }),
    ).toEqual([{ kind: "shifted", first: "seebeck", second: "hall" }]);
  });

  test("finds ranges with no T in common", () => {
    expect(
      temperatureMismatches({ seebeck: range(300, 800), hall: range(10, 250) }),
    ).toEqual([{ kind: "apart", first: "seebeck", second: "hall" }]);
  });

  test("leaves overlapping ranges alone, also of different lengths", () => {
    expect(
      temperatureMismatches({
        seebeck: range(300, 800),
        resistivity: range(25, 750),
        hall: range(10, 300),
      }),
    ).toEqual([]);
  });

  test("does not take a range shifted at one end only for °C", () => {
    // Hall measured from 10 K, S from 300 K: 290 K apart at the low end, 500 K at the high.
    expect(
      temperatureMismatches({ seebeck: range(300, 800), hall: range(10, 300) }),
    ).toEqual([]);
  });

  test("needs two files", () => {
    expect(temperatureMismatches({ seebeck: range(27, 527) })).toEqual([]);
    expect(temperatureMismatches({})).toEqual([]);
  });
});
