// @vitest-environment node
import { beforeEach, describe, expect, test } from "vitest";

import {
  createSessionStore,
  currentGuess,
  fitData,
  holdsFiles,
  type FitResult,
  type ParsedTable,
  type SessionData,
} from "@/session/store";

const RESULT: FitResult = {
  parameters: { m_eff: 1 },
  status: "converged",
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
  held: [],
};
const DATA: SessionData = {
  measurement: {
    temperature_k: [100],
    values: [1e-4],
    points: 1,
    min_temperature_k: 100,
    max_temperature_k: 100,
    loaded_as: "seebeck",
  },
  source: { kind: "demo", messageKey: "demo_dataset.synthetic" },
  extrapolated: false,
  text: "T S\n100 1e-4\n",
};

let store: ReturnType<typeof createSessionStore>;
const state = () => store.getState();

beforeEach(() => {
  store = createSessionStore();
});

describe("a fit", () => {
  test("goes from waiting through its events to a result", () => {
    const run = state().fitRequested();
    expect(state().fit).toEqual({ status: "waiting" });

    state().fitEvent(run, { type: "started" });
    expect(state().fit).toEqual({
      status: "running",
      iteration: null,
      lastParameters: null,
    });

    state().fitEvent(run, {
      type: "iteration",
      iteration: 2,
      parameters: { m_eff: 0.5, A: null },
    });
    expect(state().fit).toEqual({
      status: "running",
      iteration: 2,
      lastParameters: { m_eff: 0.5, A: null },
    });

    state().fitEvent(run, { type: "done", result: RESULT });
    expect(state().fit).toEqual({ status: "done", result: RESULT });
  });

  test("after a stop, the last values received stay", () => {
    const run = state().fitRequested();
    state().fitEvent(run, { type: "started" });
    state().fitEvent(run, {
      type: "iteration",
      iteration: 1,
      parameters: { m_eff: 0.5 },
    });

    state().fitStopped(run);

    expect(state().fit).toEqual({
      status: "stopped",
      iteration: 1,
      lastParameters: { m_eff: 0.5 },
    });
  });

  test("a stop while waiting has no values", () => {
    const run = state().fitRequested();

    state().fitStopped(run);

    expect(state().fit).toEqual({
      status: "stopped",
      iteration: null,
      lastParameters: null,
    });
  });

  test("events after a stop do not change it", () => {
    const run = state().fitRequested();
    state().fitStopped(run);
    const stopped = state().fit;

    state().fitEvent(run, { type: "done", result: RESULT });
    state().fitFailed(run, { code: "stream_ended", message: "m", details: [] });

    expect(state().fit).toBe(stopped);
  });

  test("an error event fails it, with the code to translate", () => {
    const error = { code: "fit_timeout", message: "m", details: [] };
    const run = state().fitRequested();

    state().fitEvent(run, { type: "error", error });

    expect(state().fit).toEqual({ status: "failed", failure: error });
  });

  test("a second run ignores everything from the first", () => {
    const first = state().fitRequested();
    state().fitEvent(first, { type: "started" });
    const second = state().fitRequested();
    expect(state().fit).toEqual({ status: "waiting" });

    state().fitEvent(first, { type: "done", result: RESULT });
    state().fitEvent(first, {
      type: "iteration",
      iteration: 9,
      parameters: {},
    });
    state().fitStopped(first);
    state().fitFailed(first, {
      code: "stream_ended",
      message: "m",
      details: [],
    });
    expect(state().fit).toEqual({ status: "waiting" });

    state().fitEvent(second, { type: "done", result: RESULT });
    expect(state().fit).toEqual({ status: "done", result: RESULT });
  });

  test("a stop with no fit running does nothing", () => {
    state().fitStopped(0);

    expect(state().fit).toEqual({ status: "idle" });
  });
});

describe("held parameters", () => {
  test("are kept for each mode, once each, and a reset releases those of its mode", () => {
    state().setHeld("dpb_s", "band_gap", true);
    state().setHeld("dpb_s", "band_gap", true);
    state().setHeld("dpb_s", "m_eff", true);
    state().setHeld("spb_s_rho", "A", true);
    state().setHeld("dpb_s", "m_eff", false);
    expect(state().held).toEqual({ dpb_s: ["band_gap"], spb_s_rho: ["A"] });

    state().resetParameters("dpb_s");
    expect(state().held).toEqual({ spb_s_rho: ["A"] });
  });
});

describe("a change after a result", () => {
  test.each([
    ["data", () => state().setData("seebeck", DATA)],
    ["removed data", () => state().removeData("seebeck")],
    ["selection", () => state().setSelection({ fitMode: "dpb_s" })],
    ["parameters", () => state().setParameters("dpb_s", { m_eff: 2 })],
    ["one parameter", () => state().setParameter("dpb_s", "m_eff", 2)],
    ["a held parameter", () => state().setHeld("dpb_s", "band_gap", true)],
  ])("%s clears the result, which no longer matches", (_, change) => {
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    change();

    expect(state().fit).toEqual({ status: "idle" });
  });

  test("it leaves a running fit alone, as stopping it is the caller's", () => {
    state().fitEvent(state().fitRequested(), { type: "started" });

    state().setParameter("dpb_s", "m_eff", 2);

    expect(state().fit.status).toBe("running");
    expect(state().parameters).toEqual({ dpb_s: { m_eff: 2 } });
  });
});

describe("the source of data", () => {
  const FILE = { name: "a.csv", text: "T S", mapping: [], table: null };
  const TABLE = {
    column_count: 2,
    row_count: 1,
    preview: [],
    mapping: [{ column: 0, role: "temperature" }],
    measurements: {},
    errors: [],
    warnings: [],
    warnings_omitted: 0,
  } as unknown as ParsedTable;

  test("changing it clears the data and the table, and leaves a running fit", () => {
    state().setData("seebeck", DATA);
    state().startSingleFile(FILE);
    state().fitEvent(state().fitRequested(), { type: "started" });

    state().setDataMode("single");

    expect(state().dataMode).toBe("single");
    expect(state().data).toEqual({});
    expect(state().singleFile).toBeNull();
    expect(state().fit.status).toBe("running");
  });

  test("coming back brings the files of that way", () => {
    state().setData("seebeck", DATA);
    state().setDataMode("single");
    const request = state().startSingleFile(FILE);
    state().finishSingleFile(TABLE);
    state().setData("hall", DATA);

    state().setDataMode("separate");
    expect(state().data).toEqual({ seebeck: DATA });
    expect(state().singleFile).toBeNull();

    state().setDataMode("single");
    expect(state().data).toEqual({ hall: DATA });
    expect(state().singleFile).toMatchObject({ table: TABLE, loading: false });
    expect(state().singleFile?.request).not.toBe(request);
  });

  test("a table still being read does not stay", () => {
    state().setDataMode("single");
    state().startSingleFile(FILE);

    state().setDataMode("separate");
    state().setDataMode("single");

    expect(state().singleFile).toBeNull();
  });

  test("a change of mapping on its way leaves the last answer", () => {
    state().setDataMode("single");
    state().startSingleFile(FILE);
    state().finishSingleFile(TABLE);
    state().startSingleFile({ ...FILE, mapping: [], table: TABLE });

    state().setDataMode("separate");
    state().setDataMode("single");

    expect(state().singleFile).toMatchObject({
      table: TABLE,
      mapping: TABLE.mapping,
      loading: false,
    });
  });

  test("files in either way count as files to lose", () => {
    expect(holdsFiles(state())).toBe(false);

    state().setData("seebeck", DATA);
    expect(holdsFiles(state())).toBe(true);

    state().setDataMode("single");
    expect(holdsFiles(state())).toBe(true);

    state().setDataMode("separate");
    state().removeData("seebeck");
    expect(holdsFiles(state())).toBe(false);
  });

  test("a read not yet answered is no file to lose", () => {
    state().setDataMode("single");
    state().startSingleFile(FILE);

    expect(holdsFiles(state())).toBe(false);
  });

  test("choosing the same one again clears nothing", () => {
    state().setData("seebeck", DATA);

    state().setDataMode("separate");

    expect(state().data).toEqual({ seebeck: DATA });
  });

  test("each read of a table has a new id, and failing keeps the last table", () => {
    const first = state().startSingleFile(FILE);
    const second = state().startSingleFile(FILE);
    state().failSingleFile("message");

    expect(second).toBeGreaterThan(first);
    expect(state().singleFile).toMatchObject({
      loading: false,
      failure: "message",
    });
  });
});

describe("interpolation", () => {
  const VALUES = {
    temperature_k: [50, 100],
    values: [5, 6],
    extrapolated: true,
    range_limited: false,
    measured_points_in_range: 1,
    underdetermined: false,
  };
  const measured = () => fitData(state(), "seebeck");

  test("off, a fit reads the measured data", () => {
    state().setData("seebeck", DATA);

    expect(measured()).toEqual({
      temperature_k: [100],
      values: [1e-4],
      extrapolated: false,
    });
  });

  test("on, a fit reads the interpolated values, and says that they are made up", () => {
    state().setData("seebeck", DATA);
    state().setInterpolationEnabled(true);
    state().finishInterpolation({ seebeck: VALUES }, []);

    expect(measured()).toEqual({
      temperature_k: [50, 100],
      values: [5, 6],
      extrapolated: true,
    });
  });

  test("turning it off restores the measured data exactly", () => {
    state().setData("seebeck", DATA);
    const before = state().data.seebeck;
    state().setInterpolationEnabled(true);
    state().finishInterpolation({ seebeck: VALUES }, []);

    state().setInterpolationEnabled(false);

    expect(state().data.seebeck).toBe(before);
    expect(state().interpolation.values).toEqual({});
    expect(measured()?.values).toEqual([1e-4]);
  });

  test.each([
    ["not answered yet", undefined],
    ["a value that is not finite", { ...VALUES, values: [5, null] }],
  ])(
    "on, with %s, a fit reads nothing rather than the measured data",
    (_, values) => {
      state().setData("seebeck", DATA);
      state().setInterpolationEnabled(true);
      state().finishInterpolation(
        values === undefined ? {} : { seebeck: values },
        [],
      );

      expect(measured()).toBeNull();
    },
  );

  test("new data drop values from the old data, and keep the switch on", () => {
    state().setData("seebeck", DATA);
    state().setInterpolationEnabled(true);
    state().finishInterpolation({ seebeck: VALUES }, ["hall"]);

    state().setData("seebeck", DATA);

    expect(state().interpolation).toMatchObject({
      enabled: true,
      values: {},
      failed: [],
    });
  });

  test("a change clears an old result, which was from other values", () => {
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    state().setInterpolationEnabled(true);

    expect(state().fit).toEqual({ status: "idle" });
  });

  test("a failure of one file says so, and leaves the others", () => {
    state().setInterpolationEnabled(true);

    state().finishInterpolation({ seebeck: VALUES }, ["hall"], "message");

    expect(state().interpolation).toMatchObject({
      values: { seebeck: VALUES },
      failed: ["hall"],
      failure: "message",
      loading: false,
    });
  });

  test("while it waits for an answer, a fit reads nothing, as the values are old", () => {
    state().setData("seebeck", DATA);
    state().setInterpolationEnabled(true);
    state().finishInterpolation({ seebeck: VALUES }, []);
    expect(measured()).not.toBeNull();

    state().startInterpolation();

    expect(measured()).toBeNull();
  });

  test("stopping clears the wait, and leaves the rest", () => {
    state().setInterpolationEnabled(true);
    state().startInterpolation();

    state().stopInterpolation();

    expect(state().interpolation).toMatchObject({
      enabled: true,
      loading: false,
    });
  });

  test("an answer does not clear a fit's result", () => {
    state().setInterpolationEnabled(true);
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    state().finishInterpolation({ seebeck: VALUES }, []);

    expect(state().fit.status).toBe("done");
  });
});

describe("parameters", () => {
  test("are kept per fit mode", () => {
    state().setParameter("dpb_s", "m_eff", 2);
    state().setParameter("dpb_s", "band_gap", 900);
    state().setParameter("dpb_s_rho", "m_eff", 3);

    expect(state().parameters).toEqual({
      dpb_s: { m_eff: 2, band_gap: 900 },
      dpb_s_rho: { m_eff: 3 },
    });
  });
});

describe("a fit's values", () => {
  const ITERATION = {
    type: "iteration" as const,
    iteration: 1,
    parameters: { m_eff: 2, band_gap: null },
  };

  test("go to its fit mode, and one that is not finite leaves the last", () => {
    state().setParameter("dpb_s", "band_gap", 900);
    state().setParameter("spb_s", "fermi_energy", 5);
    const run = state().fitRequested("dpb_s");
    state().fitEvent(run, { type: "started" });

    state().fitEvent(run, ITERATION);

    expect(state().parameters).toEqual({
      dpb_s: { band_gap: 900, m_eff: 2 },
      spb_s: { fermi_energy: 5 },
    });
  });

  test("the last answer's go there too", () => {
    const run = state().fitRequested("dpb_s");

    state().fitEvent(run, {
      type: "done",
      result: { ...RESULT, parameters: { m_eff: 3 } },
    });

    expect(state().parameters).toEqual({ dpb_s: { m_eff: 3 } });
    expect(state().fit.status).toBe("done");
  });

  test("with no fit mode named, stay out of the session", () => {
    const run = state().fitRequested();

    state().fitEvent(run, { type: "started" });
    state().fitEvent(run, ITERATION);

    expect(state().parameters).toEqual({});
  });

  test("of a run that was stopped do not count", () => {
    const run = state().fitRequested("dpb_s");
    state().fitEvent(run, { type: "started" });
    state().fitStopped(run);

    state().fitEvent(run, ITERATION);

    expect(state().parameters).toEqual({});
    expect(state().fit.status).toBe("stopped");
  });
});

describe("a guess", () => {
  const MEASUREMENT = DATA.measurement;
  const APPLIED = {
    kind: "applied" as const,
    netRange: { min_temperature_k: 100, max_temperature_k: 400 },
    warnings: [],
  };

  test("writes to each mode it names, and keeps the rest", () => {
    state().setParameter("dpb_s", "A", 7);
    state().setParameter("spb_s", "fermi_energy", 5);

    state().guessApplied(
      [
        { fitMode: "dpb_s", values: { m_eff: 2 } },
        { fitMode: "dpb_s_rho", values: { m_eff: 2 } },
      ],
      APPLIED,
      "dpb",
      MEASUREMENT,
    );

    expect(state().parameters).toEqual({
      dpb_s: { A: 7, m_eff: 2 },
      dpb_s_rho: { m_eff: 2 },
      spb_s: { fermi_energy: 5 },
    });
  });

  test("clears an old result, and holds until new values or data", () => {
    state().setData("seebeck", DATA);
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    state().guessApplied([], APPLIED, "dpb", MEASUREMENT);

    expect(state().fit.status).toBe("idle");
    expect(currentGuess(state())).toEqual(APPLIED);

    state().setParameter("dpb_s", "m_eff", 3);
    expect(currentGuess(state())).toBeNull();
  });

  test("one that changed nothing holds through new values, and not new data", () => {
    state().setData("seebeck", DATA);
    const outcome = { kind: "not_finite" as const, warnings: [] };

    state().guessFinished(outcome, "dpb", MEASUREMENT);
    state().setParameter("dpb_s", "m_eff", 3);
    expect(currentGuess(state())).toEqual(outcome);

    state().removeData("seebeck");
    expect(currentGuess(state())).toBeNull();
  });

  test("starting another ends the last, and an empty end leaves nothing", () => {
    state().guessFinished(
      { kind: "not_finite", warnings: [] },
      "dpb",
      MEASUREMENT,
    );

    state().guessStarted();
    expect(state().guessPending).toBe(true);
    expect(state().guess).toBeNull();

    state().guessDropped();
    expect(state().guessPending).toBe(false);
    expect(state().guess).toBeNull();
  });
});

describe("bounds of the user's", () => {
  const GAP = { lower: 500, upper: 1500 };

  test("belong to one mode, and null ends one of them", () => {
    state().setCustomBounds("dpb_s", "band_gap", GAP);
    state().setCustomBounds("dpb_s", "B", { lower: 0.95, upper: 1.05 });
    state().setCustomBounds("spb_s", "fermi_energy", GAP);

    state().setCustomBounds("dpb_s", "B", null);

    expect(state().customBounds).toEqual({
      dpb_s: { band_gap: GAP },
      spb_s: { fermi_energy: GAP },
    });
  });

  test("clearing and a reset end those of that mode alone", () => {
    state().setCustomBounds("dpb_s", "band_gap", GAP);
    state().setCustomBounds("spb_s", "fermi_energy", GAP);
    state().setCustomBounds("dpb_s_rho", "band_gap", GAP);

    state().clearCustomBounds("dpb_s");
    expect(Object.keys(state().customBounds).sort()).toEqual([
      "dpb_s_rho",
      "spb_s",
    ]);

    state().resetParameters("spb_s");
    expect(Object.keys(state().customBounds)).toEqual(["dpb_s_rho"]);
  });

  test("a change ends the last result, not a fit that runs", () => {
    state().fitEvent(state().fitRequested(), {
      type: "done",
      result: { status: "converged" },
    } as never);
    state().setCustomBounds("dpb_s", "band_gap", GAP);
    expect(state().fit.status).toBe("idle");

    state().fitRequested();
    state().setCustomBounds("dpb_s", "band_gap", null);
    expect(state().fit.status).toBe("waiting");

    state().clearCustomBounds("dpb_s");
    expect(state().fit.status).toBe("waiting");
  });
});

describe("resetting parameters", () => {
  test("clears only that fit mode, and an old result, and counts", () => {
    state().setParameter("dpb_s", "m_eff", 2);
    state().setParameter("spb_s", "fermi_energy", 5);
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });
    const before = state().parameterResets;

    state().resetParameters("dpb_s");

    expect(state().parameters).toEqual({ spb_s: { fermi_energy: 5 } });
    expect(state().fit.status).toBe("idle");
    expect(state().parameterResets).toBe(before + 1);
  });
});

describe("choosing a model", () => {
  const DPB = {
    fitMode: "dpb_s",
    scattering: null,
    band1Degeneracy: 2,
    band2Degeneracy: 3,
  };
  const SPB = {
    fitMode: "spb_s",
    scattering: null,
    band1Degeneracy: 1,
    band2Degeneracy: 1,
  };

  test("keeps the last model's settings and the range, and clears a result", () => {
    state().setSelection({ model: "dpb", ...DPB, minTemperatureK: 60 });
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    state().chooseModel("spb", SPB);

    expect(state().selection).toMatchObject({
      model: "spb",
      fitMode: "spb_s",
      band2Degeneracy: 1,
      minTemperatureK: 60,
    });
    expect(state().savedModelSettings).toEqual({ dpb: DPB });
    expect(state().fit).toEqual({ status: "idle" });
  });

  test("choosing the same model changes nothing", () => {
    state().setSelection({ model: "dpb", ...DPB });

    state().chooseModel("dpb", SPB);

    expect(state().selection.fitMode).toBe("dpb_s");
    expect(state().savedModelSettings).toEqual({});
  });
});

describe("session values", () => {
  test("data keep their source, and removing one leaves the others", () => {
    state().setData("seebeck", DATA);
    state().setData("hall", DATA);

    state().removeData("seebeck");

    expect(state().data).toEqual({ hall: DATA });
    expect(state().data.hall?.source).toEqual({
      kind: "demo",
      messageKey: "demo_dataset.synthetic",
    });
  });

  test("a selection changes only what it names", () => {
    state().setSelection({ model: "dpb" });
    state().setSelection({ fitMode: "dpb_s" });

    expect(state().selection).toMatchObject({
      model: "dpb",
      fitMode: "dpb_s",
      band1Degeneracy: 1,
    });
  });

  test("each store is separate", () => {
    state().setParameter("dpb_s", "m_eff", 2);

    expect(createSessionStore().getState().parameters).toEqual({});
  });

  test("nothing is written to browser storage", () => {
    const writes: string[] = [];
    const storage = {
      setItem: (key: string) => writes.push(key),
      getItem: () => null,
      removeItem: () => undefined,
    };
    Object.assign(globalThis, {
      localStorage: storage,
      sessionStorage: storage,
    });

    const fresh = createSessionStore();
    fresh.getState().setData("seebeck", DATA);
    fresh.getState().setParameter("dpb_s", "m_eff", 2);

    expect(writes).toEqual([]);
  });
});

describe("the start of a fit", () => {
  const APPLIED = {
    kind: "applied" as const,
    netRange: { min_temperature_k: 300, max_temperature_k: 800 },
    warnings: [],
  };
  const SETTINGS = {
    fitMode: null,
    scattering: null,
    band1Degeneracy: 1,
    band2Degeneracy: 1,
  };

  function guessed() {
    state().setData("seebeck", DATA);
    state().chooseModel("dpb", SETTINGS);
    state().guessApplied(
      [{ fitMode: "dpb_s", values: { m_eff: 2 } }],
      APPLIED,
      "dpb",
      DATA.measurement,
    );
  }

  test("names the net whose guess it starts from", () => {
    guessed();
    state().fitRequested("dpb_s");
    expect(state().fitStartNet).toEqual(APPLIED.netRange);
  });

  test("a numerical SPB start has no neural network range", () => {
    state().setData("seebeck", DATA);
    state().chooseModel("spb", SETTINGS);
    state().guessApplied(
      [{ fitMode: "spb_s", values: { band_mass: -1.7, fermi_energy: -700 } }],
      { kind: "applied", warnings: [] },
      "spb",
      DATA.measurement,
    );
    state().fitRequested("spb_s");
    expect(state().fitStartNet).toBeNull();
  });

  test("an edit after the guess makes the values the user's", () => {
    guessed();
    state().setParameter("dpb_s", "m_eff", 3);
    state().fitRequested("dpb_s");
    expect(state().fitStartNet).toBeNull();
  });

  test("a reset makes them the defaults", () => {
    guessed();
    state().resetParameters("dpb_s");
    state().fitRequested("dpb_s");
    expect(state().fitStartNet).toBeNull();
  });

  test("a fit of another model did not start from it", () => {
    guessed();
    state().chooseModel("spb", SETTINGS);
    state().fitRequested("spb_s");
    expect(state().fitStartNet).toBeNull();
  });

  test("each fit says its own start", () => {
    guessed();
    state().fitRequested("dpb_s");
    state().setParameter("dpb_s", "m_eff", 3);
    state().fitRequested("dpb_s");
    expect(state().fitStartNet).toBeNull();
  });
});

test("a fit keeps the values it started from", () => {
  state().fitRequested("dpb_s", { m_eff: 1.5, band_gap: 900 });
  expect(state().fitStartValues).toEqual({ m_eff: 1.5, band_gap: 900 });
  state().fitRequested("dpb_s");
  expect(state().fitStartValues).toBeNull();
});
