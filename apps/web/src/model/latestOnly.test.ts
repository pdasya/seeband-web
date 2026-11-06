// @vitest-environment node
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ApiError } from "@/api/errors";
import {
  DEBOUNCE_MS,
  LatestOnly,
  MAX_WAIT_MS,
  STUCK_AFTER_MS,
} from "@/model/latestOnly";

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
  const sender = new LatestOnly<string>({
    send: (body, signal) =>
      new Promise((resolve, reject) => {
        calls.push({ body, signal, resolve, reject });
      }),
    onResult: (result, body) => results.push([result, body]),
    onFailure: (error, settled) => failures.push([error.code, settled]),
  });
  return { calls, results, failures, sender };
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
