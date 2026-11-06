// @vitest-environment node
import { type ChildProcess, spawn } from "node:child_process";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, test } from "vitest";

import { ApiClient, type CalcRequest, type FitRequest } from "@/api/client";
import { streamFit, type FitEvent } from "@/api/fitStream";

// The mock of A2, serving the contract, so that the client and the contract cannot drift apart.
const MOCK = fileURLToPath(
  new URL("../../../../packages/api-client/scripts/mock.mjs", import.meta.url),
);
const STARTUP_TIMEOUT_MS = 30_000;

let mock: ChildProcess;
let baseUrl: string;

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        resolve(
          typeof address === "object" && address !== null ? address.port : 0,
        );
      });
    });
  });
}

function client(prefer?: string): ApiClient {
  return new ApiClient({
    baseUrl,
    fetch: (input, init) =>
      fetch(input, {
        ...init,
        headers: {
          ...(init?.headers as Record<string, string>),
          ...(prefer ? { Prefer: prefer } : {}),
        },
      }),
  });
}

beforeAll(async () => {
  const port = await freePort();
  baseUrl = `http://127.0.0.1:${String(port)}`;
  mock = spawn(process.execPath, [MOCK], {
    env: { ...process.env, MOCK_PORT: String(port) },
    stdio: "ignore",
  });
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok) {
        return;
      }
    } catch {
      // It has not started yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The mock did not start");
}, STARTUP_TIMEOUT_MS + 5_000);

afterAll(() => {
  mock.kill();
});

const FIT: FitRequest = {
  model: "dpb",
  fit_mode: "dpb_s",
  start: { m_eff: 1.01 },
  min_temperature_k: 100,
  max_temperature_k: 500,
  measurements: { seebeck: { temperature_k: [100], values: [1e-4] } },
} as FitRequest;
const CALC = {
  model: "dpb",
  fit_mode: "dpb_s",
  parameters: { m_eff: 1.01 },
  min_temperature_k: 100,
  max_temperature_k: 500,
} as CalcRequest;

async function events(prefer?: string): Promise<FitEvent[]> {
  const found: FitEvent[] = [];
  for await (const event of streamFit(client(prefer), FIT)) {
    found.push(event);
  }
  return found;
}

describe("against the mock", () => {
  test("each route gives its answer", async () => {
    const api = client();

    expect((await api.getHealth()).status).toBe("ok");
    expect((await api.getModels()).models.length).toBeGreaterThan(0);
    expect((await api.getDemo()).synthetic).toBe(true);
    expect((await api.postCalc(CALC)).temperature_k.length).toBeGreaterThan(0);
    expect(
      (await api.postParse({ text: "T S\n100 1e-6\n" })).row_count,
    ).toBeGreaterThan(0);
    expect(
      (
        await api.postGuess({
          model: "dpb",
          temperature_k: [100],
          seebeck_v_per_k: [1e-4],
        })
      ).status,
    ).toBe("guess");
  });

  test("a fit gives its events, in each example of the contract", async () => {
    const single = await events();
    expect(single.map((event) => event.type)).toEqual(["started", "done"]);

    const iterative = await events("example=iterative");
    expect(iterative.map((event) => event.type)).toEqual([
      "started",
      "iteration",
      "iteration",
      "done",
    ]);

    const failed = await events("example=fit_timeout");
    expect(failed.at(-1)).toMatchObject({
      type: "error",
      error: { code: "fit_timeout" },
    });
  });

  test("an error reaches the client in its form, with its hint", async () => {
    await expect(
      client("code=429, example=rate_limited").getHealth(),
    ).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
    });
    await expect(
      client("code=429, example=rate_limited").postGuess({
        model: "dpb",
        temperature_k: [100],
        seebeck_v_per_k: [1e-4],
      }),
    ).rejects.toMatchObject({ code: "rate_limited", retryAfterS: 5 });
    await expect(
      events("code=409, example=fit_mode_disabled"),
    ).rejects.toMatchObject({
      status: 409,
      code: "fit_mode_disabled",
    });
  });

  test("a request that breaks the contract lists its problems", async () => {
    await expect(
      client().postCalc({ model: "dpb" } as CalcRequest),
    ).rejects.toMatchObject({
      status: 422,
      code: "validation_error",
      details: expect.any(Array) as unknown,
    });
  });
});
