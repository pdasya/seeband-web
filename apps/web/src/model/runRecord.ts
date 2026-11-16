import type { CalcResponse } from "@/api/client";
import type { Role } from "@/data/columnChoice";
import { unitDoubtMessage } from "@/data/units";
import { numberText } from "@/model/exportFiles";
import {
  coreToDisplay,
  parameterSymbol,
  parameterValues,
  visibleParameters,
} from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import { fitAlgorithm, type SessionState } from "@/session/store";
import { STRINGS } from "@/strings";

const { export: exportText, data: dataText } = STRINGS;

/** The parts of a session that say what a run used. */
export type RunState = Pick<
  SessionState,
  | "data"
  | "interpolation"
  | "fit"
  | "fitStartValues"
  | "fitStartNet"
  | "fitStartNumerical"
  | "selection"
  | "customBounds"
  | "held"
  | "parameters"
>;
const text = exportText.run;

/**
 * The roles of the columns a quantity was loaded from: temperature, and its own, or σ for a ρ
 * loaded as σ. A file with both ρ and σ columns gives ρ from one of them only.
 */
function rolesOf(
  quantity: string,
  entry: SessionState["data"][keyof SessionState["data"]],
): readonly Role[] {
  const loaded = entry?.measurement.loaded_as ?? quantity;
  return ["temperature", loaded as Role];
}

function roleLabel(role: Role): string {
  if (role === "temperature") {
    return text.temperature;
  }
  if (role === "conductivity") {
    return text.conductivity;
  }
  return dataText.quantities[role].symbol;
}

function valueText(
  parameter: ReturnType<typeof visibleParameters>[number],
  core: number,
): string {
  const units: Record<string, string | undefined> = exportText.units;
  const unit = units[parameter.display_unit] ?? parameter.display_unit;
  // Twelve figures: all a value holds, without the noise of converting units, as 0.04999999999997.
  const shown = numberText(
    Number(coreToDisplay(parameter, core).toPrecision(12)),
  );
  return unit === "" ? shown : `${shown} ${unit}`;
}

/** Where each quantity came from, the column and unit of each of its columns, and doubts. */
function inputLines(state: RunState, mode: FitModeDescription): string[] {
  return mode.quantities.flatMap((quantity) => {
    const entry = state.data[quantity];
    if (entry === undefined) {
      return [];
    }
    const symbol = dataText.quantities[quantity].symbol;
    const source =
      entry.source.kind === "demo" ? text.demo : text.file(entry.source.name);
    const columns = (entry.readAs ?? [])
      .filter(({ role }) => rolesOf(quantity, entry).includes(role))
      .map(({ column, role, unit, unit_source: from }) =>
        text.column(
          roleLabel(role),
          column + 1,
          unit == null ? text.unitNotNamed : dataText.units[unit],
          from == null ? text.sourceUnknown : text.unitSource[from],
        ),
      );
    const doubts = (entry.unitDoubts ?? []).map((doubt) => {
      const item = (entry.readAs ?? []).find(
        ({ role }) =>
          role !== "temperature" && rolesOf(quantity, entry).includes(role),
      );
      const role: Role = item?.role ?? (quantity as Role);
      return text.doubt(
        symbol,
        unitDoubtMessage(doubt, role, item),
        entry.unitConfirmed === true,
      );
    });
    const { minTemperatureK: low, maxTemperatureK: high } = state.selection;
    const temperatures = entry.measurement.temperature_k;
    const inRange =
      low === null || high === null
        ? null
        : temperatures.filter((t) => t >= low && t <= high).length;
    return [
      text.input(symbol, source, columns.join("; ")),
      text.points(symbol, temperatures.length, inRange),
      ...doubts,
    ];
  });
}

function interpolationLines(
  state: RunState,
  mode: FitModeDescription,
): string[] {
  const { interpolation } = state;
  const failed = interpolation.failed
    .filter((quantity) => mode.quantities.includes(quantity))
    .map((quantity) => dataText.quantities[quantity].symbol);
  return [
    interpolation.enabled ? text.interpolationOn : text.interpolationOff,
    ...(interpolation.enabled && failed.length > 0
      ? [text.interpolationFailed(failed.join(", "))]
      : []),
  ];
}

/** The values in use, which the file's fitted curve and parameters are of. */
function valueLines(state: RunState, mode: FitModeDescription): string[] {
  const values = parameterValues(mode, state.parameters[mode.id]);
  const listed = visibleParameters(mode, state.selection.scattering)
    .map((parameter) => {
      const value = values[parameter.name] ?? parameter.core_range.default;
      return `${parameterSymbol(parameter.name)} = ${valueText(parameter, value)}`;
    })
    .join(", ");
  return [text.values(listed)];
}

/** The values a fit started from, and where they came from, in the units the screen shows. */
function startLines(state: RunState, mode: FitModeDescription): string[] {
  const start = state.fitStartValues;
  if (state.fit.status === "idle" || start === null) {
    return [];
  }
  const source =
    state.fitStartNet !== null
      ? text.fromNet(
          numberText(state.fitStartNet.min_temperature_k),
          numberText(state.fitStartNet.max_temperature_k),
        )
      : state.fitStartNumerical
        ? text.fromNumerical
        : text.fromScreen;
  const values = parameterValues(mode, start);
  const listed = visibleParameters(mode, state.selection.scattering)
    .map((parameter) => {
      const value = values[parameter.name] ?? parameter.core_range.default;
      return `${parameterSymbol(parameter.name)} = ${valueText(parameter, value)}`;
    })
    .join(", ");
  return [text.start(source, listed)];
}

/** The bounds of each parameter a fit finds, which ones the user set, and those held. */
function boundLines(state: RunState, mode: FitModeDescription): string[] {
  const custom = state.customBounds[mode.id] ?? {};
  const held = state.held[mode.id] ?? [];
  const fitted = visibleParameters(mode, state.selection.scattering).filter(
    ({ role }) => role === "fitted",
  );
  const bounds = fitted
    .filter(({ name }) => !held.includes(name))
    .flatMap((parameter) => {
      const chosen = custom[parameter.name];
      const range = chosen ?? parameter.fit_bounds;
      if (range === undefined || range === null) {
        return [];
      }
      return [
        text.bound(
          parameterSymbol(parameter.name),
          valueText(parameter, range.lower),
          valueText(parameter, range.upper),
          chosen !== undefined,
        ),
      ];
    });
  const legacyMass =
    mode.id.startsWith("dpb") &&
    (fitAlgorithm(state.fit) ?? state.selection.algorithm) ===
      "legacy-sequential-v1" &&
    fitted.some(({ name }) => name === "m_eff") &&
    !held.includes("m_eff");
  return [
    ...(bounds.length > 0 ? [text.bounds(bounds.join("; "))] : []),
    ...(legacyMass ? [text.massBranch] : []),
    ...(held.length > 0
      ? [text.held(held.map((name) => parameterSymbol(name)).join(", "))]
      : []),
  ];
}

function rmseLines(
  rmse: CalcResponse["rmse"] | "failed" | null,
  fitted: boolean,
): string[] {
  if (rmse === null) {
    return [];
  }
  if (rmse === "failed") {
    return [text.rmseFailed];
  }
  const units: Record<string, string> = STRINGS.fit.rmseUnits;
  return Object.entries(rmse).map(([quantity, { value, unit }]) =>
    text.rmse(
      dataText.quantities[quantity as keyof typeof dataText.quantities].symbol,
      value === null ? text.notFinite : numberText(value),
      units[unit] ?? unit,
      fitted,
    ),
  );
}

/** The stop rule of a legacy loop, its limit, and how much each parameter changed last. */
function stopLines(state: RunState, mode: FitModeDescription): string[] {
  if (!mode.iterative || fitAlgorithm(state.fit) !== "legacy-sequential-v1") {
    return [];
  }
  const threshold = mode.threshold ?? null;
  const changes =
    state.fit.status === "done"
      ? Object.entries(state.fit.result.last_changes ?? {})
      : [];
  return [
    ...(threshold === null
      ? []
      : [
          text.stopRule(
            numberText(Number((threshold * 100).toPrecision(12))),
            mode.max_iterations ?? null,
          ),
        ]),
    ...(changes.length === 0
      ? []
      : [
          text.lastChanges(
            changes
              .map(
                ([name, change]) =>
                  `${parameterSymbol(name)} ${change === null ? text.notFinite : `${numberText(Number((change * 100).toPrecision(12)))} %`}`,
              )
              .join(", "),
          ),
          ...(state.fit.status === "done" &&
          state.fit.result.status === "iteration_limit"
            ? [text.limitBands]
            : []),
        ]),
  ];
}

/**
 * What a run used, so that it can be made again: the data and how they were read, interpolation,
 * where the fit started, its bounds, the RMSE of the curve in the file, and its stop rule.
 * `rmse` is that of the fitted curve if `fitted`, else of the values in use, "failed" if its
 * curve could not be calculated, which the file then says, or null if none was asked for.
 */
export function runLines(
  state: RunState,
  mode: FitModeDescription,
  rmse: CalcResponse["rmse"] | "failed" | null,
  fitted: boolean,
): string[] {
  return [
    ...inputLines(state, mode),
    ...interpolationLines(state, mode),
    ...valueLines(state, mode),
    ...startLines(state, mode),
    ...boundLines(state, mode),
    ...rmseLines(rmse, fitted),
    ...stopLines(state, mode),
  ];
}

/**
 * The unit each quantity was read in, with its temperature's if not kelvin, and any doubt about
 * it, for the results subtitle: a fit from µV/K read as V/K must not look clean.
 */
export function unitSummary(
  data: SessionState["data"],
  mode: FitModeDescription,
): string[] {
  return mode.quantities.flatMap((quantity) => {
    const entry = data[quantity];
    if (entry === undefined || entry.source.kind === "demo") {
      return [];
    }
    const read = entry.readAs ?? [];
    const own = read.find(
      ({ role }) =>
        role !== "temperature" && rolesOf(quantity, entry).includes(role),
    );
    const temperature = read.find(({ role }) => role === "temperature");
    if (own?.unit == null) {
      return [];
    }
    const symbol = roleLabel(own.role);
    const unit = dataText.units[own.unit];
    const inCelsius = temperature?.unit === "C";
    const doubt = (entry.unitDoubts ?? []).length > 0;
    return [
      text.summary(
        symbol,
        unit,
        inCelsius ? dataText.units.C : null,
        doubt ? (entry.unitConfirmed === true ? "confirmed" : "open") : null,
      ),
    ];
  });
}
