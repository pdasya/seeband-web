import { DataBar } from "@/data/DataBar";
import { ChartGrid } from "@/model/ChartGrid";
import { FitPanel } from "@/model/FitPanel";
import { ModelPanel } from "@/model/ModelPanel";
import { ParametersPanel } from "@/model/ParametersPanel";
import { ResultPanel } from "@/model/ResultPanel";
import { useFitControl } from "@/model/useFitControl";
import { useGuess } from "@/model/useGuess";
import { useLiveCurves } from "@/model/useLiveCurves";
import { STRINGS } from "@/strings";

/**
 * The fit screen, as the design's four-chart layout: the data and the charts, then the result,
 * beside the fit, the model and the parameters. The two wrap into one column on a narrow screen.
 */
export function FitPage() {
  const { fit } = STRINGS;
  const live = useLiveCurves();
  const control = useFitControl();
  const guess = useGuess();
  return (
    <>
      <title>{`${fit.pageTitle} · ${STRINGS.appName}`}</title>
      {/* The charts take what the right column leaves, and above 1200 px it stands beside them. */}
      <div className="grid grid-cols-1 items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1fr)_600px]">
        <div className="flex min-w-0 flex-col gap-3">
          <DataBar />
          <ChartGrid live={live} />
          <ResultPanel live={live} />
        </div>
        <aside
          aria-label={fit.panelTitle}
          className="flex min-w-0 flex-col gap-3"
        >
          <FitPanel control={control} guess={guess} />
          {/* Side by side and of one size where both fit, one under the other where they do not. */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(294px,1fr))] gap-3">
            <ParametersPanel />
            <ModelPanel />
          </div>
        </aside>
      </div>
    </>
  );
}
