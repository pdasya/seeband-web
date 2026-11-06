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
