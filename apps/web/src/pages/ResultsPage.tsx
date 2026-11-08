import { useQuery } from "@tanstack/react-query";
import { InfoIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { modelsQuery } from "@/api/queries";
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
import { fitModeOf } from "@/model/selection";
import { useMeasuredCurves } from "@/model/useLiveCurves";
import { QUANTITIES, useSessionStore, type Quantity } from "@/session/store";
import { PageHeading, Panel } from "@/shell/layout";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

const {
  results: text,
  fit: fitText,
  data: dataText,
  model: modelText,
} = STRINGS;

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
  const measured = useMeasuredCurves();

  const model = models?.models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  const badge = fitBadge(fit, mode?.iterative === true);
  const title = <title>{`${text.pageTitle} · ${STRINGS.appName}`}</title>;

  if (model === undefined || mode === undefined || !hasFittedValues(fit)) {
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
          subtitle=""
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
  const subtitle = [
    demo.length > 0 ? dataText.demoSource : null,
    model.id.toUpperCase(),
    scattering,
    mode.quantities
      .map((quantity) => dataText.quantities[quantity].symbol)
      .join(" + "),
    minK === null || maxK === null
      ? null
      : fitText.rangeSummary(formatNumber(minK), formatNumber(maxK)),
  ]
    .filter((part) => part !== null)
    .join(" · ");

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
  const notes = [
    ...new Set(demo.map(noticeText)),
    ...(endNote === null ? [] : [endNote]),
    // Its known issues come with the curves, so without them some may be missing.
    ...(measured.error === null ? [] : [fitText.rmseFailed]),
    ...issues.map(
      ({ severity, text: issue }) =>
        `${fitText.issueSeverity[severity]}: ${issue}`,
    ),
    ...(rows.some(({ atBound }) => atBound) ? [fitText.atBoundNote] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      {title}
      <PageHeading
        title={text.title}
        subtitle={subtitle}
        {...(badge === null ? {} : { status: <StatusBadge {...badge} /> })}
      />
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
              value={rmse === undefined ? "—" : rmseText(rmse)}
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
      <Panel title={text.parametersTitle} subtitle={text.parametersSubtitle}>
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
                    {row.value === "" ? "—" : row.value}
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    {row.bounds === "" ? "—" : row.bounds}
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
      {notes.length > 0 && (
        <section
          aria-label={text.notes}
          className="flex gap-2.5 rounded-xl border bg-muted/40 px-4 py-3.5 text-[13px]"
        >
          <InfoIcon className="mt-0.5 size-4 flex-none" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            {notes.map((note) => (
              <p key={note} className="m-0">
                {note}
              </p>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
