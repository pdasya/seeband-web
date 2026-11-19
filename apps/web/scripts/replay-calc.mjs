// Replays what the fit screen sends while a slider moves, against an API, and prints how long the
// answers took (FS12, #56). Each step sends, at the same time as the screen does with its default
// charts, `/api/calc` for the measured curves and `/api/band-diagram`, for DPB S and DPB S + ρ + R_H
// on the desktop SeeBand's Fe2VAl0.9Si0.1 example, with E_F a step along. The bodies are built as
// the screen builds them: core default values from `/api/models`, the points in the default fit
// range, and S points of 0 kept. A step's time is its slower answer. It is the network and server
// baseline only: Node's fetch is not a browser, and measure-latency.mjs times the screen itself.
//   node apps/web/scripts/replay-calc.mjs --base https://seeband.example --label home
// Options:
//   --base        the API's address (default http://localhost:8000)
//   --steps       timed steps per mode (default 300)
//   --warmup      steps first, not timed (default 5)
//   --pause-ms    between steps (default 250, the screen's debounce, which also keeps two
//                 requests per step under the API's 600 per minute)
//   --timeout-ms  for one request (default 60000, the screen's own limit)
//   --label       a name for the network, printed with the results
// It prints one JSON line per mode. Only answers with status 2xx enter the percentiles; a run
// with any failure is marked invalid, with the failures counted by status. The first request of
// a new connection is reported apart, as `cold_ms`, and a probe of `/api/health` gives the
// network's round trip.
import { readFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

const { values: options } = parseArgs({
  options: {
    base: { type: "string", default: "http://localhost:8000" },
    steps: { type: "string", default: "300" },
    warmup: { type: "string", default: "5" },
    "pause-ms": { type: "string", default: "250" },
    "timeout-ms": { type: "string", default: "60000" },
    label: { type: "string", default: "" },
  },
});

function count(name, min) {
  const value = Number(options[name]);
  if (!Number.isInteger(value) || value < min) {
    throw new Error(
      `--${name} must be a whole number from ${min}, not ${options[name]}`,
    );
  }
  return value;
}
const BASE = options.base.replace(/\/$/, "");
const STEPS = count("steps", 1);
const WARMUP = count("warmup", 0);
const PAUSE_MS = count("pause-ms", 0);
const TIMEOUT_MS = count("timeout-ms", 1);

const EXAMPLE = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/01_Fe2VAl09Si01_",
    import.meta.url,
  ),
);
const FILES = { seebeck: "see", resistivity: "rho", hall: "hall" };
// The screen's default fit range, and its default model and scattering.
const MIN_K = 50;
const MAX_K = 800;
const MODEL = "dpb";
const SCATTERING = "acPh";
const MODES = ["dpb_s", "dpb_s_rho_rh"];

/** The points the screen sends: in the fit range, and for ρ and R_H not 0, as the API asks. */
function measurement(quantity) {
  const rows = readFileSync(`${EXAMPLE}${FILES[quantity]}.txt`, "utf8")
    .trim()
    .split("\n")
    .map((line) => line.trim().split(/\s+/).map(Number))
    .filter(
      ([t, value]) =>
        Number.isFinite(t) &&
        Number.isFinite(value) &&
        t >= MIN_K &&
        t <= MAX_K &&
        (quantity === "seebeck" || value !== 0),
    );
  return {
    temperature_k: rows.map(([t]) => t),
    values: rows.map(([, value]) => value),
  };
}

const percentile = (sorted, p) =>
  sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)];

/** The p-th percentile's 95 % confidence interval, from order statistics. */
function interval(sorted, p) {
  const n = sorted.length;
  const q = p / 100;
  const half = 1.96 * Math.sqrt(n * q * (1 - q));
  const low = Math.max(0, Math.floor(n * q - half) - 1);
  const high = Math.min(n - 1, Math.ceil(n * q + half) - 1);
  return [Math.round(sorted[low]), Math.round(sorted[high])];
}

/** One request: its time to the whole answer, its status, and the answer's size on the wire. */
async function timed(path, body) {
  const started = performance.now();
  try {
    const response = await fetch(`${BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const answer = new Uint8Array(await response.arrayBuffer());
    return {
      ms: performance.now() - started,
      status: response.status,
      bytes: Number(
        response.headers.get("content-length") ?? answer.byteLength,
      ),
      encoding: response.headers.get("content-encoding") ?? "identity",
    };
  } catch (error) {
    return { ms: performance.now() - started, status: error.name, bytes: 0 };
  }
}

// The first request opens the connection; it is the cold case, kept apart.
const cold = await timed("/api/health");
const probe = [];
for (let step = 0; step < 20; step += 1) {
  probe.push((await timed("/api/health")).ms);
}
const modelsAnswer = await fetch(`${BASE}/api/models`, {
  signal: AbortSignal.timeout(TIMEOUT_MS),
});
if (!modelsAnswer.ok) {
  throw new Error(`GET /api/models answered ${modelsAnswer.status}`);
}
const models = await modelsAnswer.json();

for (const fitMode of MODES) {
  const mode = models.models
    .find(({ id }) => id === MODEL)
    ?.fit_modes.find(({ id }) => id === fitMode);
  if (mode === undefined) {
    throw new Error(`The API has no fit mode ${MODEL}/${fitMode}`);
  }
  const parameters = Object.fromEntries(
    mode.parameters.map(({ name, core_range }) => [name, core_range.default]),
  );
  const fermi = mode.parameters.find(
    ({ name }) => name === "fermi_energy",
  ).core_range;
  const measurements = Object.fromEntries(
    mode.quantities.map((quantity) => [quantity, measurement(quantity)]),
  );
  const steps = [];
  const failures = {};
  let calcBytes = 0;
  let encoding = "identity";
  for (let step = 0; step < WARMUP + STEPS; step += 1) {
    // Up and back by 1 K, as arrow keys move E_F, within its bounds.
    const offset = step % 20 < 10 ? step % 10 : 10 - (step % 10);
    const values = {
      ...parameters,
      fermi_energy: Math.min(
        fermi.maximum,
        Math.max(fermi.minimum, fermi.default + offset),
      ),
    };
    const shared = {
      model: MODEL,
      fit_mode: fitMode,
      parameters: values,
      band_1_degeneracy: 1,
      band_2_degeneracy: 1,
    };
    const [calc, diagram] = await Promise.all([
      timed(
        "/api/calc",
        JSON.stringify({
          ...shared,
          scattering: SCATTERING,
          min_temperature_k: MIN_K,
          max_temperature_k: MAX_K,
          extrapolated: false,
          measurements,
        }),
      ),
      timed("/api/band-diagram", JSON.stringify(shared)),
    ]);
    if (step >= WARMUP) {
      const answers = [calc, diagram];
      const bad = answers.filter(
        ({ status }) => !(status >= 200 && status < 300),
      );
      for (const { status } of bad) {
        failures[status] = (failures[status] ?? 0) + 1;
      }
      if (bad.length === 0) {
        steps.push(Math.max(calc.ms, diagram.ms));
        calcBytes = calc.bytes;
        encoding = calc.encoding;
      }
    }
    await sleep(PAUSE_MS);
  }
  const sorted = steps.toSorted((a, b) => a - b);
  const failed = Object.values(failures).reduce((sum, n) => sum + n, 0);
  console.log(
    JSON.stringify({
      label: options.label,
      base: BASE,
      mode: `${MODEL}/${fitMode}/${SCATTERING}`,
      steps: STEPS,
      answered_steps: sorted.length,
      failures,
      valid: failed === 0,
      step_p50_ms: sorted.length ? Math.round(percentile(sorted, 50)) : null,
      step_p95_ms: sorted.length ? Math.round(percentile(sorted, 95)) : null,
      step_p95_ci_ms: sorted.length ? interval(sorted, 95) : null,
      step_max_ms: sorted.length ? Math.round(sorted.at(-1)) : null,
      calc_answer_bytes: calcBytes,
      calc_answer_encoding: encoding,
      cold_ms: Math.round(cold.ms),
      health_rtt_p50_ms: Math.round(
        percentile(
          probe.toSorted((a, b) => a - b),
          50,
        ),
      ),
      node: process.version,
    }),
  );
}
