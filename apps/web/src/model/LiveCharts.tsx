import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon } from "lucide-react";
import { useMemo } from "react";

import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { modelsQuery } from "@/api/queries";
import { TransportChart } from "@/charts/TransportChart";
import type { ChartFitRange } from "@/charts/figure";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  bandGapForTab,
  chartTabView,
  drawsMeasuredCurves,
} from "@/model/chartTabs";
import { retriesByItself } from "@/model/latestOnly";
import { fitModeOf } from "@/model/selection";
import type { LiveCurves } from "@/model/useLiveCurves";
import { useSessionStore, type ChartTab } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { chart: text, fit } = STRINGS;

function failureText(error: ApiError): string {
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

const TABS: readonly ChartTab[] = [
  "seebeck",
  "resistivity",
  "hall",
  "chemical_potential",
  "bands",
];

/** The chart of the open tab, which keeps its last curve while waiting and after an error. */
export function LiveCharts({ live }: { live: LiveCurves }) {
  const { measured, derived } = live;
  const { data: models } = useQuery(modelsQuery);
  const tab = useSessionStore((state) => state.chartTab);
  const setTab = useSessionStore((state) => state.setChartTab);
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
  const bandGapK = bandGapForTab(tab, mode, parameters);
  const view = useMemo(
    () =>
      chartTabView(
        tab,
        mode,
        { data, interpolation, bandGapK },
        measured.result,
        derived.result,
      ),
    [tab, mode, data, interpolation, bandGapK, measured.result, derived.result],
  );
  const fitRange = useMemo((): ChartFitRange | null => {
    return minK === null || maxK === null ? null : { minK, maxK };
  }, [minK, maxK]);

  // Only what this tab draws. An RMSE has its own note, and other curves end with their tab.
  const usesMeasured = drawsMeasuredCurves(tab, mode, data);
  const failed = usesMeasured && measured.error !== null ? measured : derived;
  const { error } = failed;
  const busy = (usesMeasured && measured.busy) || derived.busy;

  return (
    <Panel title={fit.charts}>
      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value as ChartTab);
        }}
        className="mt-3 gap-2"
      >
        <TabsList
          aria-label={text.tabsLabel}
          className="h-auto flex-wrap justify-start"
        >
          {TABS.map((id) => (
            <TabsTrigger key={id} value={id} className="flex-none">
              {text.tabs[id]}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={tab} className="flex flex-col gap-2">
          <p
            role="status"
            className="m-0 min-h-[18px] text-xs text-muted-foreground"
          >
            {busy ? text.updating : ""}
          </p>
          {error !== null && (
            <Alert variant="destructive">
              <AlertCircleIcon aria-hidden="true" />
              <AlertDescription>
                {failed.result === null
                  ? failureText(error)
                  : `${failureText(error)} ${text.lastCurveStays}`}
              </AlertDescription>
            </Alert>
          )}
          <TransportChart
            empty={view.empty}
            curves={view.curves}
            measurements={view.measurements}
            interpolated={view.interpolated}
            referenceLines={view.referenceLines}
            fitRange={fitRange}
            xAxisTitle={text.temperatureAxis}
            yAxisTitle={view.yAxisTitle}
            description={view.description}
            toggleMeasurementsLabel={text.toggleMeasurements}
            failedText={text.failed}
          />
          {view.note !== null && (
            <p className="m-0 text-xs text-muted-foreground">{view.note}</p>
          )}
        </TabsContent>
      </Tabs>
    </Panel>
  );
}
