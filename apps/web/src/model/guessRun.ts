import { apiClient } from "@/api/client";
import { ApiError, NETWORK_ERROR } from "@/api/errors";
import type { ModelDescription } from "@/model/selection";
import {
  useSessionStore,
  type GuessOutcome,
  type Measurement,
} from "@/session/store";

let controller: AbortController | null = null;

function store() {
  return useSessionStore.getState();
}

/** Return the selected model when the API offers initial estimates for it. */
export function guessModel(
  models: readonly ModelDescription[] | undefined,
  selected = "dpb",
): ModelDescription | undefined {
  return models?.find(
    ({ id, has_initial_guess }) => id === selected && has_initial_guess,
  );
}

function failure(error: unknown): GuessOutcome {
  return {
    kind: "failed",
    code: error instanceof ApiError ? error.code : NETWORK_ERROR,
    warnings: [],
  };
}

function sameRows(a: Measurement, b: Measurement): boolean {
  return (
    a.temperature_k.length === b.temperature_k.length &&
    a.temperature_k.every((value, index) => value === b.temperature_k[index]) &&
    a.values.every((value, index) => value === b.values[index])
  );
}

/**
 * Asks the nets for start values from every row of S, as the desktop does, whatever the fit range.
 * Like the desktop, it writes to every mode of the model. An edit while it waits wins, as the user
 * has moved on from these values, and so does S going away, as they would describe nothing on
 * screen. A new mapping that reads the same S is no such thing.
 */
export async function runGuess(
  model: ModelDescription,
  measurement: Measurement,
): Promise<void> {
  controller?.abort();
  const own = new AbortController();
  controller = own;
  const { parameters } = store();
  store().guessStarted();
  // The data this answer is still about, if the user has not moved on.
  const current = (): Measurement | null => {
    const now = store().data.seebeck?.measurement;
    return store().parameters === parameters &&
      now !== undefined &&
      sameRows(now, measurement)
      ? now
      : null;
  };
  try {
    const answer = await apiClient.postGuess(
      {
        model: model.id,
        temperature_k: [...measurement.temperature_k],
        seebeck_v_per_k: [...measurement.values],
      },
      own.signal,
    );
    if (own.signal.aborted) {
      return;
    }
    const now = current();
    if (now === null) {
      store().guessDropped();
    } else if (
      answer.status === "guess" ||
      answer.status === "numerical_guess"
    ) {
      if (answer.warnings.includes("m_eff_rounds_to_zero")) {
        store().guessFinished(
          { kind: "needs_mass", warnings: answer.warnings },
          model.id,
          now,
        );
      } else {
        store().guessApplied(
          model.fit_modes.map(({ id, parameters: specs }) => ({
            fitMode: id,
            values: Object.fromEntries(
              specs.flatMap(({ name, core_range }) => {
                let value = answer.start_values[name];
                if (name === "band_mass" && value !== undefined) {
                  const previous =
                    parameters[id]?.band_mass ?? core_range.default;
                  value = Math.sign(value) * (Math.abs(previous) || 1);
                }
                return value === undefined ? [] : [[name, value]];
              }),
            ),
          })),
          {
            kind: "applied",
            ...(answer.status === "guess"
              ? { netRange: answer.net_range }
              : {}),
            warnings: answer.warnings,
          },
          model.id,
          now,
        );
      }
    } else if (answer.status === "no_net") {
      store().guessFinished(
        {
          kind: "no_net",
          firstK: answer.first_temperature_k,
          lastK: answer.last_temperature_k,
          available: answer.available_ranges,
          warnings: answer.warnings,
        },
        model.id,
        now,
      );
    } else {
      store().guessFinished(
        { kind: "not_finite", warnings: answer.warnings },
        model.id,
        now,
      );
    }
  } catch (error) {
    if (!own.signal.aborted) {
      const now = current();
      if (now === null) {
        store().guessDropped();
      } else {
        store().guessFinished(failure(error), model.id, now);
      }
    }
  } finally {
    if (controller === own) {
      controller = null;
    }
  }
}

/**
 * Ends a guess on its way, for a fit: that starts from the values on screen, so they must stay the
 * ones it uses, even if it ends before the answer comes.
 */
export function dropGuess(): void {
  if (controller !== null) {
    controller.abort();
    controller = null;
    store().guessDropped();
  }
}

const seen = new WeakSet<Measurement>();
let last: Measurement | null = null;

/**
 * Whether S just came from a new load, as the desktop guesses on each. Coming back to a tab brings
 * back the same data, and a new mapping of a table can read the same S, which are no such thing.
 */
export function isNewLoad(measurement: Measurement | undefined): boolean {
  if (measurement === undefined) {
    last = null;
    return false;
  }
  const known = seen.has(measurement) || (last && sameRows(last, measurement));
  seen.add(measurement);
  last = measurement;
  return known !== true;
}
