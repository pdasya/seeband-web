import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:net";
import { networkInterfaces } from "node:os";
import { after, describe, test } from "node:test";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const MOCK = fileURLToPath(new URL("../scripts/mock.mjs", import.meta.url));
const POST_CONTRACT = fileURLToPath(
  new URL("./fixtures/post-contract.json", import.meta.url),
);
const JSON_HEADERS = { "content-type": "application/json" };

function freePort() {
  return new Promise((resolve) => {
    const probe = createServer();
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

const running = new Set();

function spawnMock({ contract, env = {} } = {}) {
  const mock = spawn(
    process.execPath,
    [MOCK, ...(contract ? [contract] : [])],
    {
      env: { ...process.env, ...env },
      stdio: ["ignore", "ignore", "pipe"],
    },
  );
  mock.stderrText = "";
  mock.stderr.on("data", (chunk) => (mock.stderrText += chunk));
  running.add(mock);
  mock.on("exit", () => running.delete(mock));
  return mock;
}

async function startMock({ contract, env = {} } = {}) {
  const port = await freePort();
  const mock = spawnMock({
    contract,
    env: { MOCK_PORT: String(port), ...env },
  });
  const url = `http://127.0.0.1:${port}`;
  while (mock.exitCode === null) {
    try {
      await fetch(`${url}/`);
      return { url, port, mock };
    } catch {
      await sleep(50);
    }
  }
  throw new Error(`The mock stopped: ${mock.stderrText}`);
}

function isRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function prismPid(mock) {
  return Number(
    execFileSync("pgrep", ["-P", String(mock.pid)], {
      encoding: "utf8",
    }).trim(),
  );
}

async function waitUntilStopped(pid) {
  for (let attempt = 0; attempt < 200 && isRunning(pid); attempt += 1) {
    await sleep(50);
  }
  return !isRunning(pid);
}

after(() => {
  for (const mock of running) {
    mock.kill();
  }
});

describe("the mock of the real contract", async () => {
  const { url } = await startMock();

  test("returns the example from the contract, with its headers", async () => {
    const response = await fetch(`${url}/api/health`);

    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), /application\/json/);
    assert.deepEqual(await response.json(), { status: "ok", version: "1.0.0" });
  });

  test("serves the real model descriptions", async () => {
    const response = await fetch(`${url}/api/models`);

    assert.equal(response.status, 200);
    const { models } = await response.json();
    const mode = models[0].fit_modes.find(({ id }) => id === "spb_s_rho_rh");
    assert.equal(mode.disabled, true);
    assert.deepEqual(mode.disabled_by, ["spb_hall_mode_disabled"]);
    assert.equal(response.headers.get("cache-control"), "no-cache");
    assert.match(response.headers.get("etag"), /^"[0-9a-f]{32}"$/);
  });

  test("serves a curve for a request that fits the contract", async () => {
    const response = await fetch(`${url}/api/calc`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        model: "dpb",
        fit_mode: "dpb_s",
        parameters: { m_eff: 1.01 },
        min_temperature_k: 100,
        max_temperature_k: 500,
      }),
    });

    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.temperature_k.length, 5);
    assert.equal(body.curves.seebeck_v_per_k.length, 5);
  });

  test("refuses a curve request that breaks the contract", async () => {
    const response = await fetch(`${url}/api/calc`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ model: "dpb" }),
    });

    assert.equal(response.status, 422);
    assert.equal((await response.json()).code, "validation_error");
  });

  for (const [status, code] of [
    [404, "not_found"],
    [422, "validation_error"],
    [500, "internal_error"],
    [422, "calculation_failed"],
    [409, "fit_mode_disabled"],
    [504, "calculation_timeout"],
    [503, "calculation_unavailable"],
    [422, "invalid_calculation"],
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
    assert.match(body.message, /hasn't been found/);
  });

  test("answers a wrong method in the API's error format", async () => {
    const response = await fetch(`${url}/api/health`, { method: "POST" });

    assert.equal(response.status, 405);
    assert.equal((await response.json()).code, "method_not_allowed");
  });

  test("marks an unknown example as a problem of the mock", async () => {
    for (const prefer of ["example=nope", "code=500, example=nope"]) {
      const response = await fetch(`${url}/api/health`, {
        headers: { prefer },
      });

      const body = await response.json();
      assert.equal(body.code, "mock_error", prefer);
      assert.notEqual(body.message, "");
    }
  });

  for (const path of ["/api/health", "/api/nothing"]) {
    test(`survives HEAD on ${path}`, async () => {
      const response = await fetch(`${url}${path}`, { method: "HEAD" });

      assert.ok(response.status >= 200);
      assert.equal((await fetch(`${url}/api/health`)).status, 200);
    });
  }
});

describe("a request to a route like those of api_router", async () => {
  const { url } = await startMock({ contract: POST_CONTRACT });
  const post = (body, { path = "/api/points", headers = JSON_HEADERS } = {}) =>
    fetch(`${url}${path}`, { method: "POST", headers, body });

  test("has an invalid field reported with its location", async () => {
    const response = await post(
      JSON.stringify({ temperature_k: [300, "warm"] }),
    );

    assert.equal(response.status, 422);
    const body = await response.json();
    assert.equal(body.code, "validation_error");
    assert.equal(body.details.length, 1);
    assert.deepEqual(body.details[0].location, ["body", "temperature_k", 1]);
    assert.equal(body.details[0].code, "type");
    assert.match(body.details[0].message, /must be number/);
  });

  test("has a missing body reported at the body", async () => {
    const response = await post(undefined);

    assert.equal(response.status, 422);
    const body = await response.json();
    assert.equal(body.code, "validation_error");
    assert.deepEqual(body.details[0].location, ["body"]);
  });

  test("has an unsupported content type answered as the API does", async () => {
    const response = await post("text", {
      headers: { "content-type": "text/plain" },
    });

    assert.equal(response.status, 422);
    const body = await response.json();
    assert.equal(body.code, "validation_error");
    assert.equal(body.details[0].code, "415");
  });

  test("has its query string checked", async () => {
    const response = await post(JSON.stringify({ temperature_k: [300] }), {
      path: "/api/points?limit=many",
    });

    assert.equal(response.status, 422);
    assert.deepEqual((await response.json()).details[0].location, [
      "query",
      "limit",
    ]);
  });

  test("has malformed JSON refused, rather than never answered", async () => {
    const response = await post("{not json", {});

    assert.equal(response.status, 422);
    const body = await response.json();
    assert.equal(body.code, "validation_error");
    assert.deepEqual(body.details, [
      {
        location: ["body"],
        code: "json_invalid",
        message: "JSON decode error",
      },
    ]);
  });

  test("passes when it is valid, with its body forwarded", async () => {
    const response = await post(JSON.stringify({ temperature_k: [300, 400] }));

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { count: 2 });
  });
});

describe("settings from the environment", async () => {
  const delayed = await startMock({ env: { MOCK_DELAY_MS: "300" } });
  const failing = await startMock({
    env: { MOCK_PREFER: "code=500, example=internal_error" },
  });

  for (const headers of [{}, { prefer: "code=200" }]) {
    test(`MOCK_DELAY_MS delays a request with headers ${JSON.stringify(headers)}`, async () => {
      const started = performance.now();
      await (await fetch(`${delayed.url}/api/health`, { headers })).text();

      assert.ok(performance.now() - started >= 290);
    });
  }

  test("a request cancelled during the delay does not stop the mock", async () => {
    await assert.rejects(
      fetch(`${delayed.url}/api/health`, { signal: AbortSignal.timeout(50) }),
      /timeout/i,
    );
    assert.equal((await fetch(`${delayed.url}/api/health`)).status, 200);
  });

  test("MOCK_PREFER applies to requests with no Prefer header", async () => {
    const response = await fetch(`${failing.url}/api/health`);

    assert.equal(response.status, 500);
    assert.equal((await response.json()).code, "internal_error");
  });

  test("a request's own Prefer header wins over MOCK_PREFER", async () => {
    const response = await fetch(`${failing.url}/api/health`, {
      headers: { prefer: "code=200" },
    });

    assert.equal(response.status, 200);
  });

  for (const env of [
    { MOCK_PORT: "abc" },
    { MOCK_PORT: "70000" },
    { MOCK_DELAY_MS: "abc" },
    { MOCK_DELAY_MS: "-5" },
    { MOCK_DELAY_MS: "1e12" },
  ]) {
    test(`refuses ${JSON.stringify(env)}`, async () => {
      const mock = spawnMock({ env });

      const [code] = await once(mock, "exit");
      assert.equal(code, 1);
      assert.match(
        mock.stderrText,
        /Mock API: MOCK_\w+ must be a whole number/,
      );
      assert.doesNotMatch(mock.stderrText, /\n\s+at /);
    });
  }
});

describe("the mock's processes", () => {
  test("listens only on the loopback interface", async (context) => {
    const { port } = await startMock();
    const external = Object.values(networkInterfaces())
      .flat()
      .find((address) => address.family === "IPv4" && !address.internal);
    if (!external) {
      context.skip("this machine has no other interface");
      return;
    }

    await assert.rejects(
      fetch(`http://${external.address}:${port}/api/health`),
    );
  });

  test("a busy port gives a clear error and starts nothing", async () => {
    const { port, url } = await startMock();

    const second = spawnMock({ env: { MOCK_PORT: String(port) } });
    const [code] = await once(second, "exit");

    assert.equal(code, 1);
    assert.match(
      second.stderrText,
      new RegExp(`Mock API: port ${port} is in use`),
    );
    assert.equal((await fetch(`${url}/api/health`)).status, 200);
  });

  test("stopping the mock stops Prism", async () => {
    const { mock } = await startMock();
    const pid = prismPid(mock);
    assert.ok(isRunning(pid));

    mock.kill("SIGTERM");

    assert.ok(await waitUntilStopped(pid));
  });

  test("Prism stopping stops the mock", async () => {
    const { mock } = await startMock();

    process.kill(prismPid(mock), "SIGKILL");
    const [code] = await once(mock, "exit");

    assert.equal(code, 1);
    assert.match(mock.stderrText, /Prism stopped/);
  });

  test("a contract that does not exist fails without a stack trace", async () => {
    const mock = spawnMock({
      contract: "/no/such/contract.json",
      env: { MOCK_PORT: String(await freePort()) },
    });

    const [code] = await once(mock, "exit");
    assert.equal(code, 1);
    assert.match(mock.stderrText, /Mock API: Prism stopped/);
  });
});
