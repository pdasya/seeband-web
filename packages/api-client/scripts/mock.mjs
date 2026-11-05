// Serves the OpenAPI contract with Prism, for working on the client without the API.
//
// A small proxy stands in front of Prism, because Prism:
// - cannot delay a response;
// - answers an invalid request with the first example of `default`, or in its own format;
// - answers its other errors in its own format;
// - never answers a malformed JSON body.
//
// Usage: node scripts/mock.mjs [contract file]
// Environment: MOCK_PORT, MOCK_DELAY_MS, and MOCK_PREFER, a Prefer header for requests with none.
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { createServer as createTcpServer } from "node:net";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const HOST = "127.0.0.1";
const PRISM_ERROR_PREFIX = "https://stoplight.io/prism/errors#";
const PRISM_ERROR_CODES = new Map([
  ["NO_PATH_MATCHED_ERROR", "not_found"],
  ["NO_METHOD_MATCHED_ERROR", "method_not_allowed"],
]);
const UPSTREAM_TIMEOUT_MS = 30_000;
const MAX_DELAY_MS = 600_000;
const HEADERS_NOT_FORWARDED = new Set([
  "connection",
  "content-length",
  "expect",
  "host",
  "keep-alive",
  "transfer-encoding",
]);

function fail(message) {
  console.error(`Mock API: ${message}`);
  process.exit(1);
}

function integerSetting(name, fallback, minimum, maximum) {
  const text = process.env[name] ?? String(fallback);
  const value = Number(text);
  if (
    text.trim() === "" ||
    !Number.isInteger(value) ||
    value < minimum ||
    value > maximum
  ) {
    fail(
      `${name} must be a whole number from ${minimum} to ${maximum}, not "${text}"`,
    );
  }
  return value;
}

const contract =
  process.argv[2] ?? fileURLToPath(new URL("../openapi.json", import.meta.url));
const port = integerSetting("MOCK_PORT", 4010, 1, 65535);
const delayMs = integerSetting("MOCK_DELAY_MS", 0, 0, MAX_DELAY_MS);
const defaultPrefer = process.env.MOCK_PREFER;

function error(code, message, details = []) {
  return { code, message, details };
}

function sendJson(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function isMalformedJson(incoming, body) {
  return (
    body.length > 0 &&
    incoming.headers["content-type"]?.includes("json") &&
    parseJson(body.toString("utf8")) === undefined
  );
}

function toErrorLocation(location) {
  const parts = (Array.isArray(location) ? location : []).filter(
    (part) => part !== "request",
  );
  const typed = parts.map((part) => (/^\d+$/.test(part) ? Number(part) : part));
  return typed.length > 0 ? typed : ["body"];
}

function toValidationError(violations) {
  return error(
    "validation_error",
    "Invalid request",
    violations.map((violation) => ({
      location: toErrorLocation(violation.location),
      code: String(violation.code),
      message: String(violation.message),
    })),
  );
}

function toPrismError(problem) {
  const name = problem.type.slice(PRISM_ERROR_PREFIX.length);
  return error(
    PRISM_ERROR_CODES.get(name) ?? "mock_error",
    problem.detail || problem.title || "The mock could not answer this request",
  );
}

function isPrismProblem(problem) {
  return (
    typeof problem?.type === "string" &&
    problem.type.startsWith(PRISM_ERROR_PREFIX)
  );
}

function forwardedHeaders(headers) {
  return Object.fromEntries(
    Object.entries(headers).filter(
      ([name]) => !HEADERS_NOT_FORWARDED.has(name),
    ),
  );
}

async function callPrism(prismPort, incoming, body, clientGone) {
  const prefer = incoming.headers.prefer ?? defaultPrefer;
  return fetch(`http://${HOST}:${prismPort}${incoming.url}`, {
    method: incoming.method,
    headers: {
      ...forwardedHeaders(incoming.headers),
      ...(prefer ? { prefer } : {}),
    },
    body: ["GET", "HEAD"].includes(incoming.method) ? undefined : body,
    redirect: "manual",
    signal: AbortSignal.any([
      clientGone,
      AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    ]),
  });
}

async function answer(prismPort, incoming, response, clientGone) {
  const chunks = [];
  for await (const chunk of incoming) {
    chunks.push(chunk);
  }
  const body = Buffer.concat(chunks);
  await sleep(delayMs, undefined, { signal: clientGone });

  if (isMalformedJson(incoming, body)) {
    const detail = {
      location: ["body"],
      code: "json_invalid",
      message: "JSON decode error",
    };
    sendJson(
      response,
      422,
      error("validation_error", "Invalid request", [detail]),
    );
    return;
  }

  const upstream = await callPrism(prismPort, incoming, body, clientGone);
  const upstreamBody = Buffer.from(await upstream.arrayBuffer());

  const violations = parseJson(upstream.headers.get("sl-violations") ?? "");
  if (
    upstream.status >= 400 &&
    Array.isArray(violations) &&
    violations.length > 0
  ) {
    sendJson(response, 422, toValidationError(violations));
    return;
  }
  const problem = parseJson(upstreamBody.toString("utf8"));
  if (isPrismProblem(problem)) {
    sendJson(response, upstream.status, toPrismError(problem));
    return;
  }
  if (
    upstream.headers.get("content-type")?.includes("application/problem+json")
  ) {
    // Prism sends no body on HEAD, so this can only be one of its own errors.
    const code = upstream.status === 404 ? "not_found" : "mock_error";
    sendJson(
      response,
      upstream.status,
      error(code, "The mock could not answer this request"),
    );
    return;
  }
  response.writeHead(
    upstream.status,
    forwardedHeaders(Object.fromEntries(upstream.headers.entries())),
  );
  response.end(upstreamBody);
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const probe = createTcpServer();
    probe.on("error", reject);
    probe.listen(0, HOST, () => {
      const { port: free } = probe.address();
      probe.close(() => resolve(free));
    });
  });
}

function startPrism(prismPort) {
  const prism = spawn(
    fileURLToPath(new URL("../node_modules/.bin/prism", import.meta.url)),
    [
      "mock",
      contract,
      "--host",
      HOST,
      "--port",
      String(prismPort),
      "--multiprocess",
      "false",
    ],
    { stdio: "inherit" },
  );
  prism.on("error", (cause) => fail(`could not start Prism: ${cause.message}`));
  prism.on("exit", (code) => fail(`Prism stopped with code ${code}`));
  // This also covers a crash of the proxy, so that Prism is never left running without it.
  process.on("exit", () => {
    prism.removeAllListeners("exit");
    prism.kill();
  });
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => process.exit(0));
  }
  return prism;
}

async function waitForPrism(prismPort) {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    try {
      await fetch(`http://${HOST}:${prismPort}/`, {
        signal: AbortSignal.timeout(1000),
      });
      return;
    } catch {
      await sleep(50);
    }
  }
  fail("Prism did not start");
}

// The port is taken before Prism starts, so a busy port fails at once, with nothing to clean up.
let ready;
const server = createServer(async (incoming, response) => {
  const controller = new AbortController();
  response.on("close", () => controller.abort());
  try {
    const prismPort = await ready;
    await answer(prismPort, incoming, response, controller.signal);
  } catch (cause) {
    if (controller.signal.aborted) {
      return;
    }
    if (response.headersSent) {
      response.destroy();
      return;
    }
    const status = cause.name === "TimeoutError" ? 504 : 502;
    sendJson(response, status, error("mock_error", cause.message));
  }
});
server.on("error", (cause) =>
  fail(cause.code === "EADDRINUSE" ? `port ${port} is in use` : cause.message),
);
server.listen(port, HOST, async () => {
  const prismPort = await findFreePort();
  startPrism(prismPort);
  ready = waitForPrism(prismPort).then(() => prismPort);
  await ready;
  console.log(`Mock API on http://${HOST}:${port}, from ${contract}`);
});
