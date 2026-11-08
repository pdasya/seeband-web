import { ChartLineIcon } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import {
  buildFigure,
  CHART_HEIGHT_PX,
  curveColor,
  PLOT_CONFIG,
  readChartTheme,
  type ChartCurve,
  type ChartFitRange,
  type ChartMeasurements,
  type ReferenceLine,
} from "@/charts/figure";
import { loadPlotly, type PlotlyModule } from "@/charts/loadPlotly";

const NO_REFERENCE_LINES: readonly ReferenceLine[] = [];

interface EmptyState {
  title: string;
  text: string;
}

export interface TransportChartProps {
  /** When set, this shows instead of a chart, and Plotly does not load. */
  empty?: EmptyState | null;
  curves: readonly ChartCurve[];
  measurements?: ChartMeasurements | null;
  /** Shown and hidden together with the measurements, as they stand for them. */
  interpolated?: ChartMeasurements | null;
  fitRange?: ChartFitRange | null;
  referenceLines?: readonly ReferenceLine[];
  xAxisTitle: string;
  xAxisSpan?: readonly [number, number] | null | undefined;
  xAxisUnitless?: boolean | undefined;
  yAxisTitle: string;
  /** What a screen reader says about the chart, as it cannot read the drawing. */
  description: string;
  toggleMeasurementsLabel: string;
  /** Shown if Plotly cannot load, or cannot draw this data. */
  failedText: string;
}

function ChartEmptyState({ title, text }: EmptyState) {
  return (
    <div className="flex min-h-[340px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <ChartLineIcon className="size-[18px]" aria-hidden="true" />
      </div>
      <div className="font-semibold">{title}</div>
      <div className="max-w-[420px] text-muted-foreground">{text}</div>
    </div>
  );
}

function Legend({
  curves,
  measurementsLabel,
  interpolatedLabel,
}: {
  curves: readonly ChartCurve[];
  measurementsLabel: string | null;
  interpolatedLabel: string | null;
}) {
  if (curves.length === 0 && measurementsLabel === null) {
    return null;
  }
  return (
    <ul className="m-0 flex list-none flex-wrap gap-4 p-0 text-xs text-muted-foreground">
      {measurementsLabel !== null && (
        <li className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block size-2 rounded-full border-[1.5px] border-foreground bg-background"
          />
          {measurementsLabel}
        </li>
      )}
      {interpolatedLabel !== null && (
        <li className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block size-2 rounded-full"
            style={{ backgroundColor: "var(--accent-orange)" }}
          />
          {interpolatedLabel}
        </li>
      )}
      {curves.map((curve, index) => (
        <li key={curve.id} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0 w-4 border-t-2"
            style={{
              borderTopColor: `var(--accent-${curveColor(curve, index)})`,
              borderTopStyle: curve.dashed === true ? "dashed" : "solid",
            }}
          />
          {curve.label}
        </li>
      ))}
    </ul>
  );
}

function Plot({
  curves,
  measurements,
  interpolated,
  fitRange,
  referenceLines,
  xAxisTitle,
  xAxisSpan,
  xAxisUnitless,
  yAxisTitle,
  description,
  failedText,
}: {
  curves: readonly ChartCurve[];
  measurements: ChartMeasurements | null;
  interpolated: ChartMeasurements | null;
  fitRange: ChartFitRange | null;
  referenceLines: readonly ReferenceLine[];
  xAxisTitle: string;
  xAxisSpan?: readonly [number, number] | null | undefined;
  xAxisUnitless?: boolean | undefined;
  yAxisTitle: string;
  description: string;
  failedText: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [plotly, setPlotly] = useState<PlotlyModule | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    loadPlotly().then(
      (module) => {
        if (current) {
          setPlotly(module);
        }
      },
      () => {
        if (current) {
          setFailed(true);
        }
      },
    );
    return () => {
      current = false;
    };
  }, []);

  const input = useMemo(
    () => ({
      curves,
      measurements,
      interpolated,
      fitRange,
      referenceLines,
      xAxisTitle,
      xAxisSpan,
      xAxisUnitless,
      yAxisTitle,
    }),
    [
      curves,
      measurements,
      interpolated,
      fitRange,
      referenceLines,
      xAxisTitle,
      xAxisSpan,
      xAxisUnitless,
      yAxisTitle,
    ],
  );

  // `react` updates the existing drawing, so that a moving slider stays smooth.
  useEffect(() => {
    const element = container.current;
    if (plotly === null || element === null) {
      return;
    }
    // An error thrown here would otherwise take the whole page with it.
    Promise.resolve()
      .then(() => {
        const { data, layout } = buildFigure(input, readChartTheme(element));
        return plotly.react(element, data, layout, PLOT_CONFIG);
      })
      .catch(() => {
        setFailed(true);
      });
  }, [plotly, input]);

  useEffect(() => {
    const element = container.current;
    if (plotly === null || element === null) {
      return;
    }
    return () => {
      plotly.purge(element);
    };
  }, [plotly]);

  if (failed) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{failedText}</AlertDescription>
      </Alert>
    );
  }
  return (
    <div
      ref={container}
      role="img"
      aria-label={description}
      style={{ minHeight: CHART_HEIGHT_PX }}
    />
  );
}

/**
 * A chart of a quantity against temperature: measurements, model curves, the area outside the fit
 * range, and reference lines. All text comes in as props, for i18n.
 */
export function TransportChart({
  empty = null,
  curves,
  measurements = null,
  interpolated = null,
  fitRange = null,
  referenceLines = NO_REFERENCE_LINES,
  xAxisTitle,
  xAxisSpan,
  xAxisUnitless,
  yAxisTitle,
  description,
  toggleMeasurementsLabel,
  failedText,
}: TransportChartProps) {
  const [showMeasurements, setShowMeasurements] = useState(true);
  const toggleId = useId();

  if (empty !== null) {
    return <ChartEmptyState title={empty.title} text={empty.text} />;
  }
  const shownMeasurements = showMeasurements ? measurements : null;
  const shownInterpolated = showMeasurements ? interpolated : null;
  return (
    <figure className="m-0 flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Legend
          curves={curves}
          measurementsLabel={shownMeasurements?.label ?? null}
          interpolatedLabel={shownInterpolated?.label ?? null}
        />
        {measurements !== null && (
          <label
            htmlFor={toggleId}
            className="inline-flex items-center gap-2 text-xs text-muted-foreground"
          >
            {toggleMeasurementsLabel}
            <Switch
              id={toggleId}
              checked={showMeasurements}
              onCheckedChange={setShowMeasurements}
            />
          </label>
        )}
      </div>
      <Plot
        curves={curves}
        measurements={shownMeasurements}
        interpolated={shownInterpolated}
        fitRange={fitRange}
        referenceLines={referenceLines}
        xAxisTitle={xAxisTitle}
        xAxisSpan={xAxisSpan}
        xAxisUnitless={xAxisUnitless}
        yAxisTitle={yAxisTitle}
        description={description}
        failedText={failedText}
      />
    </figure>
  );
}
