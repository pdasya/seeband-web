// @vitest-environment node
import { beforeEach, describe, expect, test } from "vitest";

import {
  createSessionStore,
  type FitResult,
  type SessionData,
} from "@/session/store";

const RESULT: FitResult = {
  parameters: { m_eff: 1 },
  status: "converged",
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};
const DATA: SessionData = {
  measurement: {
    temperature_k: [100],
    values: [1e-4],
    points: 1,
    min_temperature_k: 100,
    max_temperature_k: 100,
  },
  source: { kind: "demo", messageKey: "demo_dataset.synthetic" },
  extrapolated: false,
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

describe("a change after a result", () => {
  test.each([
    ["data", () => state().setData("seebeck", DATA)],
    ["removed data", () => state().removeData("seebeck")],
    ["selection", () => state().setSelection({ fitMode: "dpb_s" })],
    ["parameters", () => state().setParameters({ m_eff: 2 })],
    ["one parameter", () => state().setParameter("m_eff", 2)],
  ])("%s clears the result, which no longer matches", (_, change) => {
    state().fitEvent(state().fitRequested(), { type: "done", result: RESULT });

    change();

    expect(state().fit).toEqual({ status: "idle" });
  });

  test("it leaves a running fit alone, as stopping it is the caller's", () => {
    state().fitEvent(state().fitRequested(), { type: "started" });

    state().setParameter("m_eff", 2);

    expect(state().fit.status).toBe("running");
    expect(state().parameters).toEqual({ m_eff: 2 });
  });
});

describe("the source of data", () => {
  const FILE = { name: "a.csv", text: "T S", mapping: [], table: null };

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
    state().setParameter("m_eff", 2);

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
    fresh.getState().setParameter("m_eff", 2);

    expect(writes).toEqual([]);
  });
});
