// @vitest-environment node
import { describe, expect, test } from "vitest";

import { temperatureMismatches } from "@/data/temperatureRanges";

function range(min: number, max: number) {
  return { min_temperature_k: min, max_temperature_k: max };
}

describe("temperatureMismatches", () => {
  test("finds a file in °C read as K beside one in K, and names the lower", () => {
    // 27–527 °C is 300.15–800.15 K.
    expect(
      temperatureMismatches({
        seebeck: range(300, 800),
        resistivity: range(27, 527),
      }),
    ).toEqual([{ lower: "resistivity", higher: "seebeck" }]);
  });

  test("allows set points a few kelvin apart", () => {
    expect(
      temperatureMismatches({ seebeck: range(30, 520), hall: range(300, 800) }),
    ).toEqual([{ lower: "seebeck", higher: "hall" }]);
  });

  test("leaves runs that only meet alone, such as Hall to 300 K beside S from 300 K", () => {
    // 298 K and 273 K apart at the two ends.
    expect(
      temperatureMismatches({ seebeck: range(300, 573), hall: range(2, 300) }),
    ).toEqual([]);
    expect(
      temperatureMismatches({ seebeck: range(300, 580), hall: range(10, 300) }),
    ).toEqual([]);
  });

  test("leaves ranges with nothing in common alone, as runs can cover them on purpose", () => {
    expect(
      temperatureMismatches({ seebeck: range(300, 800), hall: range(10, 250) }),
    ).toEqual([]);
    expect(
      temperatureMismatches({ seebeck: range(301, 400), hall: range(10, 300) }),
    ).toEqual([]);
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

  test("counts a shift only within 10 K of 273.15 K at each end", () => {
    expect(
      temperatureMismatches({ seebeck: range(300, 800), hall: range(36, 536) }),
    ).toEqual([{ lower: "hall", higher: "seebeck" }]);
    expect(
      temperatureMismatches({ seebeck: range(300, 800), hall: range(16, 516) }),
    ).toEqual([]);
  });

  test("needs two files", () => {
    expect(temperatureMismatches({ seebeck: range(27, 527) })).toEqual([]);
    expect(temperatureMismatches({})).toEqual([]);
  });
});
