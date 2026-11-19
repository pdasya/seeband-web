// @vitest-environment node
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
  type MockInstance,
} from "vitest";

import { ApiError } from "@/api/errors";
import {
  DEBOUNCE_MS,
  LatestOnly,
  MAX_WAIT_MS,
  STUCK_AFTER_MS,
  retriesByItself,
} from "@/model/latestOnly";
import { setTimingEnabled } from "@/model/timing";

interface Call {
  body: string;
  signal: AbortSignal;
  resolve: (result: string) => void;
  reject: (error: unknown) => void;
}

function setUp() {
  const calls: Call[] = [];
  const results: [string, string][] = [];
  const failures: [string, string | null][] = [];
  const sentBodies: string[] = [];
  const sender = new LatestOnly<string>({
    send: (body, signal) =>
      new Promise((resolve, reject) => {
        calls.push({ body, signal, resolve, reject });
      }),
    onResult: (result, body) => results.push([result, body]),
    onFailure: (error, settled, sent) => {
      failures.push([error.code, settled]);
      sentBodies.push(sent);
    },
  });
  return { calls, results, failures, sentBodies, sender };
}

const rest = () => vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
const limit = (retryAfterS: number | null) =>
  new ApiError(429, "rate_limited", "x", [], retryAfterS);

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("changes", () => {
  test("wait for the debounce, and only the last goes", async () => {
    const { calls, sender } = setUp();

    sender.change("a", false);
    await vi.advanceTimersByTimeAsync(100);
    sender.change("b", false);
    await vi.advanceTimersByTimeAsync(100);
    expect(calls).toHaveLength(0);

    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
    expect(calls.map(({ body }) => body)).toEqual(["b"]);
  });

  test("that never rest still go at the longest wait", async () => {
    const { calls, sender } = setUp();

    for (let step = 0; step < 6; step += 1) {
      sender.change(String(step), false);
      await vi.advanceTimersByTimeAsync(MAX_WAIT_MS / 3);
    }

    expect(calls.length).toBeGreaterThanOrEqual(1);
  });

  test("the same values send nothing", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    calls[0]?.resolve("A");
    await rest();

    sender.change("a", false);
    await rest();

    expect(calls).toHaveLength(1);
  });

  test("back to the values just answered send nothing", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    calls[0]?.resolve("A");
    await rest();

    sender.change("b", false);
    sender.change("a", false);
    await rest();

    expect(calls).toHaveLength(1);
  });
});

describe("one request at a time", () => {
  test("however many changes come during it, and the latest goes after it", async () => {
    const { calls, results, sender } = setUp();
    sender.change("a", false);
    await rest();

    for (let step = 0; step < 30; step += 1) {
      sender.change(String(step), false);
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    }
    expect(calls).toHaveLength(1);
    expect(calls[0]?.signal.aborted).toBe(false);

    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    expect(results).toEqual([["A", "a"]]);
    expect(calls.map(({ body }) => body)).toEqual(["a", "29"]);
  });

  test("the answer leaves a debounce that is still waiting to finish", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    sender.change("b", false);

    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toHaveLength(1);

    await rest();
    expect(calls.map(({ body }) => body)).toEqual(["a", "b"]);
  });

  test("a failure lets the latest values go too", async () => {
    const { calls, failures, sender } = setUp();
    sender.change("a", false);
    await rest();
    sender.change("b", false);
    await rest();

    calls[0]?.reject(new ApiError(422, "calculation_failed", "x"));
    await vi.advanceTimersByTimeAsync(0);

    expect(failures).toEqual([["calculation_failed", "a"]]);
    expect(calls.map(({ body }) => body)).toEqual(["a", "b"]);
  });

  test("a failure of the latest values does not repeat by itself", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();

    calls[0]?.reject(new ApiError(503, "calculation_unavailable", "x"));
    await vi.advanceTimersByTimeAsync(STUCK_AFTER_MS);

    expect(calls).toHaveLength(1);
  });

  test("a request with no answer ends, and does not block later values", async () => {
    const { calls, failures, sender } = setUp();
    sender.change("a", false);
    await rest();
    sender.change("b", false);
    await rest();

    await vi.advanceTimersByTimeAsync(STUCK_AFTER_MS);

    expect(calls[0]?.signal.aborted).toBe(true);
    expect(failures).toEqual([["calculation_timeout", "a"]]);
    expect(calls.map(({ body }) => body)).toEqual(["a", "b"]);
  });
});

describe("a limit with Retry-After", () => {
  test("sends the values again after it", async () => {
    const { calls, failures, sender } = setUp();
    sender.change("a", false);
    await rest();

    calls[0]?.reject(limit(2));
    await vi.advanceTimersByTimeAsync(1999);
    expect(calls).toHaveLength(1);
    expect(failures).toEqual([["rate_limited", null]]);

    await vi.advanceTimersByTimeAsync(1);
    expect(calls.map(({ body }) => body)).toEqual(["a", "a"]);
  });

  test("arriving during a newer change's debounce sends only the newer values", async () => {
    const { calls, sender } = setUp();
    sender.change("old", false);
    await rest();
    sender.change("new", false);

    calls[0]?.reject(limit(1));
    await vi.advanceTimersByTimeAsync(5000);

    expect(calls.map(({ body }) => body)).toEqual(["old", "new"]);
  });

  test("holds changes back until it has passed", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    calls[0]?.reject(limit(2));
    await vi.advanceTimersByTimeAsync(0);

    sender.change("b", false);
    await rest();
    sender.change("c", false);
    await rest();
    expect(calls).toHaveLength(1);

    await vi.advanceTimersByTimeAsync(2000);
    expect(calls.map(({ body }) => body)).toEqual(["a", "c"]);
  });

  test("with no time or a long one, waits for the next change", async () => {
    for (const retryAfterS of [null, 31]) {
      const { calls, failures, sender } = setUp();
      sender.change("a", false);
      await rest();

      calls[0]?.reject(limit(retryAfterS));
      await vi.advanceTimersByTimeAsync(60_000);

      expect(calls).toHaveLength(1);
      expect(failures).toEqual([["rate_limited", "a"]]);

      sender.change("b", false);
      await rest();
      expect(calls).toHaveLength(2);
    }
  });

  test("says which values failed, also while another try is on its way", async () => {
    const { calls, failures, sentBodies, sender } = setUp();
    sender.change("a", false);
    await rest();

    calls[0]?.reject(limit(1));
    await vi.advanceTimersByTimeAsync(0);

    expect(failures).toEqual([["rate_limited", null]]);
    expect(sentBodies).toEqual(["a"]);
  });

  test("does not fire once there is nothing to ask", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    calls[0]?.reject(limit(1));
    await vi.advanceTimersByTimeAsync(0);

    sender.change(null, false);
    await vi.advanceTimersByTimeAsync(5000);

    expect(calls).toHaveLength(1);
  });
});

describe("waiting", () => {
  test("holds values back, and they go when it ends", async () => {
    const { calls, sender } = setUp();

    sender.change("a", true);
    await vi.advanceTimersByTimeAsync(5000);
    expect(calls).toHaveLength(0);

    sender.change("b", false);
    await rest();
    expect(calls.map(({ body }) => body)).toEqual(["b"]);
  });

  test("with the same values at the end, sends nothing new", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    sender.change("a", true);
    sender.change("a", false);
    await rest();

    expect(calls).toHaveLength(1);
  });
});

describe("stopping", () => {
  test("nothing to ask aborts what runs, and its answer is ignored", async () => {
    const { calls, results, sender } = setUp();
    sender.change("a", false);
    await rest();

    sender.change(null, false);
    expect(calls[0]?.signal.aborted).toBe(true);

    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);
    expect(results).toEqual([]);
  });

  test("a request that was stopped does not count as stuck later", async () => {
    const { failures, sender } = setUp();
    sender.change("a", false);
    await rest();

    sender.change(null, false);
    await vi.advanceTimersByTimeAsync(STUCK_AFTER_MS);

    expect(failures).toEqual([]);
  });

  test("the same values after that ask again", async () => {
    const { calls, sender } = setUp();
    sender.change("a", false);
    await rest();
    sender.change(null, false);

    sender.change("a", false);
    await rest();

    expect(calls).toHaveLength(2);
  });

  test("dispose ends everything, and a later change starts again", async () => {
    const { calls, results, sender } = setUp();
    sender.change("a", false);
    sender.dispose();
    await rest();
    expect(calls).toHaveLength(0);

    sender.change("a", false);
    await rest();
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);
    expect(results).toEqual([["A", "a"]]);
  });
});

describe("a busy server", () => {
  test("is tried again after its Retry-After, as a rate limit is", () => {
    expect(
      retriesByItself(new ApiError(503, "calculation_busy", "x", [], 2)),
    ).toBe(true);
    expect(
      retriesByItself(new ApiError(429, "client_calc_limit", "x", [], 1)),
    ).toBe(true);
  });

  test("is not tried again with no Retry-After, as when a worker died", () => {
    expect(
      retriesByItself(new ApiError(503, "calculation_unavailable", "x")),
    ).toBe(false);
    expect(
      retriesByItself(new ApiError(503, "calculation_busy", "x", [], 600)),
    ).toBe(false);
  });
});

describe("timing", () => {
  let clockMs = 0;
  let measure: MockInstance<Performance["measure"]>;
  const at = (ms: number) => {
    clockMs = ms;
  };
  const measured = (name: string) =>
    measure.mock.calls
      .filter(([entry]) => entry === `seeband:curves:${name}`)
      .map(([, span]) => span);

  beforeEach(() => {
    setTimingEnabled(true);
    clockMs = 0;
    vi.spyOn(performance, "now").mockImplementation(() => clockMs);
    measure = vi.spyOn(performance, "measure").mockImplementation(() => {
      return undefined as unknown as PerformanceMeasure;
    });
  });
  afterEach(() => {
    setTimingEnabled(false);
    vi.restoreAllMocks();
  });

  function timed() {
    const calls: Call[] = [];
    const answers: (number | null)[] = [];
    const sender = new LatestOnly<string>({
      send: (body, signal) =>
        new Promise((resolve, reject) => {
          calls.push({ body, signal, resolve, reject });
        }),
      onResult: (_result, _body, changedAtMs) => answers.push(changedAtMs),
      onFailure: () => undefined,
      timing: "curves",
    });
    return { calls, answers, sender };
  }

  test("times a request from sending, and the wait from the last change, to the answer", async () => {
    const { calls, answers, sender } = timed();
    at(100);
    sender.change("a", false);
    at(350);
    await rest();
    at(500);
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    expect(measured("request")).toEqual([{ start: 350, end: 500 }]);
    expect(measured("change-to-answer")).toEqual([{ start: 100, end: 500 }]);
    expect(answers).toEqual([100]);
  });

  test("an answer for values already left times the request, not the wait", async () => {
    const { calls, answers, sender } = timed();
    at(100);
    sender.change("a", false);
    await rest();
    at(400);
    sender.change("b", false);
    at(450);
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    expect(measured("request")).toHaveLength(1);
    expect(measured("change-to-answer")).toEqual([]);
    expect(answers).toEqual([null]);

    await rest();
    at(900);
    calls[1]?.resolve("B");
    await vi.advanceTimersByTimeAsync(0);
    expect(measured("change-to-answer")).toEqual([{ start: 400, end: 900 }]);
    expect(answers).toEqual([null, 400]);
  });

  test("a change of waiting alone does not restart the wait", async () => {
    const { calls, sender } = timed();
    at(100);
    sender.change("a", true);
    at(300);
    sender.change("a", false);
    await rest();
    at(700);
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    expect(measured("change-to-answer")).toEqual([{ start: 100, end: 700 }]);
  });

  test("times a failure from sending", async () => {
    const { calls, sender } = timed();
    sender.change("a", false);
    at(200);
    await rest();
    at(260);
    calls[0]?.reject(new ApiError(500, "calc_failed", "x"));
    await vi.advanceTimersByTimeAsync(0);

    expect(measured("failed")).toEqual([{ start: 200, end: 260 }]);
    expect(measured("request")).toEqual([]);
  });

  test("records nothing unless turned on, or without a name", async () => {
    setTimingEnabled(false);
    const { calls, sender } = timed();
    sender.change("a", false);
    await rest();
    calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    setTimingEnabled(true);
    const unnamed = setUp();
    unnamed.sender.change("a", false);
    await rest();
    unnamed.calls[0]?.resolve("A");
    await vi.advanceTimersByTimeAsync(0);

    expect(measure).not.toHaveBeenCalled();
  });
});
