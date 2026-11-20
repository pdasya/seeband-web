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
    state().setSelection({ model: "dpb", fitMode: "dpb_s" });
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

  test("automatic estimates preserve manual starts across repeated guesses in every mode", async () => {
    const measurement = rows(1, 2);
    holdS(measurement);
    state().setParameter("dpb_s", "band_gap", 901);
    state().setParameter("dpb_s_rho", "m_eff", 4);
    vi.spyOn(apiClient, "postGuess").mockResolvedValue(ANSWER as never);

    await runGuess(dpb, measurement, "automatic");
    await runGuess(dpb, measurement, "automatic");

    expect(state().parameters.dpb_s?.band_gap).toBe(901);
    expect(state().parameters.dpb_s_rho?.m_eff).toBe(4);
    expect(state().parameters.dpb_s?.fermi_energy).toBe(1170);
  });

  test.each(["automatic", "requested"] as const)(
    "%s estimates preserve held values in every mode, including a hold added while waiting",
    async (intent) => {
      for (const { id } of dpb.fit_modes) {
        state().setParameter(id, "band_gap", 902);
        state().setHeld(id, "band_gap", true);
      }
      const measurement = rows(1, 2);
      let resolve: (answer: unknown) => void = () => undefined;
      vi.spyOn(apiClient, "postGuess").mockReturnValue(
        new Promise((done) => {
          resolve = done;
        }) as never,
      );
      holdS(measurement);
      const run = runGuess(dpb, measurement, intent);
      state().setHeld("dpb_s", "fermi_energy", true);
      resolve(ANSWER);
      await run;
      for (const { id } of dpb.fit_modes)
        expect(state().parameters[id]?.band_gap).toBe(902);
      expect(state().parameters.dpb_s?.fermi_energy).toBeUndefined();
    },
  );

  test("manual edits after a guess remain manual even when set to the same number", async () => {
    const measurement = rows(1, 2);
    holdS(measurement);
    const post = vi
      .spyOn(apiClient, "postGuess")
      .mockResolvedValue(ANSWER as never);
    await runGuess(dpb, measurement, "automatic");
    state().setParameter("dpb_s", "band_gap", 554);
    post.mockResolvedValue({
      ...ANSWER,
      start_values: { ...ANSWER.start_values, band_gap: 700 },
    } as never);
    await runGuess(dpb, measurement, "automatic");
    expect(state().parameters.dpb_s?.band_gap).toBe(554);
    expect(state().parameters.dpb_s_rho?.band_gap).toBe(700);
    await runGuess(dpb, measurement, "requested");
    expect(state().parameters.dpb_s?.band_gap).toBe(700);
  });

  test("legacy stored starts are manual and no eligible values gives no applied badge", async () => {
    const measurement = rows(1, 2);
    holdS(measurement);
    useSessionStore.setState({
      parameters: Object.fromEntries(
        dpb.fit_modes.map(({ id, parameters }) => [
          id,
          Object.fromEntries(
            parameters.map(({ name, core_range }) => [
              name,
              core_range.default,
            ]),
          ),
        ]),
      ),
    });
    const before = state().parameters;
    vi.spyOn(apiClient, "postGuess").mockResolvedValue(ANSWER as never);
    await runGuess(dpb, measurement, "automatic");
    expect(state().parameters).toBe(before);
    expect(currentGuess(state())?.kind).toBe("unchanged");
    expect(state().guessPending).toBe(false);
  });

  test("an edit during a requested guess wins and keeps the estimate stale", async () => {
    const answer = waiting(rows(1, 2));
    state().setParameter("dpb_s", "band_gap", 903);
    await answer();
    expect(applied()).toBe(903);
    expect(state().parameters.dpb_s_rho).toBeUndefined();
    expect(currentGuess(state())).toBeNull();
  });

  test.each(["unsupported", "failed"] as const)(
    "%s guesses retain manual values and settings for forward evaluation",
    async (kind) => {
      const measurement = rows(1, 2);
      holdS(measurement);
      state().setParameter("dpb_s", "band_gap", 904);
      state().setCustomBounds("dpb_s", "band_gap", { lower: 800, upper: 1000 });
      state().setSelection({ band1Degeneracy: 3, band2Degeneracy: 5 });
      const before = state();
      const post = vi.spyOn(apiClient, "postGuess");
      if (kind === "unsupported")
        post.mockResolvedValue({
          status: "unsupported",
          reason: "sign_change",
          warnings: [],
        });
      else post.mockRejectedValue(new Error("unavailable"));
      await runGuess(dpb, measurement, "automatic");
      expect(state().parameters).toBe(before.parameters);
      expect(state().customBounds).toBe(before.customBounds);
      expect(state().selection).toBe(before.selection);
      expect(currentGuess(state())?.kind).toBe(kind);
    },
  );

  test("successful estimates retain custom bounds and valley counts", async () => {
    state().setCustomBounds("dpb_s", "band_gap", { lower: 200, upper: 1000 });
    state().setSelection({ band1Degeneracy: 3, band2Degeneracy: 5 });
    const before = state();
    await waiting(rows(1, 2))();
    expect(state().customBounds).toBe(before.customBounds);
    expect(state().selection).toBe(before.selection);
    expect(applied()).toBe(554);
  });

  test("guess badges and fit provenance follow modes that received suggestions", async () => {
    const measurement = rows(1, 2);
    holdS(measurement);
    state().setSelection({ fitMode: "dpb_s" });
    for (const { name, core_range } of dpb.fit_modes[0]?.parameters ?? [])
      state().setParameter("dpb_s", name, core_range.default);
    vi.spyOn(apiClient, "postGuess").mockResolvedValue({
      ...ANSWER,
      warnings: ["underdetermined_fit"],
    } as never);
    await runGuess(dpb, measurement, "automatic");
    const unchanged = currentGuess(state());
    expect(unchanged?.kind).toBe("unchanged");
    expect(currentGuess(state())).toBe(unchanged);
    expect(currentGuess(state())?.warnings).toContain("underdetermined_fit");
    state().fitRequested("dpb_s");
    expect(state().fitStartNet).toBeNull();
    state().setSelection({ fitMode: "dpb_s_rho" });
    expect(currentGuess(state())?.kind).toBe("applied");
    state().fitRequested("dpb_s_rho");
    expect(state().fitStartNet).toEqual(ANSWER.net_range);
  });

  test("a pending estimate is dropped when scattering changes", async () => {
    const answer = waiting(rows(1, 2));
    state().setSelection({ scattering: "ionized" });
    await answer();
    expect(applied()).toBeUndefined();
    expect(state().guessPending).toBe(false);
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

  test.each(["automatic", "requested"] as const)(
    "%s preserves fixed masses and applies only the sign to eligible mass magnitudes",
    async (intent) => {
      useSessionStore.setState(useSessionStore.getInitialState(), true);
      useSessionStore
        .getState()
        .setSelection({ model: "spb", fitMode: "spb_s" });
      const spb = models.find(({ id }) => id === "spb");
      if (!spb) throw new Error("Missing SPB model fixture");
      const measurement = rows(1e-4, 2e-4, 3e-4);
      useSessionStore.setState({
        data: { seebeck: { measurement } } as never,
        parameters: {
          spb_s: { band_mass: 1.7 },
          spb_s_rho_rh: { band_mass: 2.3 },
        },
        guessedParameters: { spb_s_rho_rh: { band_mass: 2.3 } },
      });
      vi.spyOn(apiClient, "postGuess").mockResolvedValue({
        status: "numerical_guess",
        sign_only_parameters: ["band_mass"],
        rmse_v_per_k: 0,
        start_values: { band_mass: -1, fermi_energy: -700 },
        warnings: [],
      });
      await runGuess(spb, measurement, intent);
      expect(useSessionStore.getState().parameters.spb_s?.band_mass).toBe(1.7);
      expect(
        useSessionStore.getState().parameters.spb_s_rho?.band_mass,
      ).toBeUndefined();
      expect(
        useSessionStore.getState().parameters.spb_s_rho_rh?.band_mass,
      ).toBe(-2.3);
      expect(useSessionStore.getState().parameters.spb_s?.fermi_energy).toBe(
        -700,
      );
      expect(currentGuess(useSessionStore.getState())?.kind).toBe("applied");
    },
  );
});

test("a load is tracked independently for each model", () => {
  const measurement = rows(9, 8, 7);
  expect(isNewLoad(measurement, "spb")).toBe(true);
  expect(isNewLoad(measurement, "dpb")).toBe(true);
  expect(isNewLoad(measurement, "spb")).toBe(false);
});
