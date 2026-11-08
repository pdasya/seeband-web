import type { CalcResponse } from "@/api/client";
import { quantityCurve } from "@/model/chartTabs";
import {
  coreToDisplay,
  parameterSymbol,
  parameterValues,
  visibleParameters,
} from "@/model/parameters";
import type { ResultIssue } from "@/model/resultSummary";
import type { FitModeDescription } from "@/model/selection";
import type {
  FitState,
  Quantity,
  Selection,
  SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { export: text, fit: fitText } = STRINGS;

/** A column of a file: its heading, with the unit, and its values. */
export interface ExportColumn {
  legend: string;
  values: readonly (number | null)[];
}

/**
 * Numbers as a program reads them back: a decimal point, full precision, and nothing for a value
 * that is not finite. The screen's decimal comma is for people.
 */
export function numberText(value: number | null): string {
  return value === null || !Number.isFinite(value) ? "" : String(value);
}

/**
 * Columns side by side, as the desktop's `save_data` writes them: a tab between columns, a line
 * of headings, and an empty field where a column is shorter than the longest.
 */
export function table(columns: readonly ExportColumn[]): string {
  const rows = Math.max(0, ...columns.map(({ values }) => values.length));
  const lines = [columns.map(({ legend }) => legend).join("\t")];
  for (let row = 0; row < rows; row += 1) {
    lines.push(
      columns
        .map(({ values }) =>
          row < values.length ? numberText(values[row] ?? null) : "",
        )
        .join("\t"),
    );
  }
  return `${lines.join("\n")}\n`;
}

/** Lines that a reader, and the app's own parser, take as comments. */
export function commented(lines: readonly string[]): string {
  return lines.map((line) => `# ${line}\n`).join("");
}

export interface ExportContext {
  appVersion: string;
  apiVersion: string | null;
  /** When the file was made, as ISO 8601. */
  date: string;
  modelId: string;
  modeLabel: string;
  selection: Selection;
  /** Whether the mode has band degeneracies, which only a model with two bands has. */
  degeneracy: boolean;
  fit: FitState;
  demo: boolean;
  issues: readonly ResultIssue[];
}

function fitLine(fit: FitState): string {
  switch (fit.status) {
    case "done":
      return text.header.fit(fit.result.status, fit.result.iterations ?? null);
    case "stopped":
      return text.header.fit("stopped", fit.iteration);
    default:
      return text.header.noFit;
  }
}

/** What a file is of: the app, the model and fit, and what is known to be wrong with it. */
export function exportHeader(context: ExportContext): string[] {
  const { selection } = context;
  return [
    text.header.app(context.appVersion, context.apiVersion),
    text.header.date(context.date),
    ...(context.demo ? [text.header.demo] : []),
    text.header.model(context.modelId.toUpperCase(), context.modeLabel),
    ...(selection.scattering === null
      ? []
      : [text.header.scattering(selection.scattering)]),
    ...(selection.minTemperatureK === null || selection.maxTemperatureK === null
      ? []
      : [
          text.header.range(
            numberText(selection.minTemperatureK),
            numberText(selection.maxTemperatureK),
          ),
        ]),
    ...(context.degeneracy
      ? [
          text.header.degeneracies(
            numberText(selection.band1Degeneracy),
            numberText(selection.band2Degeneracy),
          ),
        ]
      : []),
    fitLine(context.fit),
    ...context.issues.map(({ id, severity, text: issue }) =>
      text.header.issue(fitText.issueSeverity[severity], issue, id),
    ),
  ];
}

/** The label of a fit mode in a file, from the symbols of its quantities. */
export function modeLabel(mode: FitModeDescription): string {
  return mode.quantities
    .map((quantity: Quantity) => STRINGS.data.quantities[quantity].symbol)
    .join(" + ");
}

function pair(
  legend: string,
  temperatureK: readonly number[],
  values: readonly (number | null)[] | undefined,
): ExportColumn[] {
  return values === undefined
    ? []
    : [
        { legend: text.columns.temperature, values: temperatureK },
        { legend, values },
      ];
}

/**
 * The data and curves of each quantity of the mode, as the desktop's data file has them: measured
 * points, then the interpolated values a fit used, the curve before the fit, and the fitted one.
 */
export function dataFile(
  header: readonly string[],
  mode: FitModeDescription,
  session: Pick<SessionState, "data" | "interpolation">,
  preFit: CalcResponse | null,
  fitted: CalcResponse | null,
): string {
  const columns = mode.quantities.flatMap((quantity) => {
    const name = text.quantities[quantity];
    const curve = quantityCurve(quantity);
    const measured = session.data[quantity]?.measurement;
    const interpolated = session.interpolation.enabled
      ? session.interpolation.values[quantity]
      : undefined;
    return [
      ...(measured === undefined
        ? []
        : pair(
            text.columns.experimental(name),
            measured.temperature_k,
            measured.values,
          )),
      ...(interpolated === undefined
        ? []
        : pair(
            text.columns.interpolated(name),
            interpolated.temperature_k,
            interpolated.values,
          )),
      ...(preFit === null
        ? []
        : pair(
            text.columns.preFit(name),
            preFit.temperature_k,
            preFit.curves[curve],
          )),
      ...(fitted === null
        ? []
        : pair(
            text.columns.fit(name),
            fitted.temperature_k,
            fitted.curves[curve],
          )),
    ];
  });
  return commented(header) + table(columns);
}

/** The values in use, as the user sees them, with how each was found. */
export function parametersFile(
  header: readonly string[],
  mode: FitModeDescription,
  selection: Pick<
    Selection,
    "scattering" | "band1Degeneracy" | "band2Degeneracy"
  >,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
): string {
  const values = parameterValues(mode, saved);
  const atBounds =
    fit.status === "done" && fit.result.status !== "failed"
      ? fit.result.at_bounds
      : [];
  const units: Record<string, string | undefined> = text.units;
  const lines = visibleParameters(mode, selection.scattering).map(
    (parameter) => {
      const value = values[parameter.name] ?? parameter.core_range.default;
      const status =
        parameter.role === "fixed"
          ? text.status.fixed
          : atBounds.includes(parameter.name)
            ? text.status.atBound
            : text.status.fitted;
      return [
        text.parameter(
          parameterSymbol(parameter.name),
          parameter.meaning,
          units[parameter.unit] ?? parameter.unit,
        ),
        numberText(coreToDisplay(parameter, value)),
        status,
      ].join("\t");
    },
  );
  const degeneracy =
    mode.degeneracy === null || mode.degeneracy === undefined
      ? []
      : [
          [
            text.parameter("N1, N2", fitText.degeneracyMeaning, ""),
            `${numberText(selection.band1Degeneracy)}, ${numberText(selection.band2Degeneracy)}`,
            text.status.fixed,
          ].join("\t"),
        ];
  return (
    commented(header) +
    [text.parameterColumns, ...lines, ...degeneracy].join("\n") +
    "\n"
  );
}

/** The curves of one additional graph, on one temperature grid, with the API's own names. */
export function graphFile(
  header: readonly string[],
  temperatureK: readonly number[],
  curves: readonly { name: string; values: readonly (number | null)[] }[],
): string {
  const labels: Record<string, string | undefined> = text.curves;
  return (
    commented(header) +
    table([
      { legend: text.columns.temperature, values: temperatureK },
      ...curves.map(({ name, values }) => ({
        legend: labels[name] ?? name,
        values,
      })),
    ])
  );
}
