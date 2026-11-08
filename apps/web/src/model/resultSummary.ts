import { formatNumber } from "@/lib/numbers";
import { quantityCurve } from "@/model/chartTabs";
import {
  coreToDisplay,
  type FitBounds,
  parameterSymbol,
  parameterValues,
  shortened,
  visibleParameters,
} from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import { QUANTITIES, type FitState, type Quantity } from "@/session/store";
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
): ParameterRow[] {
  const values = parameterValues(mode, saved);
  // A failed fit has fitted nothing, so it has reached no bound.
  const atBounds =
    fit.status === "done" && fit.result.status !== "failed"
      ? fit.result.at_bounds
      : [];
  return visibleParameters(mode, scattering).map((parameter) => {
    const { name, role, unit } = parameter;
    const bounds = custom?.[name] ?? parameter.fit_bounds;
    const value = values[name] ?? parameter.core_range.default;
    const inDisplay = (core: number) => coreToDisplay(parameter, core);
    return {
      name,
      symbol: parameterSymbol(name),
      value: withUnit(shortened(inDisplay(value)), unit),
      bounds:
        role === "fixed"
          ? parameterText.fixed
          : bounds === undefined || bounds === null
            ? text.noBounds
            : text.boundsRange(
                formatNumber(shortened(inDisplay(bounds.lower))),
                formatNumber(shortened(inDisplay(bounds.upper))),
              ),
      atBound: atBounds.includes(name),
    };
  });
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
