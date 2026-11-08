// @vitest-environment node
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { MODELS } from "../../e2e/support/models";

import { apiClient } from "@/api/client";
import { dropGuess, guessModel, isNewLoad, runGuess } from "@/model/guessRun";
import type { ModelDescription } from "@/model/selection";
import {
  currentGuess,
  useSessionStore,
  type Measurement,
} from "@/session/store";

const models = MODELS.models as ModelDescription[];

const rows = (...values: number[]) =>
  ({
    temperature_k: values.map((_, index) => 100 + index),
    values,
  }) as unknown as Measurement;

describe("guessModel", () => {
  test("is the one the API says has nets", () => {
    expect(guessModel(models)?.id).toBe("dpb");
    expect(
      guessModel(models.filter(({ has_initial_guess: has }) => !has)),
    ).toBeUndefined();
    expect(guessModel(undefined)).toBeUndefined();
  });
});

describe("isNewLoad", () => {
  beforeEach(() => {
    isNewLoad(undefined);
  });

  test("a new file is one, and no data are not", () => {
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(rows(1))).toBe(true);
  });

  test("the same data coming back are not, after another file or none", () => {
    const first = rows(1);
    expect(isNewLoad(first)).toBe(true);
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(first)).toBe(false);
    expect(isNewLoad(rows(2))).toBe(true);
    expect(isNewLoad(first)).toBe(false);
  });

  test("the same S read again in place is not, as from a new mapping", () => {
    expect(isNewLoad(rows(1, 2))).toBe(true);
    expect(isNewLoad(rows(1, 2))).toBe(false);
    expect(isNewLoad(rows(1, 3))).toBe(true);
  });

  test("the same file loaded after removing the last is", () => {
    expect(isNewLoad(rows(1))).toBe(true);
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(rows(1))).toBe(true);
  });
});

describe("runGuess", () => {
  const dpb = guessModel(models) as ModelDescription;
  const ANSWER = {
    status: "guess",
    net_range: { min_temperature_k: 25, max_temperature_k: 750 },
    prediction: { m_eff: 1.57, band_gap_k: 554, fermi_energy_k: 1170 },
    start_values: { m_eff: 1.57, band_gap: 554, fermi_energy: 1170 },
    warnings: [],
  };
  const state = () => useSessionStore.getState();
  const holdS = (measurement: Measurement | null) => {
    useSessionStore.setState({
      data: (measurement === null ? {} : { seebeck: { measurement } }) as never,
    });
  };
  const applied = () => state().parameters.dpb_s?.band_gap;

  // Answers when told to, as a real one comes after the user has done something.
  function waiting(measurement: Measurement) {
    let answer: (value: unknown) => void = () => undefined;
    vi.spyOn(apiClient, "postGuess").mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }) as never,
    );
    holdS(measurement);
    const run = runGuess(dpb, measurement);
    return async () => {
      answer(ANSWER);
      await run;
    };
  }

  beforeEach(() => {
    useSessionStore.setState(useSessionStore.getInitialState(), true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("applies to the data still on screen", async () => {
    const answer = waiting(rows(1, 2));
    expect(state().guessPending).toBe(true);

    await answer();

    expect(applied()).toBe(554);
    expect(state().guessPending).toBe(false);
    expect(currentGuess(state())?.kind).toBe("applied");
  });

  test("a new mapping that reads the same S is still that data", async () => {
    const answer = waiting(rows(1, 2));
    holdS(rows(1, 2));

    await answer();

    expect(applied()).toBe(554);
    expect(currentGuess(state())?.kind).toBe("applied");
  });

  test("is dropped when S has gone or become other data", async () => {
    let answer = waiting(rows(1, 2));
    holdS(null);
    await answer();
    expect(applied()).toBeUndefined();
    expect(state().guessPending).toBe(false);

    answer = waiting(rows(1, 2));
    holdS(rows(1, 3));
    await answer();
    expect(applied()).toBeUndefined();
    expect(state().guessPending).toBe(false);
  });

  test("a failure about data that has gone says nothing", async () => {
    vi.spyOn(apiClient, "postGuess").mockRejectedValue(new Error("no"));
    holdS(null);

    await runGuess(dpb, rows(1, 2));

    expect(state().guess).toBeNull();
    expect(state().guessPending).toBe(false);
  });

  test("dropGuess ends the wait, and the answer no longer counts", async () => {
    const answer = waiting(rows(1, 2));

    dropGuess();
    expect(state().guessPending).toBe(false);

    await answer();
    expect(applied()).toBeUndefined();
    expect(state().guess).toBeNull();
  });

  test("dropGuess with no guess on its way leaves the last outcome", async () => {
    await waiting(rows(1, 2))();
    const { guess } = state();

    dropGuess();

    expect(state().guess).toBe(guess);
  });
});

describe("single-band initial estimates", () => {
  afterEach(() => vi.restoreAllMocks());

  test("selects the requested supported model", () => {
    const supported = models.map((model) => ({
      ...model,
      has_initial_guess: ["spb", "dpb"].includes(model.id),
    }));
    expect(guessModel(supported, "spb")?.id).toBe("spb");
  });

  test("preserves mass magnitude in each mode while applying the carrier sign", async () => {
    useSessionStore.setState(useSessionStore.getInitialState(), true);
    const spb = models.find(({ id }) => id === "spb");
    if (!spb) throw new Error("Missing SPB model fixture");
    const measurement = rows(1e-4, 2e-4, 3e-4);
    useSessionStore.setState({
      data: { seebeck: { measurement } } as never,
      parameters: { spb_s: { band_mass: 1.7 } },
    });
    vi.spyOn(apiClient, "postGuess").mockResolvedValue({
      status: "numerical_guess",
      start_values: { band_mass: -1, fermi_energy: -700 },
      warnings: [],
    });
    await runGuess(spb, measurement);
    expect(useSessionStore.getState().parameters.spb_s?.band_mass).toBe(-1.7);
    expect(useSessionStore.getState().parameters.spb_s?.fermi_energy).toBe(
      -700,
    );
    expect(currentGuess(useSessionStore.getState())?.kind).toBe("applied");
  });
});
