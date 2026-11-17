import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient, type CalcResponse } from "@/api/client";
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
import { quantityChart } from "@/model/chartTabs";
import { modeLabel } from "@/model/exportFiles";
import { calcRequest } from "@/model/liveCurves";
import { ParameterStatusBadge } from "@/model/ParameterStatusBadge";
import {
  parameterRows,
  rmseText,
  type ParameterRow,
} from "@/model/resultSummary";
import { fitModeOf, type ModelDescription } from "@/model/selection";
import { useSessionStore, type FitRun, type Quantity } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const text = STRINGS.runs;
const { data: dataText, model: modelText } = STRINGS;

function scatteringName(id: string | null): string {
  if (id === null) {
    return text.noScattering;
  }
  const known: Record<string, string> = modelText.scatteringNames;
  return known[id] ?? id;
}

function runName(run: FitRun): string {
  return text.runName(
    run.number,
    new Date(run.finishedAt).toLocaleTimeString("en-GB"),
  );
}

/** A run's mode in the model descriptions, if the server still offers it. */
function modeOf(run: FitRun, models: readonly ModelDescription[] | undefined) {
  return fitModeOf(
    models?.find(({ id }) => id === run.selection.model),
    run.selection.fitMode,
  );
}

/**
 * The curve of a run's values over its own data, with their RMSE, asked once: a run never
 * changes, so neither does its answer.
 */
function useRunCurve(run: FitRun | undefined) {
  const { data: models } = useQuery(modelsQuery);
  const mode = fitModeOf(
    models?.models.find(({ id }) => id === run?.selection.model),
    run?.selection.fitMode ?? null,
  );
  const request =
    run === undefined || mode === undefined
      ? null
      : calcRequest(
          {
            selection: run.selection,
            parameters: { [mode.id]: run.parameters },
            data: run.data,
            interpolation: run.interpolation,
          },
          models?.models,
        );
  return useQuery({
    queryKey: ["run-curve", run?.finishedAt, run?.number],
    queryFn: () =>
      request === null ? Promise.resolve(null) : apiClient.postCalc(request),
    enabled: request !== null,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}

function RunSelect({
  label,
  runs,
  value,
  onChange,
}: {
  label: string;
  runs: readonly FitRun[];
  value: number;
  onChange: (run: number) => void;
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted-foreground">
      {label}
      <Select
        value={String(value)}
        onValueChange={(chosen) => {
          onChange(Number(chosen));
        }}
      >
        <SelectTrigger className="w-full" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {runs.map((run) => (
            <SelectItem key={run.number} value={String(run.number)}>
              {runName(run)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}

function rowsOf(
  run: FitRun,
  models: readonly ModelDescription[] | undefined,
): ParameterRow[] {
  const mode = modeOf(run, models);
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

/** One chart of a quantity both runs fit: the points of run A's data, and each run's curve. */
function QuantityChart({
  quantity,
  a,
  b,
  curveA,
  curveB,
}: {
  quantity: Quantity;
  a: FitRun;
  b: FitRun;
  curveA: CalcResponse | null | undefined;
  curveB: CalcResponse | null | undefined;
}) {
  const { curve, factor, axis } = quantityChart(quantity);
  const entry = a.data[quantity]?.measurement;
  const scaled = (values: readonly (number | null)[]) =>
    values.map((value) => (value === null ? null : value * factor));
  const curveOf = (
    answer: CalcResponse | null | undefined,
    run: FitRun,
    dashed: boolean,
  ) => {
    const values = answer?.curves[curve];
    return answer == null || values === undefined
      ? []
      : [
          {
            id: `run-${String(run.number)}`,
            label: runName(run),
            temperatureK: answer.temperature_k,
            values: scaled(values),
            color: dashed ? ("orange" as const) : ("blue" as const),
            dashed,
          },
        ];
  };
  return (
    <figure className="m-0 min-w-0 flex-[1_1_320px]">
      <figcaption className="text-sm font-medium">
        {dataText.quantities[quantity].title}
      </figcaption>
      <TransportChart
        curves={[...curveOf(curveA, a, false), ...curveOf(curveB, b, true)]}
        measurements={
          entry === undefined
            ? null
            : {
                label: text.pointsOf(runName(a)),
                temperatureK: entry.temperature_k,
                values: scaled(entry.values),
              }
        }
        xAxisTitle={STRINGS.chart.temperatureAxis}
        yAxisTitle={axis}
        description={text.chartDescription(
          dataText.quantities[quantity].title,
          runName(a),
          runName(b),
        )}
        failedText={STRINGS.chart.failed}
      />
    </figure>
  );
}

/**
 * Fits that ended in this session, each kept as it was, and two of them side by side: their
 * settings, statuses, RMSE, parameters and curves. They are earlier fits, never the result of the
 * values now on the fit screen, and the section says so.
 */
export function RunComparison() {
  const runs = useSessionStore((state) => state.runs);
  const data = useSessionStore((state) => state.data);
  const { data: models } = useQuery(modelsQuery);
  const last = runs.at(-1)?.number ?? 0;
  const [chosenA, setA] = useState<number | null>(null);
  const [chosenB, setB] = useState<number | null>(null);
  const numberA = chosenA ?? runs.at(-2)?.number ?? last;
  const numberB = chosenB ?? last;
  const a = runs.find(({ number }) => number === numberA) ?? runs.at(-2);
  const b = runs.find(({ number }) => number === numberB) ?? runs.at(-1);
  const curveA = useRunCurve(a);
  const curveB = useRunCurve(b);

  if (runs.length === 0) {
    return null;
  }
  const subtitle = runs.length < 2 ? text.oneRun : text.subtitle(runs.length);
  if (a === undefined || b === undefined || runs.length < 2) {
    return (
      <Panel title={text.title} subtitle={subtitle}>
        <p className="m-0 mt-2 text-sm text-muted-foreground">{text.note}</p>
      </Panel>
    );
  }

  const modeA = modeOf(a, models?.models);
  const modeB = modeOf(b, models?.models);
  const rowsA = rowsOf(a, models?.models);
  const rowsB = rowsOf(b, models?.models);
  const names = [...new Set([...rowsA, ...rowsB].map(({ name }) => name))];
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
    {
      label: text.method,
      a: a.result.algorithm ?? text.none,
      b: b.result.algorithm ?? text.none,
    },
    {
      label: text.status,
      a: a.result.status,
      b: b.result.status,
    },
    {
      label: text.iterations,
      a: a.result.iterations == null ? text.none : String(a.result.iterations),
      b: b.result.iterations == null ? text.none : String(b.result.iterations),
    },
    ...quantities.map((quantity) => ({
      label: text.rmse(dataText.quantities[quantity].symbol),
      a: rmseOf(curveA.data, quantity),
      b: rmseOf(curveB.data, quantity),
    })),
  ];

  return (
    <Panel title={text.title} subtitle={subtitle}>
      <p className="m-0 mt-2 text-sm text-muted-foreground">{text.note}</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <RunSelect
          label={text.runA}
          runs={runs}
          value={a.number}
          onChange={setA}
        />
        <RunSelect
          label={text.runB}
          runs={runs}
          value={b.number}
          onChange={setB}
        />
      </div>
      {a.data !== b.data && (
        <p
          role="note"
          className="m-0 mt-2 text-sm text-warning-badge-foreground"
        >
          {text.otherData}
        </p>
      )}
      {(a.data !== data || b.data !== data) && (
        <p className="m-0 mt-2 text-xs text-muted-foreground">
          {text.dataSince}
        </p>
      )}
      <div className="mt-3">
        <Table aria-label={text.table}>
          <TableHeader>
            <TableRow>
              <TableHead>{text.what}</TableHead>
              <TableHead>{runName(a)}</TableHead>
              <TableHead>{runName(b)}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {facts.map((fact) => (
              <TableRow key={fact.label}>
                <TableCell className="font-medium">{fact.label}</TableCell>
                <TableCell>{fact.a}</TableCell>
                <TableCell>{fact.b}</TableCell>
              </TableRow>
            ))}
            {names.map((name) => (
              <TableRow key={name}>
                <TableCell className="font-medium">{symbolOf(name)}</TableCell>
                <Cell row={rowsA.find((row) => row.name === name)} />
                <Cell row={rowsB.find((row) => row.name === name)} />
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {(curveA.isError || curveB.isError) && (
        <p className="m-0 mt-2 text-xs text-muted-foreground">
          {text.curveFailed}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-3 print:hidden">
        {quantities.map((quantity) => (
          <QuantityChart
            key={quantity}
            quantity={quantity}
            a={a}
            b={b}
            curveA={curveA.data}
            curveB={curveB.data}
          />
        ))}
      </div>
    </Panel>
  );
}
