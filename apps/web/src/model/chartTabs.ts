import type { CalcResponse } from "@/api/client";
import type {
  ChartCurve,
  ChartMeasurements,
  ReferenceLine,
} from "@/charts/figure";
import { parameterValues } from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import type { ChartTab, Quantity, SessionState } from "@/session/store";
import { STRINGS } from "@/strings";

const { chart: text } = STRINGS;

/** What each tab with measurements draws, from the core's units to those of its axis. */
const QUANTITY_TABS: Record<
  Quantity,
  { curve: string; factor: number; axis: string }
> = {
  seebeck: { curve: "seebeck_v_per_k", factor: 1e6, axis: text.axes.seebeck },
  resistivity: {
    curve: "resistivity_ohm_m",
    factor: 1e6,
    axis: text.axes.resistivity,
  },
  hall: { curve: "hall_m3_per_c", factor: 1, axis: text.axes.hall },
};

/** The column of a quantity in a measured result. */
export function quantityCurve(quantity: Quantity): string {
  return QUANTITY_TABS[quantity].curve;
}

const SEEBECK_TOTAL = QUANTITY_TABS.seebeck.curve;
const SEEBECK_BAND_1 = "seebeck_band_1_v_per_k";
const SEEBECK_BAND_2 = "seebeck_band_2_v_per_k";
const CHEMICAL_POTENTIAL = "chemical_potential_k";

type CurveKind = FitModeDescription["curves"][number]["kind"];

/** The kind of curve a tab asks for on top of the measured ones, as measurements need those. */
const DERIVED_KINDS: Partial<Record<ChartTab, CurveKind>> = {
  chemical_potential: "chemical_potential",
  bands: "seebeck_by_band",
};

function availabilityOf(mode: FitModeDescription, kind: CurveKind) {
  return mode.curves.find((curve) => curve.kind === kind);
}

/** What to ask for this tab, or null if it needs no other curves or its mode has none. */
export function derivedKind(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
): CurveKind | null {
  const kind = DERIVED_KINDS[tab];
  return kind !== undefined &&
    mode !== undefined &&
    availabilityOf(mode, kind)?.available === true
    ? kind
    : null;
}

/** Whether what the open tab draws comes from the measured request. */
export function drawsMeasuredCurves(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
  data: SessionState["data"],
): boolean {
  if (tab === "bands") {
    return needsMeasuredCurves(tab, mode);
  }
  return (
    tab !== "chemical_potential" &&
    data[tab] !== undefined &&
    mode?.quantities.includes(tab) === true
  );
}

/** E_g for the line on μ, and for that tab only, so that other tabs do not follow its value. */
export function bandGapForTab(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
  parameters: SessionState["parameters"],
): number | undefined {
  return tab === "chemical_potential" && mode !== undefined
    ? parameterValues(mode, parameters[mode.id]).band_gap
    : undefined;
}

/** The total of S goes with the contributions, so that tab needs it even with no data. */
export function needsMeasuredCurves(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
): boolean {
  return tab === "bands" && derivedKind(tab, mode) !== null;
}

function scaled(
  values: readonly (number | null)[],
  factor: number,
): (number | null)[] {
  return factor === 1
    ? [...values]
    : values.map((value) => (value === null ? null : value * factor));
}

interface EmptyState {
  title: string;
  text: string;
}

export interface ChartTabView {
  empty: EmptyState | null;
  curves: ChartCurve[];
  measurements: ChartMeasurements | null;
  interpolated: ChartMeasurements | null;
  referenceLines: ReferenceLine[];
  yAxisTitle: string;
  description: string;
  /** Says what a chart with points only leaves out. */
  note: string | null;
}

const NO_CHART = {
  curves: [],
  measurements: null,
  interpolated: null,
  referenceLines: [],
  note: null,
};

type ViewState = Pick<SessionState, "data" | "interpolation"> & {
  bandGapK?: number | undefined;
};

function curveOf(
  result: CalcResponse | null,
  name: string,
  factor: number,
  label: string,
  style: Pick<ChartCurve, "color" | "dashed"> = {},
): ChartCurve[] {
  const values = result?.curves[name];
  return result === null || values === undefined
    ? []
    : [
        {
          id: name,
          label,
          temperatureK: result.temperature_k,
          values: scaled(values, factor),
          ...style,
        },
      ];
}

function quantityView(
  quantity: Quantity,
  mode: FitModeDescription | undefined,
  state: ViewState,
  measured: CalcResponse | null,
): ChartTabView {
  const { curve, factor, axis } = QUANTITY_TABS[quantity];
  const words = text.quantityTabs[quantity];
  const base = { yAxisTitle: axis, description: words.description };
  const entry = state.data[quantity]?.measurement;
  if (entry === undefined) {
    return {
      ...NO_CHART,
      ...base,
      empty: { title: words.noDataTitle, text: words.noDataText },
    };
  }
  const interpolated = state.interpolation.values[quantity];
  const inMode = mode?.quantities.includes(quantity) === true;
  return {
    ...NO_CHART,
    ...base,
    empty: null,
    curves: inMode ? curveOf(measured, curve, factor, text.model) : [],
    measurements: {
      label: text.measurements,
      temperatureK: entry.temperature_k,
      values: scaled(entry.values, factor),
    },
    interpolated:
      interpolated === undefined
        ? null
        : {
            label: text.interpolated,
            temperatureK: interpolated.temperature_k,
            values: scaled(interpolated.values, factor),
          },
    note: inMode ? null : words.notInMode,
  };
}

function unavailable(
  mode: FitModeDescription | undefined,
  kind: CurveKind,
): EmptyState {
  const reason = mode === undefined ? null : availabilityOf(mode, kind)?.reason;
  const known: Record<string, EmptyState | undefined> = text.unavailable;
  return (reason != null ? known[reason] : undefined) ?? text.notInThisMode;
}

function chemicalPotentialView(
  mode: FitModeDescription | undefined,
  state: ViewState,
  derived: CalcResponse | null,
): ChartTabView {
  const base = {
    yAxisTitle: text.axes.chemicalPotential,
    description: text.chemicalPotentialDescription,
  };
  if (derivedKind("chemical_potential", mode) === null) {
    return {
      ...NO_CHART,
      ...base,
      empty: unavailable(mode, "chemical_potential"),
    };
  }
  // Band 2 lies at E_g in a mode with one, and an edge of a band lies at 0.
  const { bandGapK } = state;
  return {
    ...NO_CHART,
    ...base,
    empty: null,
    curves: curveOf(derived, CHEMICAL_POTENTIAL, 1, text.chemicalPotential),
    referenceLines:
      bandGapK === undefined
        ? [{ value: 0, label: text.bandEdge }]
        : [
            { value: 0, label: text.band1Top },
            { value: bandGapK, label: text.band2Bottom },
          ],
  };
}

function bandsView(
  mode: FitModeDescription | undefined,
  measured: CalcResponse | null,
  derived: CalcResponse | null,
): ChartTabView {
  const base = {
    yAxisTitle: text.axes.seebeck,
    description: text.bandsDescription,
  };
  if (derivedKind("bands", mode) === null) {
    return {
      ...NO_CHART,
      ...base,
      empty: unavailable(mode, "seebeck_by_band"),
    };
  }
  const { factor } = QUANTITY_TABS.seebeck;
  return {
    ...NO_CHART,
    ...base,
    empty: null,
    curves: [
      ...curveOf(measured, SEEBECK_TOTAL, factor, text.totalS, {
        color: "blue",
      }),
      ...curveOf(derived, SEEBECK_BAND_1, factor, text.band1Contribution, {
        color: "orange",
        dashed: true,
      }),
      ...curveOf(derived, SEEBECK_BAND_2, factor, text.band2Contribution, {
        color: "teal",
        dashed: true,
      }),
    ],
  };
}

/** What a tab shows, from the answers and session. It calculates nothing but units. */
export function chartTabView(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
  state: ViewState,
  measured: CalcResponse | null,
  derived: CalcResponse | null,
): ChartTabView {
  switch (tab) {
    case "chemical_potential":
      return chemicalPotentialView(mode, state, derived);
    case "bands":
      return bandsView(mode, measured, derived);
    default:
      return quantityView(tab, mode, state, measured);
  }
}
