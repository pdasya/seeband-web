import type { CalcResponse } from "@/api/client";
import { quantityCurve, type EnergyDisplay } from "@/model/chartTabs";
import {
  coreToDisplay,
  parameterSymbol,
  parameterValues,
  visibleParameters,
} from "@/model/parameters";
import { hasFittedValues, type ResultIssue } from "@/model/resultSummary";
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
    case "waiting":
      return text.header.running(null);
    case "running":
      return text.header.running(fit.iteration);
    case "failed":
      return text.header.failed;
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
 * Whether the interpolated values are those a fit uses now: not while new ones for another range
 * are on their way, as the session treats them then.
 */
function inUse(interpolation: SessionState["interpolation"]): boolean {
  return interpolation.enabled && !interpolation.loading;
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
    const interpolated = inUse(session.interpolation)
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

interface ParameterRecord {
  name: string;
  symbol: string;
  meaning: string;
  unit: string;
  /** As the screen shows it, in the unit of its control. */
  value: number;
  status: string;
}

/** The values in use, as the user sees them, with how each was found. */
function parameterRecords(
  mode: FitModeDescription,
  scattering: string | null,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
  held: readonly string[],
): ParameterRecord[] {
  const values = parameterValues(mode, saved);
  const atBounds =
    fit.status === "done" && fit.result.status !== "failed"
      ? fit.result.at_bounds
      : [];
  const units: Record<string, string | undefined> = text.units;
  const fitted = hasFittedValues(fit);
  return visibleParameters(mode, scattering).map((parameter) => {
    const value = values[parameter.name] ?? parameter.core_range.default;
    return {
      name: parameter.name,
      symbol: parameterSymbol(parameter.name),
      meaning: parameter.meaning,
      unit: units[parameter.display_unit] ?? parameter.display_unit,
      value: coreToDisplay(parameter, value),
      // With no fit, a value the mode fits is the user's, so a file read alone does not mislead.
      status:
        parameter.role === "fixed"
          ? text.status.fixed
          : held.includes(parameter.name)
            ? text.status.held
            : !fitted
              ? text.status.free
              : atBounds.includes(parameter.name)
                ? text.status.atBound
                : text.status.fitted,
    };
  });
}

type DegeneracySelection = Pick<
  Selection,
  "scattering" | "band1Degeneracy" | "band2Degeneracy"
>;

function hasDegeneracy(mode: FitModeDescription): boolean {
  return mode.degeneracy !== null && mode.degeneracy !== undefined;
}

/** The values in use as text, a line each, as the desktop's parameter file has them. */
export function parametersFile(
  header: readonly string[],
  mode: FitModeDescription,
  selection: DegeneracySelection,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
  held: readonly string[] = [],
): string {
  const lines = parameterRecords(
    mode,
    selection.scattering,
    saved,
    fit,
    held,
  ).map(({ symbol, meaning, unit, value, status }) =>
    [text.parameter(symbol, meaning, unit), numberText(value), status].join(
      "\t",
    ),
  );
  const degeneracy = hasDegeneracy(mode)
    ? [
        [
          text.parameter("N1, N2", fitText.degeneracyMeaning, ""),
          `${numberText(selection.band1Degeneracy)}, ${numberText(selection.band2Degeneracy)}`,
          text.status.fixed,
        ].join("\t"),
      ]
    : [];
  return (
    commented(header) +
    [text.parameterColumns, ...lines, ...degeneracy].join("\n") +
    "\n"
  );
}

/** A field of a CSV, quoted when it holds a comma, a quote or a line break, as RFC 4180 asks. */
export function csvField(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

/** The values in use as a CSV, a row each, with N1 and N2 as rows of their own. */
export function parametersCsv(
  header: readonly string[],
  mode: FitModeDescription,
  selection: DegeneracySelection,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
  held: readonly string[] = [],
): string {
  const records = [
    ...parameterRecords(mode, selection.scattering, saved, fit, held),
    ...(hasDegeneracy(mode)
      ? [
          {
            name: "band_1_degeneracy",
            symbol: "N1",
            meaning: fitText.degeneracyMeaning,
            unit: "",
            value: selection.band1Degeneracy,
            status: text.status.fixed,
          },
          {
            name: "band_2_degeneracy",
            symbol: "N2",
            meaning: fitText.degeneracyMeaning,
            unit: "",
            value: selection.band2Degeneracy,
            status: text.status.fixed,
          },
        ]
      : []),
  ];
  const rows = records.map((record) =>
    [
      record.name,
      record.symbol,
      record.meaning,
      record.unit,
      numberText(record.value),
      record.status,
    ]
      .map(csvField)
      .join(","),
  );
  return (
    commented(header) + [text.parameterCsvColumns, ...rows].join("\n") + "\n"
  );
}

/** The curves of one additional graph, on one temperature grid, with the API's own names. */
export function graphFile(
  header: readonly string[],
  temperatureK: readonly number[],
  curves: readonly { name: string; values: readonly (number | null)[] }[],
  energy: EnergyDisplay,
): string {
  const labels: Record<string, string | undefined> = text.curves;
  const energyLabels: Record<string, ((unit: string) => string) | undefined> =
    text.energyCurves;
  return (
    commented(header) +
    table([
      { legend: text.columns.temperature, values: temperatureK },
      ...curves.map(({ name, values }) => {
        // An energy is in the unit the screen shows, as the parameters are.
        const energyLabel = energyLabels[name];
        return energyLabel === undefined
          ? { legend: labels[name] ?? name, values }
          : {
              legend: energyLabel(energy.unit),
              values: values.map((value) =>
                value === null ? null : value * energy.per_kelvin,
              ),
            };
      }),
    ])
  );
}

type CurveKindOfFile = "experimental" | "interpolated" | "pre_fit" | "fit";

/** Every series of the mode's quantities, as one list, for the files that are not side by side. */
function series(
  mode: FitModeDescription,
  session: Pick<SessionState, "data" | "interpolation">,
  preFit: CalcResponse | null,
  fitted: CalcResponse | null,
): {
  quantity: Quantity;
  curve: CurveKindOfFile;
  temperatureK: readonly number[];
  values: readonly (number | null)[];
}[] {
  return mode.quantities.flatMap((quantity) => {
    const column = quantityCurve(quantity);
    const measured = session.data[quantity]?.measurement;
    const interpolated = inUse(session.interpolation)
      ? session.interpolation.values[quantity]
      : undefined;
    const of = (
      curve: CurveKindOfFile,
      temperatureK: readonly number[] | undefined,
      values: readonly (number | null)[] | undefined,
    ) =>
      temperatureK === undefined || values === undefined
        ? []
        : [{ quantity, curve, temperatureK, values }];
    return [
      ...of("experimental", measured?.temperature_k, measured?.values),
      ...of("interpolated", interpolated?.temperature_k, interpolated?.values),
      ...of("pre_fit", preFit?.temperature_k, preFit?.curves[column]),
      ...of("fit", fitted?.temperature_k, fitted?.curves[column]),
    ];
  });
}

/** One table of every point, a row each, for a program such as pandas or R. */
export function csvFile(
  header: readonly string[],
  mode: FitModeDescription,
  session: Pick<SessionState, "data" | "interpolation">,
  preFit: CalcResponse | null,
  fitted: CalcResponse | null,
): string {
  const units: Record<Quantity, string> = text.quantityUnits;
  const rows = series(mode, session, preFit, fitted).flatMap(
    ({ quantity, curve, temperatureK, values }) =>
      temperatureK.map((temperature, at) =>
        [
          quantity,
          curve,
          numberText(temperature),
          numberText(values[at] ?? null),
          units[quantity],
        ].join(","),
      ),
  );
  return commented(header) + [text.csvColumns, ...rows].join("\n") + "\n";
}

/** A temperature column and others on its grid, with names the app's parser reads back. */
function readableTable(
  temperatureK: readonly number[],
  columns: readonly {
    quantity: Quantity;
    values: readonly (number | null)[];
  }[],
): string {
  return table([
    { legend: text.readable.temperature, values: temperatureK },
    ...columns.map(({ quantity, values }) => ({
      legend: text.readable[quantity],
      values,
    })),
  ]);
}

/**
 * The files of a ZIP: each a plain table. The measured data and the curves have the app's own
 * column names, so a file of them loads again.
 */
export function zipEntries(
  header: readonly string[],
  mode: FitModeDescription,
  session: Pick<SessionState, "data" | "interpolation">,
  preFit: CalcResponse | null,
  fitted: CalcResponse | null,
  parameters: string,
  graphs: readonly { kind: string; result: CalcResponse }[],
  energy: EnergyDisplay,
  /** Kinds the mode offers that have no curve here, so that metadata says why a file is missing. */
  missing: readonly string[] = [],
): Record<string, string> {
  const head = commented(header);
  const entries: Record<string, string> = {
    [text.zip.metadata]: [
      ...header,
      ...missing.map((kind) => text.zip.missing(text.zip.graph(kind))),
    ]
      .map((line) => `${line}\n`)
      .join(""),
    [text.zip.parameters]: parameters,
  };
  for (const { quantity, curve, temperatureK, values } of series(
    mode,
    session,
    null,
    null,
  )) {
    entries[text.zip.data(quantity, curve === "interpolated")] =
      head + readableTable(temperatureK, [{ quantity, values }]);
  }
  for (const [name, result] of [
    [text.zip.preFit, preFit],
    [text.zip.fit, fitted],
  ] as const) {
    if (result !== null) {
      entries[name] =
        head +
        readableTable(
          result.temperature_k,
          mode.quantities.flatMap((quantity) => {
            const values = result.curves[quantityCurve(quantity)];
            return values === undefined ? [] : [{ quantity, values }];
          }),
        );
    }
  }
  for (const { kind, result } of graphs) {
    entries[text.zip.graph(kind)] = graphFile(
      header,
      result.temperature_k,
      Object.entries(result.curves).map(([name, values]) => ({
        name,
        values,
      })),
      energy,
    );
  }
  return entries;
}
