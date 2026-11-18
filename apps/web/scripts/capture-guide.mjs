// Takes the site's user guide screenshots from the running app, on the Fe2VAl0.9Si0.1 example of
// the desktop SeeBand. It needs the API on port 8000, the app on port 5173 (`pnpm --filter
// @seeband/web dev:api`) and Chrome:
//   node apps/web/scripts/capture-guide.mjs
// The images go to apps/site/public/guide. The numbers the guide quotes come from the same runs.
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const APP = process.env.SEEBAND_APP ?? "http://localhost:5173";
const EXAMPLES = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/",
    import.meta.url,
  ),
);
const OUT = fileURLToPath(new URL("../../site/public/guide/", import.meta.url));
const QUANTITY = { see: "S", rho: "ρ", hall: "R_H" };

async function load(page, kinds) {
  for (const kind of kinds) {
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles(`${EXAMPLES}01_Fe2VAl09Si01_${kind}.txt`);
    await page
      .getByRole("combobox", { name: "Quantity for column Column 2" })
      .click();
    await page
      .getByRole("option", { name: QUANTITY[kind], exact: true })
      .click();
    await page
      .getByText("01_Fe2VAl09Si01_" + kind)
      .first()
      .waitFor();
  }
}

/** Runs a fit and waits for its end, which the Stop button coming and going marks. */
async function runFit(page) {
  await page.getByRole("button", { name: "Run fit" }).click();
  const stop = page.getByRole("button", { name: "Stop" });
  await stop.waitFor({ state: "visible" });
  await stop.waitFor({ state: "detached", timeout: 300_000 });
  await page.getByRole("heading", { name: "Result", exact: true }).waitFor();
  await page.waitForTimeout(1500);
}

/** A screenshot of the page from its top down to the bottom of `below`. */
async function upTo(page, below, path) {
  const box = await below.boundingBox();
  await page.screenshot({
    path: OUT + path,
    clip: {
      x: 0,
      y: 0,
      width: page.viewportSize().width,
      height: Math.ceil(box.y + box.height + 24),
    },
  });
}

/** The section, a card on screen, that a heading heads. */
const card = (page, heading) =>
  page
    .getByRole("heading", { name: heading, exact: true })
    .first()
    .locator("xpath=ancestor::section[1]");

const browser = await chromium.launch({ channel: "chrome" });
const viewport = { width: 1440, height: 1000 };

try {
  // One band, S only, on 5-240 K.
  {
    const page = await browser.newPage({ viewport });
    await page.goto(`${APP}/fit`);
    await page.getByRole("radio", { name: "SPB", exact: true }).click();
    await page.getByRole("radio", { name: "S", exact: true }).click();
    await load(page, ["see"]);
    for (const [name, value] of [
      ["Lower bound, K", "5"],
      ["Upper bound, K", "240"],
    ]) {
      await page.getByRole("textbox", { name }).fill(value);
      await page.getByRole("textbox", { name }).press("Enter");
    }
    await runFit(page);
    await upTo(
      page,
      page.getByRole("region", { name: "Chart 1" }),
      "spb-seebeck-fit.png",
    );
    await page.close();
  }

  // Two bands, S + ρ + R_H, from the neural net's start.
  {
    const page = await browser.newPage({ viewport });
    await page.goto(`${APP}/fit`);
    await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();
    await load(page, ["see", "rho", "hall"]);
    await page.waitForTimeout(2000);
    await card(page, "Data").screenshot({ path: OUT + "data.png" });
    await runFit(page);
    await page.screenshot({ path: OUT + "dpb-fit.png", fullPage: true });

    await page.getByRole("link", { name: "Results", exact: true }).click();
    await page.getByRole("heading", { level: 1, name: "Results" }).waitFor();
    await page.waitForTimeout(4000);
    await upTo(page, card(page, "Fit log"), "results.png");
    await page
      .getByRole("region", { name: "Additional graphs" })
      .screenshot({ path: OUT + "additional-graphs.png" });
    await page.close();
  }
} finally {
  await browser.close();
}
