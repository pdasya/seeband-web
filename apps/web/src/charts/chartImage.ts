import { buildFigure, readChartTheme, type FigureInput } from "@/charts/figure";
import { loadPlotly } from "@/charts/loadPlotly";

/**
 * The size a chart prints at, in CSS pixels: half the width of an A4 page within its margins, so
 * that two to a row keep the chart's text near its size on screen. Drawn at twice that, for paper.
 */
export const PRINT_WIDTH_PX = 360;
const PRINT_HEIGHT_PX = 260;
const PRINT_SCALE = 2;
// Plotly leaves its promise open when the browser cannot make the picture, so a report would wait
// for ever without this.
const GIVE_UP_AFTER_MS = 10_000;

function withinTime<T>(work: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error("The chart's picture took too long"));
    }, GIVE_UP_AFTER_MS);
    work.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error instanceof Error ? error : new Error(String(error)));
      },
    );
  });
}

/**
 * A chart as a PNG data URL, from the same figure as on screen. A printed page does not resize a
 * live chart, so a report holds pictures of a known size instead.
 */
export async function chartImage(input: FigureInput): Promise<string> {
  const plotly = await loadPlotly();
  const { data, layout } = buildFigure(
    input,
    readChartTheme(document.documentElement),
  );
  return withinTime(
    plotly.toImage(
      {
        data,
        layout: { ...layout, width: PRINT_WIDTH_PX, height: PRINT_HEIGHT_PX },
      },
      {
        format: "png",
        width: PRINT_WIDTH_PX,
        height: PRINT_HEIGHT_PX,
        scale: PRINT_SCALE,
      },
    ),
  );
}
