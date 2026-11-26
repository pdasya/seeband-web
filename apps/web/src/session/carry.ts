import type { ParameterDescription } from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import type { SessionState } from "@/session/store";

// Each converted DPB mode owns its archived values, bounds and holds for these controls.
export const archivedDpbControls: ReadonlySet<string> = new Set([
  "A",
  "B",
  "C",
  "D",
]);

type Carried = Pick<
  SessionState,
  "parameters" | "customBounds" | "held" | "guessedParameters"
>;

type CarryState = Carried & Partial<Pick<SessionState, "selection">>;

function keepsHistoricalControls(
  state: CarryState,
  from: FitModeDescription,
  to: FitModeDescription,
): boolean {
  return (
    Boolean(state.selection?.legacySource) &&
    state.selection?.parameterization === "explicit_density_v1" &&
    from.id.startsWith("dpb_") &&
    to.id.startsWith("dpb_")
  );
}

function sameEntries<T>(
  a: Readonly<Record<string, T>> | undefined,
  b: Readonly<Record<string, T>>,
  same: (x: T, y: T) => boolean = Object.is,
): boolean {
  const left = Object.entries(a ?? {});
  return (
    left.length === Object.keys(b).length &&
    left.every(([name, value]) => name in b && same(value, b[name] as T))
  );
}

/** The record with these names replaced by `from`'s, or the record itself if nothing changes. */
function withEntries<T>(
  record: Readonly<Record<string, T>> | undefined,
  names: ReadonlySet<string>,
  from: Readonly<Record<string, T>>,
  same?: (x: T, y: T) => boolean,
): Record<string, T> | undefined {
  const next = Object.fromEntries([
    ...Object.entries(record ?? {}).filter(([name]) => !names.has(name)),
    ...Object.entries(from).filter(([name]) => names.has(name)),
  ]);
  return sameEntries(record, next, same) ? record : next;
}

/** The map with `id` set to `value`, or the map itself if that is what it held. */
function withMode<T>(
  map: Readonly<Record<string, T>>,
  id: string,
  value: T | undefined,
): Record<string, T> {
  return value === undefined || map[id] === value
    ? map
    : { ...map, [id]: value };
}

const sameBounds = (
  a: { lower: number; upper: number },
  b: { lower: number; upper: number },
) => a.lower === b.lower && a.upper === b.upper;

const takesBounds = (parameter: ParameterDescription) =>
  parameter.role === "fitted" && parameter.bounds_editable === true;

/** What a change of mode takes along, by name. See `carryParameters`. */
function plan(
  state: CarryState,
  from: FitModeDescription,
  to: FitModeDescription,
) {
  const target = new Map(
    to.parameters.map((parameter) => [parameter.name, parameter]),
  );
  const saved = state.parameters[from.id] ?? {};
  const guessed = state.guessedParameters[from.id] ?? {};
  const shared = new Set<string>();
  const values: Record<string, number> = {};
  const replaceable: Record<string, number> = {};
  const keepHistorical = keepsHistoricalControls(state, from, to);
  for (const { name, core_range } of from.parameters) {
    // Converted sessions retain each mode's original transport controls.
    if (keepHistorical && archivedDpbControls.has(name)) continue;
    const there = target.get(name);
    if (there === undefined) continue;
    const value = saved[name] ?? core_range.default;
    // A value the new mode cannot take, such as an SPB A above its 10⁶ S/m, stays behind.
    if (value < there.core_range.minimum || value > there.core_range.maximum)
      continue;
    shared.add(name);
    if (saved[name] !== undefined) {
      values[name] = value;
      if (guessed[name] !== undefined) replaceable[name] = guessed[name];
    } else if (core_range.default !== there.core_range.default) {
      // The default it showed is no one's choice, so an automatic guess may replace it, as it
      // would the new mode's own. A default both modes share stays unset, as it was.
      values[name] = value;
      replaceable[name] = value;
    }
  }
  // Bounds and holds go only where the new mode lets the user set them.
  const bounded = new Set(
    [...shared].filter((name) => {
      const parameter = target.get(name);
      return parameter !== undefined && takesBounds(parameter);
    }),
  );
  const fitted = new Set(
    [...shared].filter((name) => target.get(name)?.role === "fitted"),
  );
  return { shared, values, replaceable, bounded, fitted };
}

/**
 * What a change from one fit mode to another takes along, within a model or from SPB to DPB and
 * back: each parameter they share by name, with the value it shows, whether an automatic guess may
 * replace it, its bounds if the new mode lets the user set them, and whether it is held if it is
 * fitted there. A shared name has one core unit and scale in every mode, so a value needs no
 * conversion; E_F keeps its number although SPB counts it from the band edge and DPB from the top
 * of band 1. A value outside the new mode's range stays behind, and a parameter only the new mode
 * has keeps what it had there, or its default. What does not change keeps its object, so that a
 * guess recorded against the values still holds.
 */
export function carryParameters(
  state: CarryState,
  from: FitModeDescription,
  to: FitModeDescription,
): Carried {
  if (from.id === to.id) {
    return state;
  }
  const { shared, values, replaceable, bounded, fitted } = plan(
    state,
    from,
    to,
  );
  const heldBefore = state.held[to.id] ?? [];
  const held = [
    ...heldBefore.filter((name) => !fitted.has(name)),
    ...(state.held[from.id] ?? []).filter((name) => fitted.has(name)),
  ];
  const sameHeld =
    held.length === heldBefore.length &&
    held.every((name) => heldBefore.includes(name));
  return {
    parameters: withMode(
      state.parameters,
      to.id,
      withEntries(state.parameters[to.id], shared, values),
    ),
    customBounds: withMode(
      state.customBounds,
      to.id,
      withEntries(
        state.customBounds[to.id],
        bounded,
        state.customBounds[from.id] ?? {},
        sameBounds,
      ),
    ),
    held: sameHeld ? state.held : { ...state.held, [to.id]: held },
    guessedParameters: withMode(
      state.guessedParameters,
      to.id,
      withEntries(state.guessedParameters[to.id], shared, replaceable),
    ),
  };
}

/** The names of the parameters whose value a change of mode takes along. */
export function carriedNames(
  state: CarryState,
  from: FitModeDescription,
  to: FitModeDescription,
): string[] {
  return from.id === to.id ? [] : [...plan(state, from, to).shared];
}
