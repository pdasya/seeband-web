import { AlertCircleIcon } from "lucide-react";
import { useId, useMemo } from "react";

import type { ApiError } from "@/api/errors";
import { carrierValidationMessage } from "@/model/explicitDpb";
import { NETWORK_ERROR } from "@/api/errors";
import { useModels } from "@/api/queries";
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
  band2EdgeShown,
  bandGapForTab,
  CHART_TABS,
  chartTabView,
  derivedKind,
  drawsMeasuredCurves,
  ENERGY_IN_K,
  isQuantityTab,
} from "@/model/chartTabs";
import { retriesByItself } from "@/model/latestOnly";
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
    case "validation_error":
      return carrierValidationMessage(error.details) ?? text.calcFailed;
    case "calculation_failed": {
      const messages: Record<string, string> = text.calculationDetails;
      const detail = error.details.find(({ code }) =>
        Object.hasOwn(messages, code),
      );
      return messages[detail?.code ?? ""] ?? text.noResult;
    }
    case "rate_limited":
      return retriesByItself(error) ? text.rateLimited : text.rateLimitedWait;
    // The server is busy, with the calculations of others or of this page, and says when to retry.
    case "calculation_busy":
    case "server_busy":
    case "client_calc_limit":
      return retriesByItself(error) ? text.busy : text.serverUnavailable;
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
  const { data: models } = useModels();
  const energy = models?.energy_display ?? ENERGY_IN_K;
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
        {
          data,
          interpolation,
          bandGapK,
          energy,
          ...(selection.parameterization !== undefined &&
          selection.model === "dpb"
            ? { bandConfiguration: selection.bandConfiguration }
            : {}),
        },
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
      energy,
      measuredCurves,
      derived.result,
      diagramResult,
      selection.parameterization,
      selection.model,
      selection.bandConfiguration,
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
  // The chart shows the latest values once every curve it draws answers them: the earliest of
  // their times, or none while one still answers values already left.
  const drawnFrom = [...(usesMeasured ? [measured] : []), onTab].filter(
    ({ result }) => result !== null,
  );
  const changedAtMs = drawnFrom.some(({ changedAtMs }) => changedAtMs == null)
    ? null
    : Math.min(...drawnFrom.map(({ changedAtMs }) => changedAtMs ?? 0));

  const rmse = isQuantityTab(tab) ? measured.result?.rmse?.[tab] : undefined;
  // Shown as its field shows it, to the same step.
  const gap =
    tab === "band_diagram" ? band2EdgeShown(mode, parameters) : undefined;
  const metric =
    rmse !== undefined
      ? `${STRINGS.fit.rmse} ${rmseText(rmse)}`
      : gap !== undefined
        ? text.bandGapMetric(formatNumber(gap), energy.unit)
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
        xAxisUnitless={
          view.xAxis !== undefined && (view.xAxis.unitless ?? true)
        }
        yAxisTitle={view.yAxisTitle}
        description={view.description}
        failedText={text.failed}
        timing={`chart:${tab}`}
        changedAtMs={drawnFrom.length === 0 ? null : changedAtMs}
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
