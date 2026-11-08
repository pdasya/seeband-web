import { useQuery } from "@tanstack/react-query";
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
import { formatNumber } from "@/lib/numbers";
import { rmseGaps } from "@/model/liveCurves";
import {
  fitEndNote,
  fitIterations,
  parameterRows,
  quantityMark,
  resultIssues,
  rmseText,
  type ResultIssue,
} from "@/model/resultSummary";
import { fitModeOf } from "@/model/selection";
import type { LiveCurves } from "@/model/useLiveCurves";
import { QUANTITIES, useSessionStore, type Quantity } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { fit, data: dataText } = STRINGS;

function symbols(quantities: readonly Quantity[]): string {
  return quantities
    .map((quantity) => dataText.quantities[quantity].symbol)
    .join(", ");
}

function Note({ children }: { children: string }) {
  return <p className="mt-3 mb-0 text-xs text-muted-foreground">{children}</p>;
}

function Metric({
  label,
  mark,
  detail,
  children,
}: {
  label: string;
  mark?: ReactNode;
  detail?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-lg border px-3 py-2.5">
      <dt className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        {label}
        {mark}
      </dt>
      <dd className="m-0 text-base font-semibold tabular-nums">{children}</dd>
      {detail !== undefined && (
        <dd className="m-0 text-[11px] text-muted-foreground">{detail}</dd>
      )}
    </div>
  );
}

function Issues({ issues }: { issues: readonly ResultIssue[] }) {
  return issues.map(({ id, severity, text }) => (
    <Note key={id}>{`${fit.issueSeverity[severity]}: ${text}`}</Note>
  ));
}

/** What the current values give, and what is known about them. */
export function ResultPanel({ live }: { live: LiveCurves }) {
  const { result, error } = live.measured;
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const fitState = useSessionStore((state) => state.fit);
  const customBounds = useSessionStore((state) => state.customBounds);
  const setChartPanel = useSessionStore((state) => state.setChartPanel);
  const panels = useSessionStore((state) => state.chartPanels);
  const gaps = rmseGaps(
    { selection, parameters, data, interpolation },
    models?.models,
  );
  const model = models?.models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);

  const rows = QUANTITIES.flatMap((quantity) => {
    const rmse = result?.rmse?.[quantity];
    return rmse === undefined ? [] : [{ quantity, rmse }];
  });
  const issues = resultIssues(mode, {
    fit: fitState.status === "done" ? fitState.result.known_issues : [],
    measured: result?.known_issues ?? [],
    derived: Object.values(live.derived).flatMap(
      ({ result: curves }) => curves?.known_issues ?? [],
    ),
  });
  const explained =
    gaps.noPointsInRange.length > 0 || gaps.notInterpolated.length > 0;
  const iterative = mode?.iterative === true;
  const iterations = fitIterations(fitState);
  const endNote = fitEndNote(fitState, mode?.max_iterations ?? null);
  const table =
    mode === undefined
      ? []
      : parameterRows(
          mode,
          selection.scattering,
          parameters[mode.id],
          fitState,
          customBounds[mode.id],
        );
  const { minTemperatureK: minK, maxTemperatureK: maxK } = selection;
  const subtitle = [
    model?.id.toUpperCase(),
    selection.scattering,
    minK === null || maxK === null
      ? null
      : fit.rangeSummary(formatNumber(minK), formatNumber(maxK)),
  ]
    .filter((part) => part !== null && part !== undefined)
    .join(" · ");

  const openMoreGraphs = () => {
    setChartPanel(panels.length - 1, "chemical_potential");
    document.getElementById("charts")?.scrollIntoView({ block: "nearest" });
  };

  return (
    <Panel title={fit.result} {...(subtitle === "" ? {} : { subtitle })}>
      {rows.length === 0 && !gaps.hasData && <Note>{fit.noRmse}</Note>}
      {rows.length === 0 && gaps.hasData && !explained && error !== null && (
        <Note>{fit.rmseFailed}</Note>
      )}
      {(rows.length > 0 || iterative) && (
        <dl className="mt-3 mb-0 grid grid-cols-[repeat(auto-fit,minmax(110px,1fr))] gap-2">
          {rows.map(({ quantity, rmse }) => {
            const mark = quantityMark(issues, quantity);
            return (
              <Metric
                key={quantity}
                label={`${fit.rmse}, ${dataText.quantities[quantity].symbol}`}
                mark={
                  mark !== null && (
                    <Badge variant="outline">{fit.issueMark[mark]}</Badge>
                  )
                }
              >
                {rmseText(rmse)}
              </Metric>
            );
          })}
          {iterative && (
            <Metric
              label={fit.iterations}
              {...(mode?.max_iterations === undefined ||
              mode.max_iterations === null
                ? {}
                : { detail: fit.iterationLimit(mode.max_iterations) })}
            >
              {iterations ?? fit.noIterations}
            </Metric>
          )}
        </dl>
      )}
      {error !== null && result !== null && <Note>{fit.rmseOutdated}</Note>}
      {gaps.noPointsInRange.length > 0 && (
        <Note>{`${symbols(gaps.noPointsInRange)}: ${fit.noPointsInRange}`}</Note>
      )}
      {gaps.notInterpolated.length > 0 && (
        <Note>{`${symbols(gaps.notInterpolated)}: ${fit.notInterpolated}`}</Note>
      )}
      {gaps.zerosLeftOut.length > 0 && (
        <Note>{`${symbols(gaps.zerosLeftOut)}: ${fit.zerosLeftOut}`}</Note>
      )}
      <Issues issues={issues.filter(({ place }) => place === "curves")} />
      {endNote !== null && <Note>{endNote}</Note>}
      {table.length > 0 && (
        <div className="mt-3">
          <Table aria-label={fit.parameterTable}>
            <TableHeader>
              <TableRow>
                <TableHead>{fit.columns.parameter}</TableHead>
                <TableHead className="text-right">
                  {fit.columns.value}
                </TableHead>
                <TableHead className="text-right">
                  {fit.columns.bounds}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {table.map((row) => (
                <TableRow key={row.name}>
                  <TableCell>
                    <span className="inline-flex flex-wrap items-center gap-1.5">
                      {row.symbol}
                      {row.atBound && (
                        <Badge variant="outline">{fit.atBound}</Badge>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {row.value}
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    {row.bounds}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {table.some(({ atBound }) => atBound) && <Note>{fit.atBoundNote}</Note>}
      <Issues issues={issues.filter(({ place }) => place === "fit")} />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={openMoreGraphs}>
          {fit.moreGraphs}
        </Button>
        <Button variant="outline" asChild>
          <Link to="/results">{fit.openResults}</Link>
        </Button>
      </div>
    </Panel>
  );
}
