// Serves the OpenAPI contract with Prism, for working on the client without the API.
//
// Prism cannot delay a response, and answers its own 404, 405 and 422 in its own format. So this
// proxy stands in front of it, to add delays and give those errors the API's format.
//
// Usage: node scripts/mock.mjs [contract file]
// Environment: MOCK_PORT, MOCK_DELAY_MS, and MOCK_PREFER, a Prefer header for requests with none.
import { spawn } from "node:child_process";
import { createServer, request } from "node:http";
import { createServer as createTcpServer } from "node:net";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const HOST = "127.0.0.1";
const PROBLEM_CODES = new Map([
  [404, "not_found"],
  [405, "method_not_allowed"],
  [422, "validation_error"],
]);

const contract =
  process.argv[2] ?? fileURLToPath(new URL("../openapi.json", import.meta.url));
const port = Number(process.env.MOCK_PORT ?? 4010);
const delayMs = Number(process.env.MOCK_DELAY_MS ?? 0);
const defaultPrefer = process.env.MOCK_PREFER;

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

function toErrorResponse(status, problem) {
  const details = problem.validation?.map((item) => ({
    location: item.location,
    code: item.code,
    message: item.message,
  }));
  return {
    code: PROBLEM_CODES.get(status) ?? "mock_error",
    message: problem.detail ?? problem.title,
    details: details ?? [],
  };
}

function sendJson(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

function sendProblemAsError(upstream, response) {
  const chunks = [];
  upstream.on("data", (chunk) => chunks.push(chunk));
  upstream.on("end", () => {
    const problem = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    sendJson(
      response,
      upstream.statusCode,
      toErrorResponse(upstream.statusCode, problem),
    );
  });
}

function forward(prismPort, incoming, response) {
  const prefer = incoming.headers.prefer ?? defaultPrefer;
  const outgoing = request(
    {
      host: HOST,
      port: prismPort,
      method: incoming.method,
      path: incoming.url,
      headers: { ...incoming.headers, ...(prefer ? { prefer } : {}) },
    },
    (upstream) => {
      if (
        upstream.headers["content-type"]?.includes("application/problem+json")
      ) {
        sendProblemAsError(upstream, response);
      } else {
        response.writeHead(upstream.statusCode, upstream.headers);
        upstream.pipe(response);
      }
    },
  );
  outgoing.on("error", (error) =>
    sendJson(response, 502, {
      code: "mock_error",
      message: error.message,
      details: [],
    }),
  );
  incoming.pipe(outgoing);
}

async function waitForPrism(prismPort, prism) {
  for (
    let attempt = 0;
    attempt < 600 && prism.exitCode === null;
    attempt += 1
  ) {
    try {
      await fetch(`http://${HOST}:${prismPort}/`);
      return;
    } catch {
      await sleep(50);
    }
  }
  throw new Error("Prism did not start");
}

const prismPort = await findFreePort();
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
prism.on("exit", (code) => process.exit(code ?? 1));
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    prism.removeAllListeners("exit");
    prism.kill(signal);
    process.exit(0);
  });
}

await waitForPrism(prismPort, prism);

createServer(async (incoming, response) => {
  await sleep(delayMs);
  forward(prismPort, incoming, response);
}).listen(port, HOST, () => {
  console.log(`Mock API on http://${HOST}:${port}, from ${contract}`);
});
