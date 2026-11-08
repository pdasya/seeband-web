import { useQuery } from "@tanstack/react-query";
import { DownloadIcon, InfoIcon, PrinterIcon } from "lucide-react";
import { useId, useMemo, type ReactNode } from "react";
import { Link } from "react-router";

import { modelsQuery } from "@/api/queries";
import { TransportChart } from "@/charts/TransportChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { noticeText } from "@/data/DemoNotice";
import { formatNumber } from "@/lib/numbers";
import { failureText } from "@/model/ChartGrid";
import { bandGapForTab, chartTabView, derivedKind } from "@/model/chartTabs";
import { fitLog, type LogStep } from "@/model/fitLog";
import { fitBadge } from "@/model/fitStatus";
import {
  fitEndNote,
  fitIterations,
  hasFittedValues,
  resultIssues,
  resultRows,
  rmseText,
  type ParameterStatus,
} from "@/model/resultSummary";
import { fitModeOf, type FitModeDescription } from "@/model/selection";
import { ExportButtons } from "@/model/ExportButtons";
import { useExport } from "@/model/useExport";
import { ReportCharts, ReportHeader, useReport } from "@/pages/Report";
import { useResultCurves, type LiveCalc } from "@/model/useLiveCurves";
import {
  QUANTITIES,
  useSessionStore,
  type ChartTab,
  type Quantity,
} from "@/session/store";
import { PageHeading, Panel } from "@/shell/layout";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const {
  results: text,
  fit: fitText,
  data: dataText,
  model: modelText,
  chart: chartText,
  export: exportText,
  report: reportText,
} = STRINGS;

type ExportGraph = ReturnType<typeof useExport>["graph"];

function symbols(quantities: readonly Quantity[]): string {
  return quantities
    .map((quantity) => dataText.quantities[quantity].symbol)
    .join(", ");
}

function scatteringName(id: string): string {
  const known: Record<string, string> = modelText.scatteringNames;
  return known[id] ?? id;
}

function Kpi({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail: string;
}) {
  return (
    <div className="min-w-0 flex-[1_1_180px] rounded-xl border bg-card px-4 py-3.5 shadow-card">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="m-0 text-[22px] font-semibold tracking-[-0.02em] tabular-nums">
        {value}
      </dd>
      <dd className="m-0 text-xs text-muted-foreground">{detail}</dd>
    </div>
  );
}

function StatusCell({ status }: { status: ParameterStatus }) {
  switch (status.kind) {
    case "fitted":
      return <Badge variant="success">{text.status.fitted}</Badge>;
    case "fixed":
      return <Badge variant="neutral">{text.status.fixed}</Badge>;
    default:
      return (
        <Badge variant="warning">
          {text.status.needs(symbols(status.quantities))}
        </Badge>
      );
  }
}

/** The steps of a fit, numbered and joined by a line, as the design draws them. */
function FitLog({ steps }: { steps: readonly LogStep[] }) {
  return (
    <ol
      aria-label={text.log.title}
      className="m-0 mt-3 flex list-none flex-col p-0"
    >
      {steps.map((step, at) => {
        const last = at === steps.length - 1;
        return (
          <li key={step.title} className="flex gap-3">
            <div className="flex flex-none flex-col items-center">
              <span
                aria-hidden="true"
                className={
                  last
                    ? "flex size-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
                    : "flex size-6 items-center justify-center rounded-full border bg-muted text-xs font-semibold"
                }
              >
                {at + 1}
              </span>
              {!last && <span className="min-h-3 w-px flex-auto bg-border" />}
            </div>
            <div className="min-w-0 pb-4">
              <div className="font-medium">{step.title}</div>
              <div className="text-[13px] text-muted-foreground">
                {step.text}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const NOTHING: LiveCalc = { result: null, busy: false, error: null };

/** The design's additional graphs, each in a chart of its own. */
const MORE_GRAPHS: readonly ChartTab[] = [
  "chemical_potential",
  "conductivity",
  "thermal_conductivity",
  "bands",
  "carrier_concentration",
];

/** One additional graph, with what is known to be wrong with its curve. */
function MoreGraph({
  tab,
  mode,
  measured,
  derived,
  onExport,
}: {
  tab: ChartTab;
  mode: FitModeDescription;
  measured: LiveCalc;
  derived: LiveCalc;
  onExport: ExportGraph;
}) {
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const parameters = useSessionStore((state) => state.parameters);
  const bandGapK = bandGapForTab(tab, mode, parameters);
  const titleId = useId();
  const total = tab === "bands" ? measured.result : null;
  // Kept between renders, as a new view redraws the chart.
  const view = useMemo(
    () =>
      chartTabView(
        tab,
        mode,
        { data, interpolation, bandGapK },
        total,
        derived.result,
      ),
    [tab, mode, data, interpolation, bandGapK, total, derived.result],
  );
  // Each flag of the curves it draws: its own kind, and for S by band also the total of S, which
  // comes with the measured curves and their flags of other quantities.
  const drawn = view.empty === null;
  const own = drawn ? (derived.result?.known_issues ?? []) : [];
  const issues = resultIssues(mode, {
    fit: [],
    measured:
      drawn && tab === "bands" ? (measured.result?.known_issues ?? []) : [],
    derived: own,
  }).filter(
    ({ id, quantities }) => own.includes(id) || quantities.includes("seebeck"),
  );
  const failed =
    derived.error ?? (tab === "bands" ? measured.error : null) ?? null;
  // What it drew, with the API's names: the total of S of the bands comes with the measured curves.
  const answer = drawn ? derived.result : null;
  const totalS = total?.curves.seebeck_v_per_k;
  const exported =
    answer === null
      ? null
      : [
          ...(tab === "bands" && totalS !== undefined
            ? [{ name: "seebeck_v_per_k", values: totalS }]
            : []),
          ...Object.entries(answer.curves).map(([name, values]) => ({
            name,
            values,
          })),
        ];
  return (
    <section
      aria-labelledby={titleId}
      className="flex min-w-0 flex-col gap-2 rounded-lg border p-3"
    >
      <div className="flex items-start justify-between gap-2">
        <h3
          id={titleId}
          className="m-0 flex flex-wrap items-center gap-1.5 text-sm font-medium"
        >
          {chartText.tabs[tab]}
          {issues.map(({ id, severity }) => (
            <Badge key={id} variant="outline">
              {fitText.issueMark[severity]}
            </Badge>
          ))}
        </h3>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={exportText.graph(chartText.tabs[tab])}
          disabled={answer === null || exported === null}
          onClick={() => {
            if (answer !== null && exported !== null) {
              void onExport(
                tab,
                answer.temperature_k,
                exported,
                issues.map(({ id }) => id),
              );
            }
          }}
        >
          <DownloadIcon aria-hidden="true" />
        </Button>
      </div>
      {failed !== null && (
        <p role="alert" className="m-0 text-xs text-destructive">
          {failureText(failed)}
        </p>
      )}
      <TransportChart
        empty={view.empty}
        curves={view.curves}
        measurements={null}
        interpolated={null}
        referenceLines={view.referenceLines}
        fitRange={null}
        xAxisTitle={chartText.temperatureAxis}
        xAxisSpan={null}
        xAxisUnitless={false}
        yAxisTitle={view.yAxisTitle}
        description={view.description}
        failedText={chartText.failed}
      />
      {view.note !== null && (
        <p className="m-0 text-xs text-muted-foreground">{view.note}</p>
      )}
      {issues.map(({ id, severity, text: issue }) => (
        <p key={id} className="m-0 text-xs text-muted-foreground">
          {text.issue(fitText.issueSeverity[severity], issue)}
        </p>
      ))}
    </section>
  );
}

/** Where the page stands before there is a fit to sum up. */
function NoResult({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border bg-card p-5 shadow-card">
      <p className="m-0 text-muted-foreground">{message}</p>
      <Button variant="outline" asChild>
        <Link to="/fit">{text.toFit}</Link>
      </Button>
    </div>
  );
}

/** The last fit: what was fitted, how well, and what is known to be wrong with it. */
export function ResultsPage() {
  const { data: models, isPending, isError } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const fit = useSessionStore((state) => state.fit);
  const customBounds = useSessionStore((state) => state.customBounds);
  const startNet = useSessionStore((state) => state.fitStartNet);

  const model = models?.models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  const summed =
    model !== undefined && mode !== undefined && hasFittedValues(fit);
  const { measured, derived } = useResultCurves(summed);
  const graphsId = useId();
  const exporter = useExport();
  const report = useReport({ mode, measured, derived });
  const reportStatusId = useId();
  const badge = fitBadge(fit, mode?.iterative === true);
  const title = <title>{`${text.pageTitle} · ${STRINGS.appName}`}</title>;

  if (!summed || model === undefined || mode === undefined) {
    // A change of values on the fit screen ends its result, so "no fit" is about these values.
    const message = isPending
      ? modelText.loading
      : isError
        ? modelText.loadFailed
        : fit.status === "idle"
          ? text.noFit
          : fit.status === "waiting" || fit.status === "running"
            ? text.running
            : text.noValues;
    return (
      <div className="flex flex-col gap-4">
        {title}
        <PageHeading
          title={text.title}
          {...(badge === null ? {} : { status: <StatusBadge {...badge} /> })}
        />
        <NoResult message={message} />
      </div>
    );
  }

  const demo = QUANTITIES.flatMap((quantity) => {
    const source = data[quantity]?.source;
    return source?.kind === "demo" ? [source.messageKey] : [];
  });
  const {
    minTemperatureK: minK,
    maxTemperatureK: maxK,
    scattering,
  } = selection;
  const subtitle = text.summary(
    [
      demo.length > 0 ? dataText.demoSource : null,
      model.id.toUpperCase(),
      scattering,
      text.modeLabel(
        mode.quantities.map((quantity) => dataText.quantities[quantity].symbol),
      ),
      minK === null || maxK === null
        ? null
        : fitText.rangeSummary(formatNumber(minK), formatNumber(maxK)),
    ].filter((part) => part !== null),
  );

  const rows = resultRows(
    model,
    mode,
    selection,
    parameters[mode.id],
    fit,
    customBounds[mode.id],
  );
  const issues = resultIssues(mode, {
    fit: fit.status === "done" ? fit.result.known_issues : [],
    measured: measured.result?.known_issues ?? [],
    derived: [],
  });
  const iterations = fitIterations(fit);
  const endNote = fitEndNote(fit, mode.max_iterations ?? null);
  // Keyed by where each comes from, as two unknown issues can read the same.
  const notes = [
    ...[...new Set(demo)].map((key) => ({
      key: `demo:${key}`,
      text: noticeText(key),
    })),
    ...(endNote === null ? [] : [{ key: "end", text: endNote }]),
    // Its known issues come with the curves, so without them some may be missing.
    ...(measured.error === null
      ? []
      : [{ key: "rmse", text: fitText.rmseFailed }]),
    ...issues.map(({ id, severity, text: issue }) => ({
      key: `issue:${id}`,
      text: text.issue(fitText.issueSeverity[severity], issue),
    })),
    ...(rows.some(({ atBound }) => atBound)
      ? [{ key: "bound", text: fitText.atBoundNote }]
      : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      {title}
      <ReportHeader apiVersion={report.apiVersion} />
      <PageHeading
        title={text.title}
        subtitle={subtitle}
        {...(badge === null ? {} : { status: <StatusBadge {...badge} /> })}
        actions={
          <>
            <ExportButtons exporter={exporter} />
            <Button
              disabled={report.preparing || !report.ready}
              aria-describedby={reportStatusId}
              onClick={() => void report.prepare()}
            >
              <PrinterIcon aria-hidden="true" />
              {report.preparing ? reportText.preparing : reportText.button}
            </Button>
          </>
        }
      />
      {/* Why the button waits, and that it works, said on screen and to a screen reader. */}
      <p
        id={reportStatusId}
        role="status"
        className="m-0 text-xs text-muted-foreground empty:hidden print:hidden"
      >
        {report.preparing
          ? reportText.preparingStatus
          : report.ready
            ? ""
            : reportText.waiting}
      </p>
      {report.failed && (
        <p role="alert" className="m-0 text-xs text-destructive print:hidden">
          {reportText.failed}
        </p>
      )}
      {exporter.failed && (
        <p role="alert" className="m-0 text-xs text-destructive print:hidden">
          {exportText.failed}
        </p>
      )}
      <dl className="m-0 flex flex-wrap gap-3">
        <Kpi
          label={text.model}
          value={model.id.toUpperCase()}
          detail={model.name}
        />
        {scattering !== null && (
          <Kpi
            label={text.scattering}
            value={scattering}
            detail={scatteringName(scattering)}
          />
        )}
        {mode.quantities.map((quantity) => {
          const rmse = measured.result?.rmse?.[quantity];
          // Missing data, a failed or pending calculation each say so, and none passes for another.
          const detail =
            rmse !== undefined
              ? text.inRange
              : data[quantity] === undefined
                ? text.noRmse
                : measured.error !== null
                  ? text.rmseFailed
                  : text.rmseCalculating;
          return (
            <Kpi
              key={quantity}
              label={text.rmse(dataText.quantities[quantity].symbol)}
              value={rmse === undefined ? text.noValue : rmseText(rmse)}
              detail={detail}
            />
          );
        })}
        {mode.iterative && (
          <Kpi
            label={text.iterations}
            value={iterations ?? fitText.noIterations}
            detail={
              mode.max_iterations === null || mode.max_iterations === undefined
                ? ""
                : fitText.iterationLimit(mode.max_iterations)
            }
          />
        )}
      </dl>
      <div className="flex flex-wrap items-stretch gap-4">
        <div className="min-w-0 flex-[999_1_520px]">
          <Panel
            title={text.parametersTitle}
            subtitle={text.parametersSubtitle}
          >
            <div className="mt-3">
              <Table aria-label={text.parameterTable}>
                <TableHeader>
                  <TableRow>
                    <TableHead>{text.columns.parameter}</TableHead>
                    <TableHead>{text.columns.meaning}</TableHead>
                    <TableHead className="text-right">
                      {text.columns.value}
                    </TableHead>
                    <TableHead className="text-right">
                      {text.columns.bounds}
                    </TableHead>
                    <TableHead className="text-right">
                      {text.columns.status}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.name}>
                      <TableCell className="font-medium">
                        <span className="inline-flex flex-wrap items-center gap-1.5">
                          {row.symbol}
                          {row.atBound && (
                            <Badge variant="outline">{fitText.atBound}</Badge>
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="whitespace-normal text-muted-foreground">
                        {row.meaning}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {row.value === "" ? text.noValue : row.value}
                      </TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">
                        {row.bounds === "" ? text.noValue : row.bounds}
                      </TableCell>
                      <TableCell className="text-right">
                        <StatusCell status={row.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>
        </div>
        {/* The report leaves the log out. */}
        <div className="min-w-0 flex-[1_1_320px] print:hidden">
          <Panel title={text.log.title} subtitle={text.log.subtitle}>
            <FitLog steps={fitLog(mode, scattering, fit, startNet)} />
          </Panel>
        </div>
      </div>
      {/* On paper, pictures of fixed size take the place of live charts, which do not resize. */}
      <ReportCharts charts={report.charts} />
      <section
        aria-labelledby={graphsId}
        className="rounded-xl border bg-card p-5 shadow-card print:hidden"
      >
        <h2
          id={graphsId}
          className="m-0 text-base font-semibold tracking-[-0.01em]"
        >
          {text.graphs.title}
        </h2>
        <p className="mt-1 mb-0 text-[13px] text-muted-foreground">
          {text.graphs.subtitle}
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {MORE_GRAPHS.map((tab) => {
            const kind = derivedKind(tab, mode);
            return (
              <MoreGraph
                key={tab}
                tab={tab}
                mode={mode}
                onExport={exporter.graph}
                measured={measured}
                derived={kind === null ? NOTHING : derived[kind]}
              />
            );
          })}
        </div>
      </section>
      {notes.length > 0 && (
        <section
          aria-label={text.notes}
          className="flex gap-2.5 rounded-xl border bg-muted/40 px-4 py-3.5 text-[13px]"
        >
          <InfoIcon className="mt-0.5 size-4 flex-none" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            {notes.map((note) => (
              <p key={note.key} className="m-0">
                {note.text}
              </p>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
