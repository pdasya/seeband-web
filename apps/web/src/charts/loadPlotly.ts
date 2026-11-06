import type Plotly from "plotly.js";

export type PlotlyModule = typeof Plotly;

let loading: Promise<PlotlyModule> | null = null;

/** Loads Plotly once, on first use, as it is 400 KB compressed and the first screen has no chart. */
export function loadPlotly(): Promise<PlotlyModule> {
  loading ??= import("plotly.js-basic-dist-min").then(
    (module) => module.default,
    (error: unknown) => {
      // A failed request can succeed later, so the next chart tries again.
      loading = null;
      throw error;
    },
  );
  return loading;
}
