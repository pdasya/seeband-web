// Steps a parameter slider on the running fit screen and prints how long a user waits for the
// charts (FS12, #56). It opens the app with `?timing`, which turns on its User Timing entries,
// presses an arrow key on the E_F slider, waits until every chart on screen shows the new values,
// and takes the step's settle time: from the change of the values to the first frame after the
// last chart drew them (`chart:<tab>:change-to-paint`, the largest of the step). It also counts
// failed requests. A step that does not settle in --settle-timeout-ms fails the run, as dropping
// it would hide exactly the slow cases.
//   node apps/web/scripts/measure-latency.mjs --app https://seeband.example --label home
// Options:
//   --app        the app's address (default http://localhost:5173)
//   --mode       "S" or "S + ρ + R_H" of DPB, repeatable (default both)
//   --steps      settled steps per mode (default 300)
//   --think-ms   pause after a step settles, before the next key (default 300)
//   --settle-timeout-ms   (default 30000)
//   --label      a name for the network, printed with the results
// It needs Chrome, and prints one JSON line per mode. The start of each entry is when the new
// values reach the request queue, after React has rendered them, not the key press itself.
import { cpus, platform, release } from "node:os";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const { values: options } = parseArgs({
  options: {
    app: { type: "string", default: "http://localhost:5173" },
    mode: { type: "string", multiple: true },
    steps: { type: "string", default: "300" },
    "think-ms": { type: "string", default: "300" },
    "settle-timeout-ms": { type: "string", default: "30000" },
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
const APP = options.app.replace(/\/$/, "");
const STEPS = count("steps", 1);
const THINK_MS = count("think-ms", 0);
const SETTLE_TIMEOUT_MS = count("settle-timeout-ms", 1);
const FILES = { S: ["see"], "S + ρ + R_H": ["see", "rho", "hall"] };
const MODES = options.mode ?? Object.keys(FILES);
for (const mode of MODES) {
  if (!(mode in FILES)) {
    throw new Error(
      `--mode must be one of ${Object.keys(FILES).join(", ")}, not ${mode}`,
    );
  }
}

const EXAMPLE = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/01_Fe2VAl09Si01_",
    import.meta.url,
  ),
);
const QUANTITY = { see: "S", rho: "ρ", hall: "R_H" };

/** Nearest-rank percentile of sorted values. */
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

// What the page has timed so far: each chart's paint entries, and the number of failed requests.
const readEntries = () =>
  performance
    .getEntriesByType("measure")
    .filter(({ name }) => name.startsWith("seeband:"))
    .map(({ name, duration }) => ({ name, duration }));

const browser = await chromium.launch({ channel: "chrome" });
try {
  const environment = {
    chrome: browser.version(),
    headless: true,
    os: `${platform()} ${release()}`,
    cpu: cpus()[0]?.model ?? "unknown",
  };
  for (const mode of MODES) {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    await page.goto(`${APP}/fit?timing`);
    await page.getByRole("radio", { name: "DPB", exact: true }).click();
    await page.getByRole("radio", { name: mode, exact: true }).click();
    for (const kind of FILES[mode]) {
      await page
        .locator('input[type="file"]')
        .first()
        .setInputFiles(`${EXAMPLE}${kind}.txt`);
      await page
        .getByRole("combobox", { name: "Quantity for column Column 2" })
        .click();
      await page
        .getByRole("option", { name: QUANTITY[kind], exact: true })
        .click();
      await page.getByText(`01_Fe2VAl09Si01_${kind}`).first().waitFor();
    }
    // The charts on screen, each of which must show a step before it counts as settled.
    const slider = page.getByRole("slider", { name: "E_F" });
    await slider.waitFor();
    await page.waitForTimeout(3000);
    const charts = new Set(
      (await page.evaluate(readEntries))
        .map(({ name }) => /^seeband:(chart:[^:]+):draw$/.exec(name)?.[1])
        .filter(Boolean),
    );
    if (charts.size === 0) {
      throw new Error("No chart was timed: is this app built with timing?");
    }

    const settle = [];
    let failed = 0;
    let seen = (await page.evaluate(readEntries)).length;
    await slider.focus();
    for (let step = 0; step < STEPS; step += 1) {
      // Up and back, so that E_F stays near its start.
      await slider.press(step % 20 < 10 ? "ArrowRight" : "ArrowLeft");
      const fresh = await page
        .waitForFunction(
          ({ seen, charts }) => {
            const entries = performance
              .getEntriesByType("measure")
              .filter(({ name }) => name.startsWith("seeband:"))
              .slice(seen);
            const painted = new Set(
              entries
                .map(
                  ({ name }) =>
                    /^seeband:(chart:[^:]+):change-to-paint$/.exec(name)?.[1],
                )
                .filter(Boolean),
            );
            return charts.every((chart) => painted.has(chart))
              ? entries.map(({ name, duration }) => ({ name, duration }))
              : null;
          },
          { seen, charts: [...charts] },
          { timeout: SETTLE_TIMEOUT_MS, polling: 20 },
        )
        .then((handle) => handle.jsonValue())
        .catch(() => {
          throw new Error(
            `Step ${step + 1} of ${mode} did not settle in ${SETTLE_TIMEOUT_MS} ms`,
          );
        });
      seen += fresh.length;
      failed += fresh.filter(({ name }) => name.endsWith(":failed")).length;
      settle.push(
        Math.max(
          ...fresh
            .filter(({ name }) => name.endsWith(":change-to-paint"))
            .map(({ duration }) => duration),
        ),
      );
      await page.waitForTimeout(THINK_MS);
    }

    const sorted = settle.toSorted((a, b) => a - b);
    console.log(
      JSON.stringify({
        label: options.label,
        app: APP,
        mode: `DPB ${mode}`,
        charts: [...charts],
        steps: STEPS,
        failed_requests: failed,
        valid: failed === 0,
        settle_p50_ms: Math.round(percentile(sorted, 50)),
        settle_p95_ms: Math.round(percentile(sorted, 95)),
        settle_p95_ci_ms: interval(sorted, 95),
        settle_max_ms: Math.round(sorted.at(-1)),
        ...environment,
      }),
    );
    await page.close();
  }
} finally {
  await browser.close();
}
