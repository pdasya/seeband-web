// @vitest-environment node
import type { Shape } from "plotly.js";
import { describe, expect, test } from "vitest";

import {
  buildFigure,
  type ChartTheme,
  type FigureInput,
} from "@/charts/figure";

const THEME: ChartTheme = {
  background: "bg",
  grid: "grid",
  axis: "axis",
  tickText: "tick",
  titleText: "title",
  outsideRange: "outside",
  measurement: "in",
  measurementOutside: "out",
  curves: { blue: "b", orange: "o", teal: "t" },
  fontFamily: "font",
};
const INPUT: FigureInput = {
  curves: [],
  measurements: null,
  fitRange: null,
  referenceLines: [],
  xAxisTitle: "T, K",
  yAxisTitle: "S",
};

function shapes(input: Partial<FigureInput>): Partial<Shape>[] {
  return buildFigure({ ...INPUT, ...input }, THEME).layout.shapes ?? [];
}

test("small values on the y axis have no SI letter next to the unit", () => {
  expect(buildFigure(INPUT, THEME).layout.yaxis?.exponentformat).toBe("e");
});

test("a band diagram preserves its signed k range without temperature ticks", () => {
  const { layout } = buildFigure({ ...INPUT, xAxisRange: [-0.1, 0.1] }, THEME);
  expect(layout.xaxis?.range).toEqual([-0.1, 0.1]);
  expect(layout.xaxis?.dtick).toBeUndefined();
});

test("uses the decimal comma of the rest of the app", () => {
  expect(buildFigure(INPUT, THEME).layout.separators).toBe(",");
});

describe("curves", () => {
  test("take colours in order, unless one is named, and keep their gaps", () => {
    const curve = {
      temperatureK: [100, 200],
      values: [1, null],
    };

    const { data } = buildFigure(
      {
        ...INPUT,
        curves: [
          { ...curve, id: "a", label: "A" },
          { ...curve, id: "b", label: "B", dashed: true },
          { ...curve, id: "c", label: "C", color: "blue" },
        ],
      },
      THEME,
    );

    expect(data).toMatchObject([
      {
        name: "A",
        y: [1, null],
        connectgaps: false,
        line: { color: "b", dash: "solid" },
      },
      { name: "B", line: { color: "o", dash: "dash" } },
      { name: "C", line: { color: "b" } },
    ]);
  });
});

describe("measurements", () => {
  const measurements = {
    label: "M",
    temperatureK: [100, 200, 300, 400],
    values: [1, 2, 3, 4],
  };

  test("are hollow, and grey outside the fit range, with its ends inside", () => {
    const { data } = buildFigure(
      { ...INPUT, measurements, fitRange: { minK: 200, maxK: 300 } },
      THEME,
    );

    expect(data[0]).toMatchObject({
      mode: "markers",
      cliponaxis: false,
      marker: {
        color: "bg",
        line: { color: ["out", "in", "in", "out"] },
      },
    });
  });

  test("are all dark with no fit range, and come above the curves", () => {
    const { data } = buildFigure(
      {
        ...INPUT,
        measurements,
        curves: [{ id: "a", label: "A", temperatureK: [100], values: [1] }],
      },
      THEME,
    );

    expect(data).toMatchObject([
      { mode: "lines" },
      {
        mode: "markers",
        marker: { line: { color: ["in", "in", "in", "in"] } },
      },
    ]);
  });
});

describe("the x axis", () => {
  const curve = (maxK: number) => ({
    id: "a",
    label: "A",
    temperatureK: [100, maxK],
    values: [1, 2],
  });

  test.each([
    [800, 800],
    [801, 900],
    [760, 800],
  ])("with data up to %d K, it ends at %d K", (dataK, axisK) => {
    const { layout } = buildFigure({ ...INPUT, curves: [curve(dataK)] }, THEME);

    expect(layout.xaxis?.range).toEqual([0, axisK]);
  });

  test("a very long curve does not overflow the stack", () => {
    const temperatureK = Array.from({ length: 300_000 }, (_, i) => i / 500);
    const values = temperatureK.map(() => 1);

    const { layout } = buildFigure(
      {
        ...INPUT,
        curves: [{ id: "a", label: "A", temperatureK, values }],
      },
      THEME,
    );

    expect(layout.xaxis?.range).toEqual([0, 600]);
  });

  test.each([
    ["only negative", [-100, -50]],
    ["not finite", [Number.NaN, Number.POSITIVE_INFINITY]],
  ])("with temperatures %s, it keeps the design's range", (_, temperatureK) => {
    const { layout } = buildFigure(
      {
        ...INPUT,
        curves: [
          {
            id: "a",
            label: "A",
            temperatureK,
            values: temperatureK.map(() => 1),
          },
        ],
      },
      THEME,
    );

    expect(layout.xaxis?.range).toEqual([0, 800]);
  });

  test("with no data, it has the design's range", () => {
    expect(buildFigure(INPUT, THEME).layout.xaxis?.range).toEqual([0, 800]);
  });

  test("a fit range past the data widens it, and a very wide one chooses its own ticks", () => {
    const wide = buildFigure(
      { ...INPUT, fitRange: { minK: 100, maxK: 5000 } },
      THEME,
    );
    const usual = buildFigure(INPUT, THEME);

    expect(wide.layout.xaxis?.range).toEqual([0, 5000]);
    expect(wide.layout.xaxis?.dtick).toBeUndefined();
    expect(usual.layout.xaxis?.dtick).toBe(100);
  });
});

describe("the y axis", () => {
  const axisFor = (values: (number | null)[]) =>
    buildFigure(
      {
        ...INPUT,
        curves: [
          {
            id: "a",
            label: "A",
            temperatureK: values.map((_, index) => index),
            values,
          },
        ],
      },
      THEME,
    ).layout.yaxis;

  test.each([
    ["S in µV/K", [5, 121], [0, 140], 20],
    ["a top on a tick, which gets room above it", [0, 120], [0, 140], 20],
    ["negative values", [-207, -12], [-250, 0], 50],
    ["both signs", [-30, 45], [-40, 60], 20],
    ["one value", [50, 50], [50, 60], 10],
    ["zero alone", [0, 0], [0, 0.2], 0.2],
  ])("with %s", (_, values, range, dtick) => {
    const axis = axisFor(values);

    expect(axis?.range).toEqual(range);
    expect(axis?.dtick).toBe(dtick);
    expect(axis?.tick0).toBe(0);
  });

  test("small values in V/K get round ticks too", () => {
    const axis = axisFor([2e-5, 2.1e-4]);

    expect(axis?.dtick).toBeCloseTo(5e-5, 12);
    expect(axis?.range?.[0]).toBeCloseTo(0, 12);
    expect(axis?.range?.[1]).toBeCloseTo(2.5e-4, 12);
  });

  test("gaps and values that are not finite are ignored", () => {
    expect(axisFor([null, 10, Number.NaN, 100])?.range).toEqual([0, 120]);
  });

  test("with no values, Plotly chooses", () => {
    expect(axisFor([null])?.range).toBeUndefined();
    expect(axisFor([])?.dtick).toBeUndefined();
  });

  test("measurements and reference lines count, and hidden ones do not", () => {
    const { layout } = buildFigure(
      {
        ...INPUT,
        measurements: { label: "M", temperatureK: [100], values: [10] },
        referenceLines: [{ value: 90, label: "E" }],
      },
      THEME,
    );

    expect(layout.yaxis?.range).toEqual([0, 100]);
  });
});

describe("interpolated points", () => {
  const measurements = { label: "M", temperatureK: [100], values: [10] };
  const interpolated = { label: "I", temperatureK: [900], values: [80, null] };

  test("are a series of their own, below the measured points", () => {
    const { data } = buildFigure(
      { ...INPUT, measurements, interpolated },
      THEME,
    );

    expect(data.map(({ name }) => name)).toEqual(["I", "M"]);
    expect(data[0]).toMatchObject({
      mode: "markers",
      marker: { color: THEME.curves.orange },
    });
  });

  test("count towards both axes", () => {
    const { layout } = buildFigure({ ...INPUT, interpolated }, THEME);

    expect(layout.xaxis?.range).toEqual([0, 900]);
    expect(layout.yaxis?.range?.[1]).toBeGreaterThanOrEqual(80);
  });

  test("with none, no series", () => {
    const { data } = buildFigure({ ...INPUT, measurements }, THEME);

    expect(data.map(({ name }) => name)).toEqual(["M"]);
  });
});

describe("the area outside the fit range", () => {
  test("is shaded on both sides, below the data", () => {
    expect(
      shapes({
        fitRange: { minK: 50, maxK: 600 },
        curves: [{ id: "a", label: "A", temperatureK: [800], values: [1] }],
      }),
    ).toMatchObject([
      { type: "rect", layer: "below", x0: 0, x1: 50, fillcolor: "outside" },
      { type: "rect", layer: "below", x0: 600, x1: 800 },
    ]);
  });

  test("is not drawn where there is none, or with no fit range", () => {
    expect(shapes({ fitRange: { minK: 0, maxK: 800 } })).toEqual([]);
    expect(shapes({})).toEqual([]);
  });
});

test("a reference line is dashed across the plot, with its label", () => {
  const { layout } = buildFigure(
    { ...INPUT, referenceLines: [{ value: 900, label: "E_g" }] },
    THEME,
  );

  expect(layout.shapes).toMatchObject([
    { type: "line", xref: "paper", y0: 900, y1: 900, line: { dash: "dash" } },
  ]);
  expect(layout.annotations).toMatchObject([{ y: 900, text: "E_g" }]);
});

test("the figure does not share arrays with its input", () => {
  const temperatureK = [100];
  const { data } = buildFigure(
    {
      ...INPUT,
      curves: [{ id: "a", label: "A", temperatureK, values: [1] }],
    },
    THEME,
  );

  expect((data[0] as { x: number[] }).x).not.toBe(temperatureK);
});
