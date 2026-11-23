import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient, type CalcRequest, type CalcResponse } from "@/api/client";
import { modelsQuery } from "@/api/queries";
import { TransportChart } from "@/charts/TransportChart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNumber } from "@/lib/numbers";
import { quantityChart } from "@/model/chartTabs";
import { modeLabel } from "@/model/exportFiles";
import { fitBadge } from "@/model/fitStatus";
import { calcRequest } from "@/model/liveCurves";
import { ParameterStatusBadge } from "@/model/ParameterStatusBadge";
import {
  parameterRows,
  rmseSymbol,
  rmseText,
  type ParameterRow,
} from "@/model/resultSummary";
import {
  fitModeOf,
  type FitModeDescription,
  type ModelDescription,
} from "@/model/selection";
import {
  useSessionStore,
  type FitResult,
  type FitRun,
  type Quantity,
} from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";
import { Subscripted } from "@/lib/subscripts";

const text = STRINGS.runs;
const { data: dataText, model: modelText, fit: fitText } = STRINGS;

function scatteringName(id: string | null): string {
  if (id === null) {
    return text.noScattering;
  }
  const known: Record<string, string> = modelText.scatteringNames;
  return known[id] ?? id;
}

/**
 * What tells a run from every other in this tab: when it ended and its number, as numbering
 * starts again with a restored session.
 */
function runKey(run: FitRun): string {
  return `${run.finishedAt}#${String(run.number)}`;
}

/** A run's mode in the model descriptions, if the server still offers it. */
function modeOf(run: FitRun, models: readonly ModelDescription[] | undefined) {
  return fitModeOf(
    models?.find(({ id }) => id === run.selection.model),
    run.selection.fitMode,
  );
}

/**
 * A run's name: its number and time, and what tells it from the others, its mode and scattering,
 * and whether it is the result now on the fit screen.
 */
function runName(
  run: FitRun,
  mode: FitModeDescription | undefined,
  current: FitResult | null,
): string {
  return text.runName(
    run.number,
    new Date(run.finishedAt).toLocaleTimeString("en-GB"),
    [
      mode === undefined ? null : modeLabel(mode),
      run.selection.scattering === null
        ? null
        : scatteringName(run.selection.scattering),
    ]
      .filter((part) => part !== null)
      .join(", "),
    run.result === current,
  );
}

/** The request of a run's curve: its values over the points it was fit to. */
function requestOf(
  run: FitRun | undefined,
  models: readonly ModelDescription[] | undefined,
): CalcRequest | null {
  const mode = run === undefined ? undefined : modeOf(run, models);
  return run === undefined || mode === undefined
    ? null
    : calcRequest(
        {
          selection: run.selection,
          parameters: { [mode.id]: run.parameters },
          data: run.data,
          interpolation: run.interpolation,
        },
        models,
      );
}

/**
 * The curve of a run's values over its own points, with their RMSE, asked once: a run never
 * changes, so neither does its answer.
 */
function useRunCurve(request: CalcRequest | null, run: FitRun | undefined) {
  return useQuery({
    queryKey: ["run-curve", run === undefined ? null : runKey(run)],
    queryFn: () =>
      request === null ? Promise.resolve(null) : apiClient.postCalc(request),
    enabled: request !== null,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}

/** The status of a run's fit in the words the fit screen uses, not its code. */
function statusText(run: FitRun, mode: FitModeDescription | undefined) {
  const badge = fitBadge(
    { status: "done", result: run.result },
    mode?.iterative === true,
    mode?.threshold ?? null,
  );
  if (badge === null) {
    return text.none;
  }
  const words = STRINGS.status[badge.status];
  return badge.detail === undefined ? words : `${words} ${badge.detail}`;
}

function methodText(run: FitRun): string {
  switch (run.result.algorithm) {
    case "verified-sequential-v2":
      return fitText.algorithm.verified;
    case "legacy-sequential-v1":
      return fitText.algorithm.legacy;
    default:
      return fitText.algorithm.unknown;
  }
}

function rangeText(run: FitRun): string {
  const { minTemperatureK: low, maxTemperatureK: high } = run.selection;
  return low === null || high === null
    ? text.none
    : text.rangeValue(formatNumber(low), formatNumber(high));
}

/** Whether two requests fit the same points, whatever their values. */
function samePoints(a: CalcRequest | null, b: CalcRequest | null): boolean {
  return (
    a !== null &&
    b !== null &&
    JSON.stringify(a.measurements) === JSON.stringify(b.measurements)
  );
}

function RunSelect({
  label,
  runs,
  names,
  value,
  onChange,
}: {
  label: string;
  runs: readonly FitRun[];
  names: ReadonlyMap<FitRun, string>;
  value: string;
  onChange: (run: string) => void;
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted-foreground">
      {label}
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {runs.map((run) => (
            <SelectItem key={runKey(run)} value={runKey(run)}>
              {names.get(run)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}

function rowsOf(
  run: FitRun,
  mode: FitModeDescription | undefined,
): ParameterRow[] {
  return mode === undefined
    ? []
    : parameterRows(
        mode,
        run.selection.scattering,
        run.parameters,
        { status: "done", result: run.result },
        run.customBounds,
        run.held,
      );
}

function Cell({ row }: { row: ParameterRow | undefined }) {
  if (row === undefined) {
    return <TableCell className="text-muted-foreground">{text.none}</TableCell>;
  }
  return (
    <TableCell>
      <span className="inline-flex flex-wrap items-center gap-1.5">
        <span className="font-mono">{row.value}</span>
        <ParameterStatusBadge status={row.status} />
      </span>
    </TableCell>
  );
}

/**
 * One chart of a quantity both runs fit: the points each was fit to, as the RMSE compares with
 * them, and each run's curve, A solid and B dashed.
 */
function QuantityChart({
  quantity,
  nameA,
  nameB,
  requestA,
  requestB,
  curveA,
  curveB,
}: {
  quantity: Quantity;
  nameA: string;
  nameB: string;
  requestA: CalcRequest | null;
  requestB: CalcRequest | null;
  curveA: CalcResponse | null | undefined;
  curveB: CalcResponse | null | undefined;
}) {
  const { curve, factor, axis } = quantityChart(quantity);
  const scaled = (values: readonly (number | null)[]) =>
    values.map((value) => (value === null ? null : value * factor));
  const pointsOf = (request: CalcRequest | null, name: string) => {
    const points = request?.measurements?.[quantity];
    return points === undefined
      ? null
      : {
          label: text.pointsOf(name),
          temperatureK: points.temperature_k,
          values: scaled(points.values),
        };
  };
  const curveOf = (
    answer: CalcResponse | null | undefined,
    name: string,
    dashed: boolean,
  ) => {
    const values = answer?.curves[curve];
    return answer == null || values === undefined
      ? []
      : [
          {
            id: dashed ? "run-b" : "run-a",
            label: name,
            temperatureK: answer.temperature_k,
            values: scaled(values),
            color: dashed ? ("orange" as const) : ("blue" as const),
            dashed,
          },
        ];
  };
  const own = samePoints(requestA, requestB);
  return (
    <figure className="m-0 min-w-0 flex-[1_1_320px]">
      <figcaption className="text-sm font-medium">
        {dataText.quantities[quantity].title}
      </figcaption>
      <TransportChart
        curves={[
          ...curveOf(curveA, nameA, false),
          ...curveOf(curveB, nameB, true),
        ]}
        measurements={pointsOf(requestA, own ? text.bothRuns : nameA)}
        // Run B's own points, when they are not run A's.
        interpolated={own ? null : pointsOf(requestB, nameB)}
        xAxisTitle={STRINGS.chart.temperatureAxis}
        yAxisTitle={axis}
        description={text.chartDescription(
          dataText.quantities[quantity].title,
          nameA,
          nameB,
        )}
        failedText={STRINGS.chart.failed}
      />
    </figure>
  );
}

/**
 * Fits that ended in this session, each kept as it was, and two of them side by side: their
 * settings, statuses, RMSE, parameters and curves. The run that is the result now on the fit
 * screen says so; the others are earlier fits, never the result of the current values. It is not
 * printed, as the report is of the current result.
 */
export function RunComparison() {
  const runs = useSessionStore((state) => state.runs);
  const fit = useSessionStore((state) => state.fit);
  const { data: models } = useQuery(modelsQuery);
  // By `runKey`, which no other run of any session in this tab shares.
  const [chosenA, setA] = useState<string | null>(null);
  const [chosenB, setB] = useState<string | null>(null);
  const a = runs.find((run) => runKey(run) === chosenA) ?? runs.at(-2);
  const b = runs.find((run) => runKey(run) === chosenB) ?? runs.at(-1);
  const requestA = requestOf(a, models?.models);
  const requestB = requestOf(b, models?.models);
  const curveA = useRunCurve(requestA, a);
  const curveB = useRunCurve(requestB, b);

  if (runs.length === 0) {
    return null;
  }
  const current = fit.status === "done" ? fit.result : null;
  const names = new Map(
    runs.map((run) => [
      run,
      runName(run, modeOf(run, models?.models), current),
    ]),
  );
  const subtitle = runs.length < 2 ? text.oneRun : text.subtitle(runs.length);
  if (a === undefined || b === undefined || runs.length < 2) {
    return (
      <div className="print:hidden">
        <Panel title={text.title} subtitle={subtitle}>
          <p className="m-0 mt-2 text-sm text-muted-foreground">{text.note}</p>
        </Panel>
      </div>
    );
  }

  const nameA = names.get(a) ?? "";
  const nameB = names.get(b) ?? "";
  const modeA = modeOf(a, models?.models);
  const modeB = modeOf(b, models?.models);
  const rowsA = rowsOf(a, modeA);
  const rowsB = rowsOf(b, modeB);
  const parameterNames = [
    ...new Set([...rowsA, ...rowsB].map(({ name }) => name)),
  ];
  const symbolOf = (name: string) =>
    [...rowsA, ...rowsB].find((row) => row.name === name)?.symbol ?? name;
  const quantities = (modeA?.quantities ?? []).filter((quantity) =>
    modeB?.quantities.includes(quantity),
  );
  const rmseOf = (
    answer: CalcResponse | null | undefined,
    quantity: Quantity,
  ) => {
    const rmse = answer?.rmse[quantity];
    return rmse === undefined ? text.none : rmseText(rmse);
  };
  const facts: { label: string; a: string; b: string }[] = [
    {
      label: text.mode,
      a: modeA === undefined ? text.notOffered : modeLabel(modeA),
      b: modeB === undefined ? text.notOffered : modeLabel(modeB),
    },
    {
      label: text.scattering,
      a: scatteringName(a.selection.scattering),
      b: scatteringName(b.selection.scattering),
    },
    { label: text.range, a: rangeText(a), b: rangeText(b) },
    {
      label: text.interpolation,
      a: a.interpolation.enabled ? text.on : text.off,
      b: b.interpolation.enabled ? text.on : text.off,
    },
    { label: text.method, a: methodText(a), b: methodText(b) },
    {
      label: text.coreVersion,
      a: a.result.core_version ?? text.none,
      b: b.result.core_version ?? text.none,
    },
    { label: text.status, a: statusText(a, modeA), b: statusText(b, modeB) },
    {
      label: text.iterations,
      a: a.result.iterations == null ? text.none : String(a.result.iterations),
      b: b.result.iterations == null ? text.none : String(b.result.iterations),
    },
    ...quantities.map((quantity) => ({
      // As the results name it, 1/σ for ρ from a σ file.
      label: text.rmse(rmseSymbol(quantity, a.data)),
      a: rmseOf(curveA.data, quantity),
      b: rmseOf(curveB.data, quantity),
    })),
  ];
  const otherPoints = !samePoints(requestA, requestB);

  return (
    <div className="print:hidden">
      <Panel title={text.title} subtitle={subtitle}>
        <p className="m-0 mt-2 text-sm text-muted-foreground">{text.note}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <RunSelect
            label={text.runA}
            runs={runs}
            names={names}
            value={runKey(a)}
            onChange={setA}
          />
          <RunSelect
            label={text.runB}
            runs={runs}
            names={names}
            value={runKey(b)}
            onChange={setB}
          />
        </div>
        {a === b && (
          <p className="m-0 mt-2 text-sm text-muted-foreground">
            {text.sameRun}
          </p>
        )}
        {a !== b && otherPoints && (
          <p
            role="note"
            className="m-0 mt-2 text-sm text-warning-badge-foreground"
          >
            {text.otherPoints}
          </p>
        )}
        <div className="mt-3">
          <Table aria-label={text.table}>
            <TableHeader>
              <TableRow>
                <TableHead>{text.what}</TableHead>
                <TableHead>{nameA}</TableHead>
                <TableHead>{nameB}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {facts.map((fact) => (
                <TableRow key={fact.label}>
                  <TableCell className="font-medium">
                    <Subscripted text={fact.label} />
                  </TableCell>
                  <TableCell>
                    <Subscripted text={fact.a} />
                  </TableCell>
                  <TableCell>
                    <Subscripted text={fact.b} />
                  </TableCell>
                </TableRow>
              ))}
              {parameterNames.map((name) => (
                <TableRow key={name}>
                  <TableCell className="font-medium">
                    {symbolOf(name)}
                  </TableCell>
                  <Cell row={rowsA.find((row) => row.name === name)} />
                  <Cell row={rowsB.find((row) => row.name === name)} />
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="m-0 mt-2 text-xs text-muted-foreground">
            {text.dashNote}
          </p>
        </div>
        {(curveA.isError || curveB.isError) && (
          <p className="m-0 mt-2 text-xs text-muted-foreground">
            {text.curveFailed}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-3">
          {quantities.map((quantity) => (
            <QuantityChart
              key={quantity}
              quantity={quantity}
              nameA={nameA}
              nameB={nameB}
              requestA={requestA}
              requestB={requestB}
              curveA={curveA.data}
              curveB={curveB.data}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
}
