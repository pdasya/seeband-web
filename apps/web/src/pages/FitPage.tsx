import { TransportChart } from "@/charts/TransportChart";
import { DataPanel } from "@/data/DataPanel";
import { ModelPanel } from "@/model/ModelPanel";
import { ParametersPanel } from "@/model/ParametersPanel";
import { PageHeading, Panel, TwoColumns } from "@/shell/layout";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const NO_CURVES = [] as const;

/** The frame of the fit screen. The panels fill up from FS1 onwards. */
export function FitPage() {
  const { fit, chart } = STRINGS;
  return (
    <>
      <title>{`${fit.pageTitle} · ${STRINGS.appName}`}</title>
      <TwoColumns
        side={
          <>
            <DataPanel />
            <ModelPanel />
          </>
        }
        main={
          <>
            <PageHeading
              title={fit.title}
              subtitle={fit.subtitle}
              status={<StatusBadge status="manual" />}
            />
            <Panel title={fit.charts}>
              <div className="mt-4">
                <TransportChart
                  empty={{ title: chart.noDataTitle, text: chart.noDataText }}
                  curves={NO_CURVES}
                  xAxisTitle={chart.temperatureAxis}
                  yAxisTitle={chart.fitAxis}
                  description={chart.fitDescription}
                  toggleMeasurementsLabel={chart.toggleMeasurements}
                  failedText={chart.failed}
                />
              </div>
            </Panel>
            <div className="flex flex-wrap items-stretch gap-4">
              <div className="min-w-0 flex-[1_1_320px]">
                <ParametersPanel />
              </div>
              <div className="min-w-0 flex-[1_1_320px]">
                <Panel title={fit.result} />
              </div>
            </div>
          </>
        }
      />
    </>
  );
}
