// @vitest-environment node
import { describe, expect, test } from "vitest";

import { DEMO as EXAMPLE } from "../../e2e/support/models";

import type { DemoResponse } from "@/api/client";
import { demoEntries, demoText } from "@/data/useDemoData";
import type { Measurement } from "@/session/store";

const DEMO = EXAMPLE as unknown as DemoResponse;

describe("demoText", () => {
  test("holds each row, with numbers that read back exactly", () => {
    const measurement = {
      temperature_k: [50, 75.5],
      values: [1.2345678901234e-5, -3e-7],
    } as Measurement;

    const lines = demoText(measurement).split("\n");

    expect(lines).toHaveLength(2);
    const [temperature, value] = (lines[0] ?? "").split(" ");
    expect(Number(temperature)).toBe(50);
    expect(Number(value)).toBe(1.2345678901234e-5);
    expect(lines[1]).toBe("75.5 -3e-7");
  });
});

describe("demoEntries", () => {
  test("labels each quantity with the demo's own message", () => {
    const entries = demoEntries(DEMO);

    expect(entries.map(([quantity]) => quantity)).toEqual([
      "seebeck",
      "resistivity",
      "hall",
    ]);
    for (const [quantity, entry] of entries) {
      expect(entry.source).toEqual({
        kind: "demo",
        messageKey: DEMO.message_key,
      });
      expect(entry.measurement).toBe(DEMO.measurements[quantity]);
      expect(entry.extrapolated).toBe(false);
      expect(entry.text.split("\n")).toHaveLength(entry.measurement.points);
    }
  });

  test("leaves out what the demo does not hold", () => {
    const measurements = { ...DEMO.measurements };
    delete measurements.hall;
    expect(
      demoEntries({ ...DEMO, measurements }).map(([quantity]) => quantity),
    ).toEqual(["seebeck", "resistivity"]);
  });
});
