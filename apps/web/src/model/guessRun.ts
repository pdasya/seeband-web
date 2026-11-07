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

/** The model whose nets guess its start values. The API says which has them. */
export function guessModel(
  models: readonly ModelDescription[] | undefined,
): ModelDescription | undefined {
  return models?.find(({ has_initial_guess }) => has_initial_guess);
}

function failure(error: unknown): GuessOutcome {
  return {
    kind: "failed",
    code: error instanceof ApiError ? error.code : NETWORK_ERROR,
    warnings: [],
  };
}

/**
 * Asks the nets for start values from every row of S, as the desktop does, whatever the fit range.
 * Like the desktop, it writes to every mode of the model. An edit or a fit while it waits wins, as
 * the user has moved on from these values.
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
    if (store().parameters !== parameters) {
      store().guessFinished(null, model.id, measurement);
    } else if (answer.status === "guess") {
      if (answer.warnings.includes("m_eff_rounds_to_zero")) {
        store().guessFinished(
          { kind: "needs_mass", warnings: answer.warnings },
          model.id,
          measurement,
        );
      } else {
        store().guessApplied(
          model.fit_modes.map(({ id, parameters: specs }) => ({
            fitMode: id,
            values: Object.fromEntries(
              specs.flatMap(({ name }) => {
                const value = answer.start_values[name];
                return value === undefined ? [] : [[name, value]];
              }),
            ),
          })),
          {
            kind: "applied",
            netRange: answer.net_range,
            warnings: answer.warnings,
          },
          model.id,
          measurement,
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
        measurement,
      );
    } else {
      store().guessFinished(
        { kind: "not_finite", warnings: answer.warnings },
        model.id,
        measurement,
      );
    }
  } catch (error) {
    if (!own.signal.aborted) {
      store().guessFinished(
        store().parameters === parameters ? failure(error) : null,
        model.id,
        measurement,
      );
    }
  } finally {
    if (controller === own) {
      controller = null;
    }
  }
}

const seen = new WeakSet<Measurement>();
let last: Measurement | null = null;

function sameRows(a: Measurement, b: Measurement): boolean {
  return (
    a.temperature_k.length === b.temperature_k.length &&
    a.temperature_k.every((value, index) => value === b.temperature_k[index]) &&
    a.values.every((value, index) => value === b.values[index])
  );
}

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
