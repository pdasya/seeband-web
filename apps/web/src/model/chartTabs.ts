import type {
  BandDiagramResponse,
  CalcResponse,
  ModelsResponse,
} from "@/api/client";
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

/** Every choice of a chart, in the order of its select. */
export const CHART_TABS: readonly ChartTab[] = [
  "seebeck",
  "conductivity",
  "resistivity",
  "hall",
  "chemical_potential",
  "thermal_conductivity",
  "bands",
  "carrier_concentration",
  "band_diagram",
];

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
const CONDUCTIVITY = "electrical_conductivity_s_per_m";
const THERMAL_CONDUCTIVITY = "thermal_conductivity_w_per_m_k";
const CARRIERS_BAND_1 = "carrier_concentration_band_1_per_cm3";
const CARRIERS_BAND_2 = "carrier_concentration_band_2_per_cm3";

type CurveKind = FitModeDescription["curves"][number]["kind"];

/** The kinds of curve that charts ask for on top of the measured ones. */
export const DERIVED_KINDS_ASKED = [
  "chemical_potential",
  "seebeck_by_band",
  "electrical_conductivity",
  "thermal_conductivity",
  "carrier_concentration_by_band",
] as const;
export type DerivedKind = (typeof DERIVED_KINDS_ASKED)[number];

/** The kind of curve a tab asks for on top of the measured ones, as measurements need those. */
const DERIVED_KINDS: Partial<Record<ChartTab, DerivedKind>> = {
  chemical_potential: "chemical_potential",
  bands: "seebeck_by_band",
  conductivity: "electrical_conductivity",
  thermal_conductivity: "thermal_conductivity",
  carrier_concentration: "carrier_concentration_by_band",
};

function availabilityOf(mode: FitModeDescription, kind: CurveKind) {
  return mode.curves.find((curve) => curve.kind === kind);
}

/** What to ask for this tab, or null if it needs no other curves or its mode has none. */
export function derivedKind(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
): DerivedKind | null {
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
  // Its points come with the measured curves, from the ρ data.
  if (tab === "conductivity") {
    return (
      derivedKind(tab, mode) !== null &&
      data.resistivity !== undefined &&
      mode?.quantities.includes("resistivity") === true
    );
  }
  return (
    isQuantityTab(tab) &&
    data[tab] !== undefined &&
    mode?.quantities.includes(tab) === true
  );
}

/** Whether a tab shows a measured quantity, with its points. */
export function isQuantityTab(tab: ChartTab): tab is Quantity {
  return tab in QUANTITY_TABS;
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
  /** Says what a chart with points only leaves out, or what is known to be wrong with it. */
  note: string | null;
  /** For a chart that is not against temperature. */
  xAxis?: { title: string; span: readonly [number, number] | null };
}

const NO_CHART = {
  curves: [],
  measurements: null,
  interpolated: null,
  referenceLines: [],
  note: null,
};

/** How energies that come in K are shown, from the model descriptions, such as in eV. */
export type EnergyDisplay = ModelsResponse["energy_display"];

/** Until the descriptions come, in K as the core has them. No chart has a mode before then. */
export const ENERGY_IN_K: EnergyDisplay = { unit: "K", per_kelvin: 1 };

type ViewState = Pick<SessionState, "data" | "interpolation"> & {
  bandGapK?: number | undefined;
  energy: EnergyDisplay;
};

function energies(
  values: readonly (number | null)[],
  energy: EnergyDisplay,
): (number | null)[] {
  return scaled(values, energy.per_kelvin);
}

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
  const data = state.data[quantity];
  const entry = data?.measurement;
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
      // Demo data say what they are wherever they appear.
      label:
        data?.source.kind === "demo"
          ? text.measurementsDemo
          : text.measurements,
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
    yAxisTitle: text.axes.chemicalPotential(state.energy.unit),
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
    curves: curveOf(
      derived,
      CHEMICAL_POTENTIAL,
      state.energy.per_kelvin,
      text.chemicalPotential,
    ),
    referenceLines:
      bandGapK === undefined
        ? [{ value: 0, label: text.bandEdge }]
        : [
            { value: 0, label: text.band1Top },
            {
              value: bandGapK * state.energy.per_kelvin,
              label: text.band2Bottom,
            },
          ],
  };
}

// σ's points are 1/ρ of the ρ data, which the server calculates with the measured curves.
function conductivityView(
  mode: FitModeDescription | undefined,
  state: ViewState,
  measured: CalcResponse | null,
  derived: CalcResponse | null,
): ChartTabView {
  const base = {
    yAxisTitle: text.axes.conductivity,
    description: text.conductivityDescription,
  };
  if (derivedKind("conductivity", mode) === null) {
    return {
      ...NO_CHART,
      ...base,
      empty: unavailable(mode, "electrical_conductivity"),
    };
  }
  // The server's 1/ρ of the ρ data the measured request sent. An answer stays while the next is on
  // its way, so its points are named by the data they are at, and left out if they fit neither.
  const answer = measured?.measured_points?.[CONDUCTIVITY];
  const from =
    answer === undefined ? null : pointsSource(answer.temperature_k, state);
  const points = from === null ? undefined : answer;
  return {
    ...NO_CHART,
    ...base,
    empty: null,
    curves: curveOf(derived, CONDUCTIVITY, 1, text.model),
    measurements:
      points === undefined
        ? null
        : {
            label:
              from === "interpolated"
                ? text.conductivityPointsInterpolated
                : text.conductivityPoints,
            temperatureK: points.temperature_k,
            values: points.values,
          },
    note:
      points === undefined
        ? text.conductivityNote
        : text.conductivityPointsNote,
  };
}

/** Which ρ the points of σ are at: those in use now, measured or interpolated, or neither. */
function pointsSource(
  temperatureK: readonly number[],
  state: ViewState,
): "measured" | "interpolated" | null {
  const within = (grid: readonly number[] | undefined) =>
    grid !== undefined &&
    temperatureK.length > 0 &&
    temperatureK.every((temperature) => grid.includes(temperature));
  if (state.interpolation.enabled) {
    return within(state.interpolation.values.resistivity?.temperature_k)
      ? "interpolated"
      : null;
  }
  return within(state.data.resistivity?.measurement.temperature_k)
    ? "measured"
    : null;
}

/** A curve the derived request gives alone, with what is said about it. */
function derivedView(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
  derived: CalcResponse | null,
  shown: {
    curves: (result: CalcResponse | null) => ChartCurve[];
    yAxisTitle: string;
    description: string;
    note: string | null;
  },
): ChartTabView {
  const base = {
    yAxisTitle: shown.yAxisTitle,
    description: shown.description,
  };
  const kind = DERIVED_KINDS[tab];
  if (kind === undefined || derivedKind(tab, mode) === null) {
    return {
      ...NO_CHART,
      ...base,
      empty: unavailable(mode, kind ?? "measured"),
    };
  }
  return {
    ...NO_CHART,
    ...base,
    empty: null,
    curves: shown.curves(derived),
    note: shown.note,
  };
}

function thermalConductivityView(
  mode: FitModeDescription | undefined,
  derived: CalcResponse | null,
): ChartTabView {
  return derivedView("thermal_conductivity", mode, derived, {
    curves: (result) =>
      curveOf(result, THERMAL_CONDUCTIVITY, 1, text.thermalConductivity),
    yAxisTitle: text.axes.thermalConductivity,
    description: text.thermalConductivityDescription,
    note: text.thermalConductivityNote,
  });
}

// Without R_H data, the core sizes n with m₁ = 1, and the description marks the curve relative.
function carrierConcentrationView(
  mode: FitModeDescription | undefined,
  derived: CalcResponse | null,
): ChartTabView {
  const relative =
    mode !== undefined &&
    availabilityOf(mode, "carrier_concentration_by_band")?.relative === true;
  return derivedView("carrier_concentration", mode, derived, {
    curves: (result) => [
      ...curveOf(result, CARRIERS_BAND_1, 1, text.band1, {
        color: "orange",
        dashed: true,
      }),
      ...curveOf(result, CARRIERS_BAND_2, 1, text.band2, {
        color: "teal",
        dashed: true,
      }),
    ],
    yAxisTitle: text.axes.carrierConcentration,
    description: text.carrierConcentrationDescription,
    note: relative ? text.carrierConcentrationRelative : null,
  });
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
function bandDiagramView(
  mode: FitModeDescription | undefined,
  diagram: BandDiagramResponse | null,
  energy: EnergyDisplay,
): ChartTabView {
  const { fit } = STRINGS;
  const labels: Record<string, string> = text.diagramCurves;
  const issueTexts: Record<string, string> = fit.knownIssueTexts;
  const first = diagram?.wavevector[0];
  const last = diagram?.wavevector.at(-1);
  return {
    ...NO_CHART,
    yAxisTitle: text.axes.energy(energy.unit),
    description: text.diagramDescription,
    empty: null,
    xAxis: {
      title: text.wavevectorAxis,
      span: first === undefined || last === undefined ? null : [first, last],
    },
    // Each name comes from the server, so a model with other bands needs no change here.
    curves: Object.entries(diagram?.curves ?? {}).map(([name, values]) => ({
      id: name,
      label: labels[name] ?? name,
      temperatureK: diagram?.wavevector ?? [],
      values: energies(values, energy),
      dashed: name === "fermi_energy_k",
    })),
    note:
      diagram === null || diagram.known_issues.length === 0
        ? null
        : diagram.known_issues
            .map((id) => {
              const issue = mode?.known_issues.find((item) => item.id === id);
              const severity =
                fit.issueSeverity[issue?.severity ?? "unreliable"];
              const said =
                issueTexts[`known_issue.${id}`] ?? fit.knownIssueOther;
              return `${severity}: ${said}`;
            })
            .join(" "),
  };
}

export function chartTabView(
  tab: ChartTab,
  mode: FitModeDescription | undefined,
  state: ViewState,
  measured: CalcResponse | null,
  derived: CalcResponse | null,
  diagram: BandDiagramResponse | null = null,
): ChartTabView {
  switch (tab) {
    case "band_diagram":
      return bandDiagramView(mode, diagram, state.energy);
    case "conductivity":
      return conductivityView(mode, state, measured, derived);
    case "thermal_conductivity":
      return thermalConductivityView(mode, derived);
    case "carrier_concentration":
      return carrierConcentrationView(mode, derived);
    case "chemical_potential":
      return chemicalPotentialView(mode, state, derived);
    case "bands":
      return bandsView(mode, measured, derived);
    case "seebeck":
    case "resistivity":
    case "hall":
      return quantityView(tab, mode, state, measured);
    default: {
      // A new tab must have its case above, which this makes the compiler check.
      const unknown: never = tab;
      throw new Error(`No view for the tab ${String(unknown)}`);
    }
  }
}
