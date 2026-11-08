import { useEffect, useState } from "react";

import { apiClient } from "@/api/client";
import { chartImage } from "@/charts/chartImage";
import {
  bandGapForTab,
  chartTabView,
  derivedKind,
  isQuantityTab,
} from "@/model/chartTabs";
import type { FitModeDescription } from "@/model/selection";
import type { LiveCalc } from "@/model/useLiveCurves";
import { DERIVED_KINDS_ASKED, type DerivedKind } from "@/model/chartTabs";
import { QUANTITIES, useSessionStore, type ChartTab } from "@/session/store";
import { STRINGS } from "@/strings";

const { report: text, chart: chartText, data: dataText } = STRINGS;

/** The charts of a report: the measured quantities with their fit, then the additional graphs. */
const ADDITIONAL: readonly ChartTab[] = [
  "chemical_potential",
  "conductivity",
  "thermal_conductivity",
  "bands",
  "carrier_concentration",
];

export interface ReportChart {
  tab: ChartTab;
  title: string;
  /** A picture, or null for a chart the mode does not draw. */
  src: string | null;
  /** What each line and set of points is, as a picture has no legend of its own. */
  legend: string;
  note: string | null;
  /** Why the chart is not drawn, as the screen says it, so that paper shows it was not left out. */
  missing: string | null;
}

/** A picture ready to paint, so that print does not take the page before it is. */
async function decoded(src: string): Promise<string> {
  const picture = new Image();
  picture.src = src;
  await picture.decode();
  return src;
}

/**
 * Prepares a report and prints it: each chart becomes a picture first, then the browser's print
 * dialog opens, from which a user saves a PDF.
 */
export function useReport({
  mode,
  measured,
  derived,
}: {
  mode: FitModeDescription | undefined;
  measured: LiveCalc;
  derived: Record<DerivedKind, LiveCalc>;
}) {
  const [charts, setCharts] = useState<readonly ReportChart[] | null>(null);
  const [apiVersion, setApiVersion] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [failed, setFailed] = useState(false);
  const [printing, setPrinting] = useState(0);

  // Once the pictures are on the page, as print takes the page as it is.
  useEffect(() => {
    if (printing > 0) {
      window.print();
    }
  }, [printing]);

  // After printing, the pictures go: they would be of old values by the next print, and are large.
  useEffect(() => {
    const done = () => {
      setCharts(null);
    };
    window.addEventListener("afterprint", done);
    return () => {
      window.removeEventListener("afterprint", done);
    };
  }, []);

  const prepare = async () => {
    if (mode === undefined) {
      return;
    }
    setPreparing(true);
    setFailed(false);
    try {
      const { data, interpolation, parameters, selection } =
        useSessionStore.getState();
      const { minTemperatureK: minK, maxTemperatureK: maxK } = selection;
      const tabs = [...(mode.quantities as readonly ChartTab[]), ...ADDITIONAL];
      const made = await Promise.all(
        tabs.map(async (tab): Promise<ReportChart> => {
          const kind = derivedKind(tab, mode);
          const view = chartTabView(
            tab,
            mode,
            {
              data,
              interpolation,
              bandGapK: bandGapForTab(tab, mode, parameters),
            },
            isQuantityTab(tab) || tab === "bands" ? measured.result : null,
            kind === null ? null : derived[kind].result,
          );
          const title = chartText.tabs[tab];
          if (view.empty !== null) {
            return {
              tab,
              title,
              src: null,
              legend: "",
              note: null,
              missing: text.notDrawn(view.empty.title, view.empty.text),
            };
          }
          const src = await decoded(
            await chartImage({
              curves: view.curves,
              measurements: view.measurements,
              interpolated: view.interpolated,
              fitRange:
                isQuantityTab(tab) && minK !== null && maxK !== null
                  ? { minK, maxK }
                  : null,
              referenceLines: view.referenceLines,
              xAxisTitle: chartText.temperatureAxis,
              yAxisTitle: view.yAxisTitle,
            }),
          );
          const legend = text.legend([
            ...(view.measurements === null ? [] : [view.measurements.label]),
            ...(view.interpolated === null || view.interpolated === undefined
              ? []
              : [view.interpolated.label]),
            ...view.curves.map(({ label }) => label),
          ]);
          return { tab, title, src, legend, note: view.note, missing: null };
        }),
      );
      setCharts(made);
      setApiVersion(
        await apiClient.getHealth().then(
          ({ version }) => version,
          () => null,
        ),
      );
      setPrinting((count) => count + 1);
    } catch {
      setFailed(true);
    } finally {
      setPreparing(false);
    }
  };

  // Every curve the mode offers is in, as a chart left out for want of one would go unnoticed.
  const ready =
    mode !== undefined &&
    measured.result !== null &&
    DERIVED_KINDS_ASKED.every(
      (kind) =>
        !mode.curves.some((curve) => curve.kind === kind && curve.available) ||
        derived[kind].result !== null,
    );

  return { charts, apiVersion, preparing, failed, ready, prepare };
}

/** What a printed report opens with, which the screen does not show. */
export function ReportHeader({ apiVersion }: { apiVersion: string | null }) {
  const data = useSessionStore((state) => state.data);
  return (
    <div className="hidden print:block">
      {/* Not a heading, as the page's own h1 follows. */}
      <p className="m-0 text-xl font-semibold">{text.title}</p>
      <p className="m-0 mt-1 text-xs text-muted-foreground">
        {text.made(
          new Date().toLocaleString("en-GB"),
          __APP_VERSION__,
          apiVersion,
        )}
      </p>
      <h2 className="m-0 mt-3 text-sm font-semibold">{text.data}</h2>
      <ul className="m-0 mt-1 list-none p-0 text-xs">
        {QUANTITIES.flatMap((quantity) => {
          const entry = data[quantity];
          if (entry === undefined) {
            return [];
          }
          const { measurement, source } = entry;
          return [
            <li key={quantity}>
              {text.file(
                dataText.quantities[quantity].symbol,
                source.kind === "file" ? source.name : dataText.demoSource,
                measurement.points,
                measurement.min_temperature_k,
                measurement.max_temperature_k,
              )}
            </li>,
          ];
        })}
      </ul>
    </div>
  );
}

/** The charts of a report, as pictures, on paper only. */
export function ReportCharts({
  charts,
}: {
  charts: readonly ReportChart[] | null;
}) {
  if (charts === null) {
    return null;
  }
  return (
    <section
      aria-label={text.charts}
      data-report-charts=""
      className="hidden print:block"
    >
      <h2 className="m-0 text-base font-semibold">{text.charts}</h2>
      <div className="mt-2 grid grid-cols-2 gap-3">
        {charts.map((chart) =>
          chart.src === null ? (
            <p key={chart.tab} className="m-0 text-xs">
              <span className="font-medium">{chart.title}</span>
              {": "}
              <span className="text-muted-foreground">{chart.missing}</span>
            </p>
          ) : (
            <figure key={chart.tab} className="m-0 break-inside-avoid">
              <figcaption className="text-xs">
                <span className="font-medium">{chart.title}</span>
                <span className="block text-[10px] text-muted-foreground">
                  {chart.legend}
                </span>
              </figcaption>
              <img
                src={chart.src}
                alt={text.chartAlt(chart.title)}
                className="w-full"
              />
              {chart.note !== null && (
                <p className="m-0 text-[10px] text-muted-foreground">
                  {chart.note}
                </p>
              )}
            </figure>
          ),
        )}
      </div>
    </section>
  );
}
