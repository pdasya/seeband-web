import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { after, describe, test } from "node:test";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const MOCK = fileURLToPath(new URL("../scripts/mock.mjs", import.meta.url));
const POST_CONTRACT = fileURLToPath(
  new URL("./fixtures/post-contract.json", import.meta.url),
);

function freePort() {
  return new Promise((resolve) => {
    const probe = createServer();
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

const running = [];

async function startMock({ contract, env = {} } = {}) {
  const port = await freePort();
  const mock = spawn(
    process.execPath,
    [MOCK, ...(contract ? [contract] : [])],
    {
      env: { ...process.env, MOCK_PORT: String(port), ...env },
      stdio: "ignore",
    },
  );
  running.push(mock);
  const url = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 600; attempt += 1) {
    try {
      await fetch(`${url}/`);
      return url;
    } catch {
      await sleep(50);
    }
  }
  throw new Error("The mock did not start");
}

after(() => {
  for (const mock of running) {
    mock.kill();
  }
});

describe("the mock of the real contract", async () => {
  const url = await startMock();

  test("returns the example from the contract", async () => {
    const response = await fetch(`${url}/api/health`);

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: "ok", version: "1.0.0" });
  });

  for (const [status, code] of [
    [404, "not_found"],
    [422, "validation_error"],
    [500, "internal_error"],
  ]) {
    test(`returns the ${code} example on request`, async () => {
      const response = await fetch(`${url}/api/health`, {
        headers: { prefer: `code=${status}, example=${code}` },
      });

      assert.equal(response.status, status);
      const body = await response.json();
      assert.equal(body.code, code);
      assert.ok(Array.isArray(body.details));
    });
  }

  test("answers an unknown path in the API's error format", async () => {
    const response = await fetch(`${url}/api/nothing`);

    assert.equal(response.status, 404);
    const body = await response.json();
    assert.equal(body.code, "not_found");
    assert.deepEqual(body.details, []);
    assert.equal(typeof body.message, "string");
  });

  test("answers a wrong method in the API's error format", async () => {
    const response = await fetch(`${url}/api/health`, { method: "POST" });

    assert.equal(response.status, 405);
    assert.equal((await response.json()).code, "method_not_allowed");
  });
});

describe("a request that breaks the contract", async () => {
  const url = await startMock({ contract: POST_CONTRACT });

  test("is refused in the API's error format", async () => {
    const response = await fetch(`${url}/api/points`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ temperature_k: "warm" }),
    });

    assert.equal(response.status, 422);
    const body = await response.json();
    assert.equal(body.code, "validation_error");
    assert.deepEqual(body.details[0].location, ["body", "temperature_k"]);
    assert.deepEqual(Object.keys(body.details[0]).sort(), [
      "code",
      "location",
      "message",
    ]);
  });

  test("passes when it is valid, with its body forwarded", async () => {
    const response = await fetch(`${url}/api/points`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ temperature_k: [300, 400] }),
    });

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { count: 2 });
  });
});

describe("settings from the environment", async () => {
  const delayed = await startMock({ env: { MOCK_DELAY_MS: "300" } });
  const failing = await startMock({
    env: { MOCK_PREFER: "code=500, example=internal_error" },
  });

  test("MOCK_DELAY_MS delays responses", async () => {
    const started = performance.now();
    await (await fetch(`${delayed}/api/health`)).text();

    assert.ok(performance.now() - started >= 290);
  });

  test("MOCK_PREFER applies to requests with no Prefer header", async () => {
    const response = await fetch(`${failing}/api/health`);

    assert.equal(response.status, 500);
    assert.equal((await response.json()).code, "internal_error");
  });

  test("a request's own Prefer header wins over MOCK_PREFER", async () => {
    const response = await fetch(`${failing}/api/health`, {
      headers: { prefer: "code=200" },
    });

    assert.equal(response.status, 200);
  });
});
