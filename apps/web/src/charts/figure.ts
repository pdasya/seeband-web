import type { Config, Data, Layout, Shape } from "plotly.js";

export type CurveColor = "blue" | "orange" | "teal";

/** Values come from the server, and null marks one that is not finite, which leaves a gap. */
export interface ChartCurve {
  id: string;
  label: string;
  temperatureK: readonly number[];
  values: readonly (number | null)[];
  color?: CurveColor;
  dashed?: boolean;
}

export interface ChartMeasurements {
  label: string;
  temperatureK: readonly number[];
  values: readonly (number | null)[];
}

export interface ChartFitRange {
  minK: number;
  maxK: number;
}

export interface ReferenceLine {
  value: number;
  label: string;
}

export interface FigureInput {
  curves: readonly ChartCurve[];
  measurements: ChartMeasurements | null;
  fitRange: ChartFitRange | null;
  referenceLines: readonly ReferenceLine[];
  xAxisTitle: string;
  yAxisTitle: string;
}

/** Colours and fonts from the tokens, as Plotly draws with values rather than CSS variables. */
export interface ChartTheme {
  background: string;
  grid: string;
  axis: string;
  tickText: string;
  titleText: string;
  outsideRange: string;
  measurement: string;
  measurementOutside: string;
  curves: Record<CurveColor, string>;
  fontFamily: string;
}

const CURVE_COLORS: readonly CurveColor[] = ["blue", "orange", "teal"];
const AXIS_STEP_K = 100;
const DEFAULT_MAX_K = 800;
// Past this, ticks each 100 K would crowd together, so Plotly chooses them.
const MAX_TICKED_K = 1200;
// Taller than the design's 340 px, at the maintainer's request, to read S more easily.
export const CHART_HEIGHT_PX = 480;

export function readChartTheme(root: Element): ChartTheme {
  const styles = getComputedStyle(root);
  const token = (name: string) => styles.getPropertyValue(name).trim();
  return {
    background: token("--background"),
    grid: token("--color-zinc-200"),
    axis: token("--color-zinc-400"),
    tickText: token("--color-zinc-500"),
    titleText: token("--color-zinc-600"),
    outsideRange: token("--color-zinc-100"),
    measurement: token("--color-zinc-950"),
    measurementOutside: token("--color-zinc-400"),
    curves: {
      blue: token("--accent-blue"),
      orange: token("--accent-orange"),
      teal: token("--accent-teal"),
    },
    fontFamily: token("--font-family-sans"),
  };
}

export function curveColor(curve: ChartCurve, index: number): CurveColor {
  return curve.color ?? CURVE_COLORS[index % CURVE_COLORS.length] ?? "blue";
}

function axisMaxK(input: FigureInput): number {
  let maxK = 0;
  const include = (temperatures: readonly number[]) => {
    // A loop, as spreading a very long array into `Math.max` overflows the stack.
    for (const temperatureK of temperatures) {
      if (Number.isFinite(temperatureK) && temperatureK > maxK) {
        maxK = temperatureK;
      }
    }
  };
  for (const curve of input.curves) {
    include(curve.temperatureK);
  }
  include(input.measurements?.temperatureK ?? []);
  include(input.fitRange === null ? [] : [input.fitRange.maxK]);
  return maxK > 0 ? Math.ceil(maxK / AXIS_STEP_K) * AXIS_STEP_K : DEFAULT_MAX_K;
}

function outsideRangeShapes(
  fitRange: ChartFitRange,
  maxK: number,
  theme: ChartTheme,
): Partial<Shape>[] {
  const spans: [number, number][] = [
    [0, Math.min(fitRange.minK, maxK)],
    [Math.min(fitRange.maxK, maxK), maxK],
  ];
  return spans
    .filter(([from, to]) => to > from)
    .map(([from, to]) => ({
      type: "rect",
      layer: "below",
      xref: "x",
      yref: "paper",
      x0: from,
      x1: to,
      y0: 0,
      y1: 1,
      fillcolor: theme.outsideRange,
      line: { width: 0 },
    }));
}

function isInside(temperatureK: number, fitRange: ChartFitRange | null) {
  return (
    fitRange === null ||
    (temperatureK >= fitRange.minK && temperatureK <= fitRange.maxK)
  );
}

/** Turns what a chart shows into Plotly's terms. It calculates nothing about the physics. */
export function buildFigure(
  input: FigureInput,
  theme: ChartTheme,
): { data: Data[]; layout: Partial<Layout> } {
  const { measurements, fitRange } = input;
  const maxK = axisMaxK(input);

  const lines: Data[] = input.curves.map((curve, index) => ({
    type: "scatter",
    mode: "lines",
    name: curve.label,
    x: [...curve.temperatureK],
    y: [...curve.values],
    connectgaps: false,
    line: {
      color: theme.curves[curveColor(curve, index)],
      width: 2,
      dash: curve.dashed === true ? "dash" : "solid",
    },
  }));
  const points: Data[] =
    measurements === null
      ? []
      : [
          {
            type: "scatter",
            mode: "markers",
            // A point at the end of the axis would otherwise be cut in half.
            cliponaxis: false,
            name: measurements.label,
            x: [...measurements.temperatureK],
            y: [...measurements.values],
            marker: {
              size: 6.4,
              color: theme.background,
              line: {
                width: 1.5,
                color: measurements.temperatureK.map((temperatureK) =>
                  isInside(temperatureK, fitRange)
                    ? theme.measurement
                    : theme.measurementOutside,
                ),
              },
            },
          },
        ];

  const tickFont = {
    size: 11,
    color: theme.tickText,
    family: theme.fontFamily,
  };
  const titleFont = {
    size: 12,
    color: theme.titleText,
    family: theme.fontFamily,
  };
  const layout: Partial<Layout> = {
    height: CHART_HEIGHT_PX,
    autosize: true,
    margin: { t: 16, r: 16, b: 52, l: 56 },
    paper_bgcolor: theme.background,
    plot_bgcolor: theme.background,
    font: { family: theme.fontFamily },
    showlegend: false,
    hovermode: "closest",
    xaxis: {
      title: { text: input.xAxisTitle, font: titleFont },
      range: [0, maxK],
      showgrid: false,
      zeroline: false,
      showline: true,
      linecolor: theme.axis,
      ticks: "outside",
      ticklen: 5,
      tickcolor: theme.axis,
      tickfont: tickFont,
      ...(maxK <= MAX_TICKED_K ? { dtick: AXIS_STEP_K } : {}),
    },
    yaxis: {
      title: { text: input.yAxisTitle, font: titleFont },
      gridcolor: theme.grid,
      zeroline: false,
      tickfont: tickFont,
      automargin: true,
    },
    shapes: [
      ...(fitRange === null ? [] : outsideRangeShapes(fitRange, maxK, theme)),
      ...input.referenceLines.map((line): Partial<Shape> => ({
        type: "line",
        layer: "above",
        xref: "paper",
        yref: "y",
        x0: 0,
        x1: 1,
        y0: line.value,
        y1: line.value,
        line: { color: theme.axis, width: 1, dash: "dash" },
      })),
    ],
    annotations: input.referenceLines.map((line) => ({
      xref: "paper",
      yref: "y",
      x: 1,
      y: line.value,
      xanchor: "right",
      yanchor: "bottom",
      showarrow: false,
      text: line.label,
      font: { size: 11, color: theme.titleText, family: theme.fontFamily },
    })),
  };
  return { data: [...lines, ...points], layout };
}

export const PLOT_CONFIG: Partial<Config> = {
  displayModeBar: false,
  responsive: true,
  scrollZoom: false,
};
