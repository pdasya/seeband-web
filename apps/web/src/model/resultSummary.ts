import { formatNumber } from "@/lib/numbers";
import { quantityCurve } from "@/model/chartTabs";
import {
  coreToDisplay,
  type FitBounds,
  parameterSymbol,
  parameterValues,
  shownValue,
  visibleParameters,
} from "@/model/parameters";
import type { FitModeDescription, ModelDescription } from "@/model/selection";
import {
  loadedAs,
  QUANTITIES,
  type FitState,
  type Quantity,
  type Selection,
  type SessionState,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { fit: text, parameters: parameterText } = STRINGS;

type IssueDescription = FitModeDescription["known_issues"][number];
export type IssueSeverity = IssueDescription["severity"];

/** The iteration a fit is at or ended on. A single-pass mode must not show it. */
export function fitIterations(fit: FitState): number | null {
  switch (fit.status) {
    case "running":
    case "stopped":
      return fit.iteration;
    case "done":
      return fit.result.iterations ?? null;
    default:
      return null;
  }
}

/** What the values on screen are, when a fit ended without converging. */
export function fitEndNote(
  fit: FitState,
  maxIterations: number | null,
): string | null {
  if (fit.status === "failed") {
    return text.endNotes.failed;
  }
  if (fit.status === "stopped") {
    return fit.lastParameters === null
      ? text.endNotes.stoppedAtStart
      : text.endNotes.stopped;
  }
  if (fit.status !== "done") {
    return null;
  }
  switch (fit.result.status) {
    case "iteration_limit":
      return text.endNotes.iterationLimit(maxIterations);
    case "stopped":
      return text.endNotes.stopped;
    case "failed":
      return text.endNotes.failed;
    default:
      return null;
  }
}

/**
 * What an RMSE of a quantity is named with. ρ from a σ file is ρ = 1/σ, as its RMSE compares the
 * curve with 1/σ, not with what was loaded (D31).
 */
export function rmseSymbol(
  quantity: Quantity,
  data: SessionState["data"],
): string {
  return loadedAs(quantity, data[quantity]) === "conductivity"
    ? STRINGS.data.inverseSigma
    : STRINGS.data.quantities[quantity].symbol;
}

/** An RMSE as the panels show it, with the unit the user reads. */
export function rmseText(rmse: { value: number | null; unit: string }): string {
  if (rmse.value === null) {
    return text.rmseNotFinite;
  }
  const units: Record<string, string> = text.rmseUnits;
  const value = formatNumber(Number(rmse.value.toPrecision(4)));
  return `${value} ${units[rmse.unit] ?? rmse.unit}`;
}

export interface ParameterRow {
  name: string;
  symbol: string;
  value: string;
  bounds: string;
  atBound: boolean;
}

function withUnit(value: number, unit: string): string {
  const units: Record<string, string> = text.valueUnits;
  const shown = units[unit];
  return shown === undefined
    ? formatNumber(value)
    : `${formatNumber(value)} ${shown}`;
}

/** The parameters in use, as they are on screen, in the units the user sees. */
export function parameterRows(
  mode: FitModeDescription,
  scattering: string | null,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
  custom?: Readonly<Record<string, FitBounds>>,
  /** Fitted parameters the fit kept at their values, which no bound sets. */
  held: readonly string[] = [],
): ParameterRow[] {
  const values = parameterValues(mode, saved);
  // A failed fit has fitted nothing, so it has reached no bound.
  const atBounds =
    fit.status === "done" && fit.result.status !== "failed"
      ? fit.result.at_bounds
      : [];
  return visibleParameters(mode, scattering).map((parameter) => {
    const { name, role, display_unit: unit } = parameter;
    const bounds = custom?.[name] ?? parameter.fit_bounds;
    const value = values[name] ?? parameter.core_range.default;
    const inDisplay = (core: number) => coreToDisplay(parameter, core);
    return {
      name,
      symbol: parameterSymbol(name),
      value: withUnit(shownValue(parameter, inDisplay(value)), unit),
      bounds:
        role === "fixed"
          ? parameterText.fixed
          : held.includes(name)
            ? parameterText.held
            : bounds === undefined || bounds === null
              ? text.noBounds
              : text.boundsRange(
                  formatNumber(shownValue(parameter, inDisplay(bounds.lower))),
                  formatNumber(shownValue(parameter, inDisplay(bounds.upper))),
                ),
      atBound: atBounds.includes(name),
    };
  });
}

/** Whether the values on screen came from a fit, so that a summary of it can be shown. */
export function hasFittedValues(fit: FitState): boolean {
  switch (fit.status) {
    case "done":
      return fit.result.status !== "failed";
    case "stopped":
      return fit.lastParameters !== null;
    default:
      return false;
  }
}

/**
 * Fitted, fixed by the mode, held at its value by the user, or known only with data that this fit
 * mode does not use.
 */
export type ParameterStatus =
  | { kind: "fitted" }
  | { kind: "fixed" }
  | { kind: "held" }
  | { kind: "needs"; quantities: Quantity[] };

export interface ResultRow {
  name: string;
  symbol: string;
  meaning: string;
  /** Empty while the parameter needs other data. */
  value: string;
  /** Empty when nothing bounds it: it is not fitted, or needs other data. */
  bounds: string;
  atBound: boolean;
  status: ParameterStatus;
}

/**
 * The parameters of a summary. On top of those in use, the band degeneracies, and each parameter
 * that another fit mode of the model finds with more data, as one that needs those data.
 */
export function resultRows(
  model: ModelDescription,
  mode: FitModeDescription,
  selection: Pick<
    Selection,
    "scattering" | "band1Degeneracy" | "band2Degeneracy"
  >,
  saved: Readonly<Record<string, number>> | undefined,
  fit: FitState,
  custom?: Readonly<Record<string, FitBounds>>,
  held: readonly string[] = [],
): ResultRow[] {
  const { scattering } = selection;
  const inUse = visibleParameters(mode, scattering);
  const rows: ResultRow[] = parameterRows(
    mode,
    scattering,
    saved,
    fit,
    custom,
    held,
  ).map((row, at) => {
    const parameter = inUse[at];
    const fixed = parameter?.role === "fixed";
    const kept = !fixed && held.includes(row.name);
    return {
      ...row,
      meaning: parameter?.meaning ?? "",
      // The status says it is not fitted, so its bounds are left empty.
      bounds: fixed || kept ? "" : row.bounds,
      status: { kind: fixed ? "fixed" : kept ? "held" : "fitted" },
    };
  });
  if (mode.degeneracy !== null && mode.degeneracy !== undefined) {
    rows.push({
      name: "degeneracy",
      symbol: text.degeneracySymbol,
      meaning: text.degeneracyMeaning,
      value: `${formatNumber(selection.band1Degeneracy)}, ${formatNumber(selection.band2Degeneracy)}`,
      bounds: "",
      atBound: false,
      status: { kind: "fixed" },
    });
  }
  // From the mode that needs the fewest data on top of these.
  const needed = new Map<string, { meaning: string; quantities: Quantity[] }>();
  for (const other of model.fit_modes) {
    // A mode that cannot run finds nothing, so it is no reason to load more data.
    if (
      other.disabled ||
      !mode.quantities.every((quantity) => other.quantities.includes(quantity))
    ) {
      continue;
    }
    const more = other.quantities.filter(
      (quantity) => !mode.quantities.includes(quantity),
    );
    // With no scattering here, only what the other mode has whatever its scattering.
    const found =
      scattering === null
        ? other.parameters.filter(
            (parameter) =>
              parameter.scattering.length === 0 ||
              other.scattering.every((id) => parameter.scattering.includes(id)),
          )
        : visibleParameters(other, scattering);
    for (const parameter of found) {
      const known = needed.get(parameter.name);
      if (
        more.length > 0 &&
        !inUse.some(({ name }) => name === parameter.name) &&
        (known === undefined || more.length < known.quantities.length)
      ) {
        needed.set(parameter.name, {
          meaning: parameter.meaning,
          quantities: more,
        });
      }
    }
  }
  for (const [name, { meaning, quantities }] of needed) {
    rows.push({
      name,
      symbol: parameterSymbol(name),
      meaning,
      value: "",
      bounds: "",
      atBound: false,
      status: { kind: "needs", quantities },
    });
  }
  return rows;
}

export interface ResultIssue {
  id: string;
  text: string;
  severity: IssueSeverity;
  /** The measured quantities whose values it changes, so whose RMSE it changes. */
  quantities: readonly Quantity[];
  /** Beside the numbers it is about: the RMSE and curves, or the fitted values. */
  place: "curves" | "fit";
}

function issueText(id: string, description?: IssueDescription): string {
  const known: Record<string, string> = text.knownIssueTexts;
  return (
    known[description?.message_key ?? `known_issue.${id}`] ??
    text.knownIssueOther
  );
}

function quantitiesOf(description: IssueDescription | undefined): Quantity[] {
  if (!description?.curve_kinds.includes("measured")) {
    return [];
  }
  const { columns } = description;
  return QUANTITIES.filter(
    (quantity) =>
      columns.length === 0 || columns.includes(quantityCurve(quantity)),
  );
}

/**
 * Everything known to be wrong with what is on screen. Curves from a fit carry that fit's errors
 * too, so this takes the flags of both, and each comes once.
 */
export function resultIssues(
  mode: FitModeDescription | undefined,
  flags: {
    fit: readonly string[];
    measured: readonly string[];
    derived: readonly string[];
  },
): ResultIssue[] {
  const ids = [...new Set([...flags.fit, ...flags.measured, ...flags.derived])];
  return ids.map((id) => {
    const description = mode?.known_issues.find((issue) => issue.id === id);
    const onMeasured = flags.fit.includes(id) || flags.measured.includes(id);
    const quantities = onMeasured ? quantitiesOf(description) : [];
    return {
      id,
      text: issueText(id, description),
      severity: description?.severity ?? "unreliable",
      quantities,
      place:
        quantities.length === 0 && flags.fit.includes(id) ? "fit" : "curves",
    };
  });
}

/** The worst of the issues on one quantity, or null if it has none. */
export function quantityMark(
  issues: readonly ResultIssue[],
  quantity: Quantity,
): IssueSeverity | null {
  const on = issues.filter(({ quantities }) => quantities.includes(quantity));
  if (on.length === 0) {
    return null;
  }
  return on.some(({ severity }) => severity === "caution") &&
    on.every(({ severity }) => severity === "caution")
    ? "caution"
    : "unreliable";
}
