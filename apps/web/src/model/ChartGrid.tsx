import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon } from "lucide-react";
import { useId, useMemo } from "react";

import type { ApiError } from "@/api/errors";
import { NETWORK_ERROR } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { TransportChart } from "@/charts/TransportChart";
import type { ChartFitRange } from "@/charts/figure";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatNumber } from "@/lib/numbers";
import {
  bandGapForTab,
  CHART_TABS,
  chartTabView,
  derivedKind,
  drawsMeasuredCurves,
  isQuantityTab,
} from "@/model/chartTabs";
import { retriesByItself } from "@/model/latestOnly";
import { parameterValues } from "@/model/parameters";
import { rmseText } from "@/model/resultSummary";
import { fitModeOf } from "@/model/selection";
import type { LiveCalc, LiveCurves } from "@/model/useLiveCurves";
import { useSessionStore, type ChartTab } from "@/session/store";
import { STRINGS } from "@/strings";

const { chart: text } = STRINGS;

const NOTHING: LiveCalc = { result: null, busy: false, error: null };

/** What a chart says of a failed curve, in our own words. */
export function failureText(error: ApiError): string {
  switch (error.code) {
    case "calculation_failed":
      return text.noResult;
    case "rate_limited":
      return retriesByItself(error) ? text.rateLimited : text.rateLimitedWait;
    case NETWORK_ERROR:
      return text.networkError;
    default:
      return error.status >= 500 ? text.serverUnavailable : text.calcFailed;
  }
}

/** One chart of the grid, with its own choice of what it shows. */
function ChartPanel({ index, live }: { index: number; live: LiveCurves }) {
  const { measured, diagram } = live;
  const labelId = useId();
  const { data: models } = useQuery(modelsQuery);
  const tab = useSessionStore((state) => state.chartPanels[index] ?? "seebeck");
  const setPanel = useSessionStore((state) => state.setChartPanel);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const parameters = useSessionStore((state) => state.parameters);
  const selection = useSessionStore((state) => state.selection);
  const minK = selection.minTemperatureK;
  const maxK = selection.maxTemperatureK;

  const mode = fitModeOf(
    models?.models.find(({ id }) => id === selection.model),
    selection.fitMode,
  );
  const kind = derivedKind(tab, mode);
  const derived = kind === null ? NOTHING : live.derived[kind];
  const bandGapK = bandGapForTab(tab, mode, parameters);
  // Only the measured quantities and the total of S draw the measured curves, so an answer for
  // them does not redraw the others.
  const measuredCurves =
    isQuantityTab(tab) || tab === "bands" || tab === "conductivity"
      ? measured.result
      : null;
  const diagramResult = tab === "band_diagram" ? diagram.result : null;
  const view = useMemo(
    () =>
      chartTabView(
        tab,
        mode,
        { data, interpolation, bandGapK },
        measuredCurves,
        derived.result,
        diagramResult,
      ),
    [
      tab,
      mode,
      data,
      interpolation,
      bandGapK,
      measuredCurves,
      derived.result,
      diagramResult,
    ],
  );
  const fitRange = useMemo((): ChartFitRange | null => {
    return minK === null || maxK === null ? null : { minK, maxK };
  }, [minK, maxK]);

  // Only what this chart draws. An RMSE has its own note, and other curves end with their chart.
  const usesMeasured = drawsMeasuredCurves(tab, mode, data);
  const onTab = tab === "band_diagram" ? diagram : derived;
  // Each request the chart draws from says when it fails, so one failure hides no other.
  const failures = [
    ...new Set(
      [...(usesMeasured ? [measured] : []), onTab].flatMap(
        ({ error, result }) =>
          error === null
            ? []
            : [
                result === null
                  ? failureText(error)
                  : `${failureText(error)} ${text.lastCurveStays}`,
              ],
      ),
    ),
  ];
  const busy = (usesMeasured && measured.busy) || onTab.busy;

  const rmse = isQuantityTab(tab) ? measured.result?.rmse?.[tab] : undefined;
  const gap =
    tab === "band_diagram" && mode !== undefined
      ? parameterValues(mode, parameters[mode.id]).band_gap
      : undefined;
  const metric =
    rmse !== undefined
      ? `${STRINGS.fit.rmse} ${rmseText(rmse)}`
      : gap !== undefined
        ? text.bandGapMetric(formatNumber(gap))
        : "";

  return (
    <section
      aria-labelledby={labelId}
      className="flex min-w-0 flex-col gap-2 rounded-xl border bg-card p-3 shadow-card"
    >
      <h2 id={labelId} className="sr-only">
        {text.panelLabel(index + 1)}
      </h2>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select
          value={tab}
          onValueChange={(value) => {
            setPanel(index, value as ChartTab);
          }}
        >
          <SelectTrigger
            size="sm"
            className="min-w-0 font-semibold"
            aria-label={text.panelSelect(index + 1)}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CHART_TABS.map((option) => (
              <SelectItem key={option} value={option}>
                {text.tabs[option]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2 text-xs whitespace-nowrap text-muted-foreground">
          {/* In the head, so a chart keeps its height while it waits. */}
          <span role="status">{busy ? text.updating : ""}</span>
          <span className="font-mono">{metric}</span>
        </div>
      </div>
      {failures.map((failure) => (
        <Alert key={failure} variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      ))}
      <TransportChart
        empty={view.empty}
        curves={view.curves}
        measurements={view.measurements}
        interpolated={view.interpolated}
        referenceLines={view.referenceLines}
        fitRange={view.xAxis === undefined ? fitRange : null}
        xAxisTitle={view.xAxis?.title ?? text.temperatureAxis}
        xAxisSpan={view.xAxis?.span ?? null}
        xAxisUnitless={view.xAxis !== undefined}
        yAxisTitle={view.yAxisTitle}
        description={view.description}
        failedText={text.failed}
      />
      {view.note !== null && (
        <p className="m-0 text-xs text-muted-foreground">{view.note}</p>
      )}
    </section>
  );
}

/** Four charts, each with its own choice, as the design draws them. */
export function ChartGrid({ live }: { live: LiveCurves }) {
  const panels = useSessionStore((state) => state.chartPanels);
  return (
    <div id="charts" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {panels.map((_, index) => (
        <ChartPanel key={index} index={index} live={live} />
      ))}
    </div>
  );
}
