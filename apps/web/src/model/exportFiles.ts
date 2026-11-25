import type { CalcResponse } from "@/api/client";
import {
  LORENZ_L0,
  quantityCurve,
  type EnergyDisplay,
} from "@/model/chartTabs";
import {
  coreToDisplay,
  parameterSymbol,
  parameterValues,
  visibleParameters,
} from "@/model/parameters";
import {
  foundStatus,
  hasFittedValues,
  type ResultIssue,
} from "@/model/resultSummary";
import type { FitModeDescription } from "@/model/selection";
import {
  fitAlgorithm,
  type FitState,
  type Quantity,
  type Selection,
  type SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";
import type { LimitedRange } from "@/model/interpolatedRanges";

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
  serverCoreVersion?: string | null;
  curveCoreVersions?: readonly (string | undefined)[];
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
  /** Quantities whose data narrowed their interpolation, and the range a fit used. */
  limitedRanges?: readonly LimitedRange[];
  /** Whether ρ is 1/σ of a σ file, as its points and RMSE are then not what was loaded. */
  fromConductivity?: boolean;
  /** What the run used, so that it can be made again: see `runLines`. */
  run?: readonly string[];
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

/** Source versions stay distinct: a newly deployed server does not relabel an old fit. */
export function coreVersionLines(
  serverVersion: string | null | undefined,
  fit: FitState,
  curveVersions: readonly (string | undefined)[] = [],
): string[] {
  return [
    text.header.serverCore(serverVersion ?? text.header.unknownVersion),
    ...(fit.status === "done"
      ? [
          text.header.fitCore(
            fit.result.core_version ?? text.header.unknownVersion,
          ),
        ]
      : fit.status === "stopped"
        ? [text.header.fitCore(text.header.unknownVersion)]
        : []),
    ...[
      ...new Set(
        curveVersions.map((version) => version ?? text.header.unknownVersion),
      ),
    ].map(text.header.curveCore),
  ];
}

/** What a file is of: the app, the model and fit, and what is known to be wrong with it. */
export function exportHeader(context: ExportContext): string[] {
  const { selection } = context;
  return [
    text.header.app(context.appVersion, context.apiVersion),
    ...coreVersionLines(
      context.serverCoreVersion,
      context.fit,
      context.curveCoreVersions,
    ),
    text.header.date(context.date),
    ...(selection.model === "dpb" &&
    selection.parameterization === "explicit_fermi_v1"
      ? [
          STRINGS.explicitDpb.fermiIdentity(
            selection.bandConfiguration ?? "vb_cb",
            selection.carrierType,
          ),
        ]
      : []),
    ...(selection.model === "dpb" &&
    selection.parameterization === "explicit_density_v1"
      ? [
          STRINGS.explicitDpb.identity(
            selection.bandConfiguration ?? "vb_cb",
            selection.netElectronDensityPerM3 ?? 1e24,
          ),
        ]
      : []),
    ...(selection.model === "dpb" && selection.legacySource
      ? [
          STRINGS.explicitDpb.legacyResult,
          legacyProvenance(selection.legacySource),
        ]
      : []),
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
    ...(context.limitedRanges ?? []).map(({ quantity, minK, maxK }) =>
      text.header.limitedRange(
        STRINGS.data.quantities[quantity].symbol,
        numberText(minK),
        numberText(maxK),
      ),
    ),
    ...(context.fromConductivity === true
      ? [text.header.fromConductivity]
      : []),
    ...(context.degeneracy
      ? [
          text.header.degeneracies(
            numberText(selection.band1Degeneracy),
            numberText(selection.band2Degeneracy),
          ),
        ]
      : []),
    fitLine(context.fit),
    // Only with no fit is the method chosen what a fit would run with. A fit that ran without
    // saying its method stays unknown rather than taking the one chosen since.
    context.fit.status === "idle"
      ? text.header.algorithmChosen(
          context.selection.algorithm ?? fitText.algorithm.unknown,
        )
      : fitText.algorithm.provenance(
          fitAlgorithm(context.fit) ?? fitText.algorithm.unknown,
        ),
    ...(context.fit.status === "done" && context.fit.result.diagnostics != null
      ? [
          fitText.diagnostics.termination(
            context.fit.result.diagnostics.termination,
          ),
          fitText.diagnostics.notAssessed,
          JSON.stringify(context.fit.result.diagnostics),
        ]
      : []),
    ...(context.run ?? []),
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
            measured.loaded_as === "conductivity"
              ? text.columns.experimentalFromSigma(name)
              : text.columns.experimental(name),
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
  selection: DegeneracySelection,
): ParameterRecord[] {
  const values = parameterValues(mode, saved, selection);
  const units: Record<string, string | undefined> = text.units;
  return visibleParameters(mode, scattering).map((parameter) => {
    const found = foundStatus(fit, parameter.name);
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
            : found.kind === "free"
              ? found.afterFailure
                ? text.status.freeAfterFailure
                : text.status.free
              : found.status === "fixed" || found.status === "held"
                ? text.status[found.status]
                : text.status.found[found.status],
    };
  });
}

type DegeneracySelection = Pick<
  Selection,
  "scattering" | "band1Degeneracy" | "band2Degeneracy"
> &
  Partial<
    Pick<
      Selection,
      | "model"
      | "parameterization"
      | "bandConfiguration"
      | "netElectronDensityPerM3"
      | "carrierType"
    >
  >;

function explicitIdentityRows(selection: DegeneracySelection): string[][] {
  if (selection.model !== "dpb" || selection.parameterization === undefined)
    return [];
  return [
    [
      "parameterization",
      "parameterization",
      STRINGS.explicitDpb.representationLabel,
      "",
      selection.parameterization,
      text.status.fixed,
    ],
    [
      "band_configuration",
      "band_configuration",
      STRINGS.explicitDpb.configuration,
      "",
      selection.bandConfiguration ?? "vb_cb",
      text.status.fixed,
    ],
    ...(selection.parameterization === "explicit_fermi_v1"
      ? selection.carrierType === undefined
        ? []
        : [
            [
              "carrier_type",
              "carrier_type",
              STRINGS.explicitDpb.carrierType,
              "",
              selection.carrierType,
              text.status.fixed,
            ],
          ]
      : [
          [
            "net_electron_density_per_m3",
            "n − p",
            STRINGS.explicitDpb.densityMeaning,
            "m^-3",
            numberText(selection.netElectronDensityPerM3 ?? 1e24),
            text.status.fixed,
          ],
        ]),
  ];
}

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
    selection,
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
    commented([...header, ...uncertaintyNotes(fit)]) +
    [
      text.parameterColumns,
      ...explicitIdentityRows(selection).map((row) =>
        [
          text.parameter(row[1] ?? "", row[2] ?? "", row[3] ?? ""),
          row[4],
          row[5],
        ].join("\t"),
      ),
      ...lines,
      ...degeneracy,
    ].join("\n") +
    "\n"
  );
}

/** What every status of a fit leaves open, written with the values it qualifies. */
function uncertaintyNotes(fit: FitState): string[] {
  return hasFittedValues(fit) ? [text.uncertaintyNote] : [];
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
    ...parameterRecords(
      mode,
      selection.scattering,
      saved,
      fit,
      held,
      selection,
    ),
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
    commented([...header, ...uncertaintyNotes(fit)]) +
    [
      text.parameterCsvColumns,
      ...explicitIdentityRows(selection).map((row) =>
        row.map(csvField).join(","),
      ),
      ...rows,
    ].join("\n") +
    "\n"
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
      ...curves.flatMap(({ name, values }) => {
        // An energy is in the unit the screen shows, as the parameters are.
        const energyLabel = energyLabels[name];
        if (energyLabel !== undefined) {
          return [
            {
              legend: energyLabel(energy.unit),
              values: values.map((value) =>
                value === null ? null : value * energy.per_kelvin,
              ),
            },
          ];
        }
        const column = { legend: labels[name] ?? name, values };
        // L also in units of L₀, as the chart shows it.
        return name.startsWith("lorenz_number")
          ? [
              column,
              {
                legend: text.relativeToL0(labels[name] ?? name),
                values: values.map((value) =>
                  value === null ? null : value / LORENZ_L0,
                ),
              },
            ]
          : [column];
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

/** Export provenance without repeating the original measurement files in every curve header. */
function legacyProvenance(source: string): string {
  try {
    const saved = JSON.parse(source) as {
      format?: string;
      version?: number;
      appVersion?: string;
      apiVersion?: string;
      content?: {
        selection?: unknown;
        parameters?: unknown;
        fit?: unknown;
        held?: unknown;
        customBounds?: unknown;
        fitStart?: unknown;
        units?: unknown;
      };
    };
    return JSON.stringify({
      format: saved.format,
      version: saved.version,
      appVersion: saved.appVersion,
      apiVersion: saved.apiVersion,
      ...(saved.content && {
        selection: saved.content.selection,
        parameters: saved.content.parameters,
        fit: saved.content.fit,
        held: saved.content.held,
        customBounds: saved.content.customBounds,
        fitStart: saved.content.fitStart,
        units: saved.content.units,
      }),
    });
  } catch {
    return source;
  }
}
