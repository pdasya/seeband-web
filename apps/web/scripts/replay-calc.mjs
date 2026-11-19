// Replays slider-like requests against an API and prints how long each answer took (FS12, #56).
// It sends what the fit screen sends while a slider moves: /api/calc with the measured curves of
// a fit mode, on the desktop SeeBand's Fe2VAl0.9Si0.1 example, one request at a time, as the
// screen does, each with E_F a little further along. Run it from each network to compare:
//   node apps/web/scripts/replay-calc.mjs --base https://api.example --label home
// Options: --base (default http://localhost:8000), --requests per case (default 50), --label (a
// name for the network, printed with the results). It prints one JSON line per case: the time from
// sending to the whole answer, p50, p95 and largest, in ms, and the size of an answer.
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

const { values: options } = parseArgs({
  options: {
    base: { type: "string", default: "http://localhost:8000" },
    requests: { type: "string", default: "50" },
    label: { type: "string", default: "" },
  },
});
const BASE = options.base.replace(/\/$/, "");
const REQUESTS = Number(options.requests);
if (!Number.isInteger(REQUESTS) || REQUESTS < 1) {
  throw new Error(
    `--requests must be a whole number from 1, not ${options.requests}`,
  );
}

const EXAMPLE = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/01_Fe2VAl09Si01_",
    import.meta.url,
  ),
);
const FILES = { seebeck: "see", resistivity: "rho", hall: "hall" };
// The screen's default fit range; it sends only the points inside it.
const MIN_K = 50;
const MAX_K = 800;

// The typical light and heavy cases: one band and S, two bands and all three quantities.
const CASES = [
  { model: "spb", fitMode: "spb_s", scattering: "acPh" },
  { model: "dpb", fitMode: "dpb_s_rho_rh", scattering: "acPh" },
];

function measurement(quantity) {
  const rows = readFileSync(`${EXAMPLE}${FILES[quantity]}.txt`, "utf8")
    .trim()
    .split("\n")
    .map((line) => line.trim().split(/\s+/).map(Number))
    .filter(([t, value]) => t >= MIN_K && t <= MAX_K && value !== 0);
  return {
    temperature_k: rows.map(([t]) => t),
    values: rows.map(([, value]) => value),
  };
}

const percentile = (sorted, p) =>
  sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)];

const models = await (await fetch(`${BASE}/api/models`)).json();

for (const { model, fitMode, scattering } of CASES) {
  const mode = models.models
    .find(({ id }) => id === model)
    ?.fit_modes.find(({ id }) => id === fitMode);
  if (mode === undefined) {
    throw new Error(`The API has no fit mode ${model}/${fitMode}`);
  }
  const parameters = Object.fromEntries(
    mode.parameters.map(({ name, core_range }) => [name, core_range.default]),
  );
  const measurements = Object.fromEntries(
    mode.quantities.map((quantity) => [quantity, measurement(quantity)]),
  );
  const durations = [];
  let failures = 0;
  let bytes = 0;
  for (let step = 0; step < REQUESTS; step += 1) {
    const body = JSON.stringify({
      model,
      fit_mode: fitMode,
      scattering,
      // As a slider moves: a new value each time, so nothing can be answered from a cache.
      parameters: {
        ...parameters,
        fermi_energy: parameters.fermi_energy + step,
      },
      min_temperature_k: MIN_K,
      max_temperature_k: MAX_K,
      band_1_degeneracy: 1,
      band_2_degeneracy: 1,
      extrapolated: false,
      measurements,
    });
    const started = performance.now();
    const response = await fetch(`${BASE}/api/calc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    const text = await response.text();
    durations.push(performance.now() - started);
    bytes = text.length;
    if (!response.ok) {
      failures += 1;
    }
  }
  const sorted = durations.toSorted((a, b) => a - b);
  console.log(
    JSON.stringify({
      label: options.label,
      base: BASE,
      case: `${model}/${fitMode}/${scattering}`,
      requests: REQUESTS,
      failures,
      p50_ms: Math.round(percentile(sorted, 50)),
      p95_ms: Math.round(percentile(sorted, 95)),
      max_ms: Math.round(sorted.at(-1)),
      answer_bytes: bytes,
    }),
  );
}
