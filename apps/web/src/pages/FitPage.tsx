import { DataPanel } from "@/data/DataPanel";
import { LiveCharts } from "@/model/LiveCharts";
import { ModelPanel } from "@/model/ModelPanel";
import { ParametersPanel } from "@/model/ParametersPanel";
import { ResultPanel } from "@/model/ResultPanel";
import { useLiveCurves } from "@/model/useLiveCurves";
import { PageHeading, TwoColumns } from "@/shell/layout";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

/** The frame of the fit screen. The panels fill up from FS1 onwards. */
export function FitPage() {
  const { fit } = STRINGS;
  const live = useLiveCurves();
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
            <LiveCharts live={live} />
            <div className="flex flex-wrap items-stretch gap-4">
              <div className="min-w-0 flex-[1_1_320px]">
                <ParametersPanel />
              </div>
              <div className="min-w-0 flex-[1_1_320px]">
                <ResultPanel live={live} />
              </div>
            </div>
          </>
        }
      />
    </>
  );
}
