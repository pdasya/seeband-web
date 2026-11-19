// Moves a parameter slider on the running fit screen and prints how long the live curves took,
// from the browser's User Timing entries (FS12, #56): `measured:change-to-answer` from the last
// change to the answer for it, which includes the debounce; `measured:request`, from sending to
// the answer; and `chart:draw`, the drawing of a chart. Their sum is what a user waits for.
//   node apps/web/scripts/measure-latency.mjs --app https://seeband.example --label home
// Options: --app (default http://localhost:5173), --mode (S or "S + ρ + R_H", default both),
// --steps (default 30), --pause-ms between key presses (default 400, longer than the debounce,
// so that each step is answered), --label. It needs Chrome, and prints one JSON line per mode.
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const { values: options } = parseArgs({
  options: {
    app: { type: "string", default: "http://localhost:5173" },
    mode: { type: "string", multiple: true },
    steps: { type: "string", default: "30" },
    "pause-ms": { type: "string", default: "400" },
    label: { type: "string", default: "" },
  },
});
const APP = options.app.replace(/\/$/, "");
const STEPS = Number(options.steps);
const PAUSE_MS = Number(options["pause-ms"]);
const MODES = options.mode ?? ["S", "S + ρ + R_H"];

const EXAMPLE = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/01_Fe2VAl09Si01_",
    import.meta.url,
  ),
);
const FILES = { S: ["see"], "S + ρ + R_H": ["see", "rho", "hall"] };
const QUANTITY = { see: "S", rho: "ρ", hall: "R_H" };

const percentile = (sorted, p) =>
  sorted.length === 0
    ? null
    : Math.round(
        sorted[
          Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)
        ],
      );

const browser = await chromium.launch({ channel: "chrome" });
try {
  for (const mode of MODES) {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    await page.goto(`${APP}/fit`);
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
    // Loading draws first; only the slider's steps count.
    await page.waitForTimeout(3000);
    await page.evaluate(() => performance.clearMeasures());

    // The E_F slider, moved by keyboard, one step at a time.
    const slider = page.getByRole("slider").nth(2);
    await slider.focus();
    for (let step = 0; step < STEPS; step += 1) {
      await slider.press(step % 20 < 10 ? "ArrowRight" : "ArrowLeft");
      await page.waitForTimeout(PAUSE_MS);
    }
    await page.waitForTimeout(2000);

    const durations = await page.evaluate(() =>
      Object.fromEntries(
        ["measured:change-to-answer", "measured:request", "chart:draw"].map(
          (name) => [
            name,
            performance
              .getEntriesByName(`seeband:${name}`, "measure")
              .map((entry) => entry.duration)
              .sort((a, b) => a - b),
          ],
        ),
      ),
    );
    console.log(
      JSON.stringify({
        label: options.label,
        app: APP,
        mode,
        steps: STEPS,
        ...Object.fromEntries(
          Object.entries(durations).flatMap(([name, sorted]) => [
            [`${name} n`, sorted.length],
            [`${name} p50_ms`, percentile(sorted, 50)],
            [`${name} p95_ms`, percentile(sorted, 95)],
          ]),
        ),
      }),
    );
    await page.close();
  }
} finally {
  await browser.close();
}
