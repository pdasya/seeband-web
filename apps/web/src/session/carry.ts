import type { FitModeDescription } from "@/model/selection";
import type { SessionState } from "@/session/store";

type Carried = Pick<
  SessionState,
  "parameters" | "customBounds" | "held" | "guessedParameters"
>;

function withEntries<T>(
  record: Readonly<Record<string, T>> | undefined,
  names: ReadonlySet<string>,
  from: Readonly<Record<string, T>> | undefined,
): Record<string, T> {
  return Object.fromEntries([
    ...Object.entries(record ?? {}).filter(([name]) => !names.has(name)),
    ...Object.entries(from ?? {}).filter(([name]) => names.has(name)),
  ]);
}

/**
 * What a change from one fit mode to another takes along, within a model or from SPB to DPB and
 * back: each parameter they share by name, with the value it shows, its bounds, whether it is
 * held, and whether an automatic guess may replace it. A shared name has one core unit and scale in every mode, so a
 * value needs no conversion; E_F keeps its number although SPB counts it from the band edge and
 * DPB from the top of band 1. A parameter only the new mode has keeps what it had there, or its
 * default.
 */
export function carryParameters(
  state: Carried,
  from: FitModeDescription,
  to: FitModeDescription,
): Carried {
  if (from.id === to.id) {
    return state;
  }
  const own = new Set(to.parameters.map(({ name }) => name));
  const shared = new Set(
    from.parameters.map(({ name }) => name).filter((name) => own.has(name)),
  );
  const saved = state.parameters[from.id] ?? {};
  const guessed = state.guessedParameters[from.id] ?? {};
  const defaults = new Map(
    to.parameters.map(({ name, core_range }) => [name, core_range.default]),
  );
  const shown: Record<string, number> = {};
  const replaceable: Record<string, number> = {};
  for (const { name, core_range } of from.parameters) {
    if (!shared.has(name)) continue;
    const value = saved[name];
    if (value !== undefined) {
      shown[name] = value;
      if (guessed[name] !== undefined) replaceable[name] = guessed[name];
    } else if (core_range.default !== defaults.get(name)) {
      // The default it showed is no one's choice, so an automatic guess may replace it, as it
      // would the new mode's own. A default both modes share stays unset, as it was.
      shown[name] = core_range.default;
      replaceable[name] = core_range.default;
    }
  }
  return {
    parameters: {
      ...state.parameters,
      [to.id]: withEntries(state.parameters[to.id], shared, shown),
    },
    customBounds: {
      ...state.customBounds,
      [to.id]: withEntries(
        state.customBounds[to.id],
        shared,
        state.customBounds[from.id],
      ),
    },
    held: {
      ...state.held,
      [to.id]: [
        ...(state.held[to.id] ?? []).filter((name) => !shared.has(name)),
        ...(state.held[from.id] ?? []).filter((name) => shared.has(name)),
      ],
    },
    guessedParameters: {
      ...state.guessedParameters,
      [to.id]: withEntries(state.guessedParameters[to.id], shared, replaceable),
    },
  };
}
