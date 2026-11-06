import { AlertCircleIcon } from "lucide-react";
import { useMemo } from "react";

import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { TransportChart } from "@/charts/TransportChart";
import type { ChartFitRange, ChartMeasurements } from "@/charts/figure";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SEEBECK_CURVE, toMicrovoltPerK } from "@/model/liveCurves";
import type { LiveCurves } from "@/model/useLiveCurves";
import { fitData, useSessionStore } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { chart: text, fit } = STRINGS;

function failureText(error: ApiError): string {
  switch (error.code) {
    case "calculation_failed":
      return text.noResult;
    case "rate_limited":
      return text.rateLimited;
    case NETWORK_ERROR:
      return text.networkError;
    default:
      return error.status >= 500 ? text.serverUnavailable : text.calcFailed;
  }
}

/** The curve of S and its measurements. The other quantities come with the chart's tabs. */
export function LiveCharts({ live }: { live: LiveCurves }) {
  const { result, busy, error } = live;
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const minK = useSessionStore((state) => state.selection.minTemperatureK);
  const maxK = useSessionStore((state) => state.selection.maxTemperatureK);

  const hasSeebeck = data.seebeck !== undefined;
  const curves = useMemo(() => {
    const values = result?.curves[SEEBECK_CURVE];
    return result == null || values === undefined
      ? []
      : [
          {
            id: SEEBECK_CURVE,
            label: text.model,
            temperatureK: result.temperature_k,
            values: toMicrovoltPerK(values),
          },
        ];
  }, [result]);
  const measurements = useMemo((): ChartMeasurements | null => {
    // Interpolated values on their way leave the measured ones in view.
    const shown =
      fitData({ data, interpolation }, "seebeck") ?? data.seebeck?.measurement;
    return shown === undefined
      ? null
      : {
          label: text.measurements,
          temperatureK: shown.temperature_k,
          values: toMicrovoltPerK(shown.values),
        };
  }, [data, interpolation]);
  const fitRange = useMemo((): ChartFitRange | null => {
    return minK === null || maxK === null ? null : { minK, maxK };
  }, [minK, maxK]);

  return (
    <Panel title={fit.charts}>
      <div className="mt-2 flex flex-col gap-2">
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
              {result === null
                ? failureText(error)
                : `${failureText(error)} ${text.lastCurveStays}`}
            </AlertDescription>
          </Alert>
        )}
        <TransportChart
          empty={
            hasSeebeck
              ? null
              : { title: text.noDataTitle, text: text.noDataText }
          }
          curves={curves}
          measurements={measurements}
          fitRange={fitRange}
          xAxisTitle={text.temperatureAxis}
          yAxisTitle={text.fitAxis}
          description={text.fitDescription}
          toggleMeasurementsLabel={text.toggleMeasurements}
          failedText={text.failed}
        />
      </div>
    </Panel>
  );
}
