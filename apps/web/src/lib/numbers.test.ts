// @vitest-environment node
import { describe, expect, test } from "vitest";

import { formatNumber, parseNumber, withDecimalComma } from "@/lib/numbers";

describe("formatNumber", () => {
  test("uses a comma, with no grouping", () => {
    expect(formatNumber(1.01)).toBe("1,01");
    expect(formatNumber(-0.5)).toBe("-0,5");
    expect(formatNumber(1000000)).toBe("1000000");
    expect(formatNumber(1.5e-7)).toBe("1,5e-7");
  });

  test("takes text that is already formatted", () => {
    expect(withDecimalComma("1.500e-5")).toBe("1,500e-5");
  });
});

describe("parseNumber", () => {
  test.each([
    ["1,5", 1.5],
    ["1.5", 1.5],
    [" -2,5 ", -2.5],
    ["−2,5", -2.5],
    ["+3", 3],
    [",5", 0.5],
    ["5,", 5],
    ["1,5e3", 1500],
    ["1e-3", 0.001],
    ["0", 0],
  ])("reads %s", (text, expected) => {
    expect(parseNumber(text)).toBe(expected);
  });

  test.each([
    "",
    " ",
    "abc",
    "1,2,3",
    "1,234.5",
    "1 000",
    "0x10",
    "Infinity",
    "NaN",
    "1e400",
    "-",
    ",",
  ])("refuses %j", (text) => {
    expect(parseNumber(text)).toBeNull();
  });
});
