// Takes the site's example walkthrough screenshots from the running app, on the three example sets
// of the desktop SeeBand, and prints the numbers the walkthroughs quote. It needs the API on port
// 8000, the app on port 5173 (`pnpm --filter @seeband/web dev:api`) and Chrome:
//   node apps/web/scripts/capture-examples.mjs
// The images go to apps/site/public/examples.
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const APP = process.env.SEEBAND_APP ?? "http://localhost:5173";
const EXAMPLES = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/",
    import.meta.url,
  ),
);
const OUT = fileURLToPath(
  new URL("../../site/public/examples/", import.meta.url),
);
const QUANTITY = { see: "S", rho: "ρ", hall: "R_H" };
const MODE = { see: "S", rho: "S + ρ", hall: "S + ρ + R_H" };

async function load(page, example, kinds) {
  await page
    .getByRole("radio", { name: MODE[kinds.at(-1)], exact: true })
    .click();
  for (const kind of kinds) {
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles(`${EXAMPLES}${example}_${kind}.txt`);
    await page
      .getByRole("combobox", { name: "Quantity for column Column 2" })
      .click();
    await page
      .getByRole("option", { name: QUANTITY[kind], exact: true })
      .click();
    await page.getByText(`${example}_${kind}`).first().waitFor();
  }
  await page.waitForTimeout(1500);
}

async function scattering(page, name) {
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: new RegExp(`^${name}`) }).click();
  await page.waitForTimeout(800);
  const guess = page.getByRole("button", { name: "Initial guess" });
  if (name !== "Ionized impurities" && (await guess.isEnabled())) {
    await guess.click();
    await page.waitForTimeout(1500);
  }
}

/** Runs a fit, waits for its end, and prints what the screen says of it. */
async function runFit(page, label) {
  await page.getByRole("button", { name: "Run fit" }).click();
  const stop = page.getByRole("button", { name: "Stop" });
  await stop.waitFor({ state: "visible" });
  await stop.waitFor({ state: "detached", timeout: 300_000 });
  await page.getByRole("heading", { name: "Result", exact: true }).waitFor();
  await page.waitForTimeout(1500);
  const badges = await page.locator('[data-slot="badge"]').allInnerTexts();
  const rmse = await page.getByText(/^RMSE \d/).allInnerTexts();
  const rows = await page
    .locator("table")
    .first()
    .locator("tbody tr")
    .allInnerTexts();
  console.log(`== ${label}: ${badges.join(", ")} | ${rmse.join(" ")}`);
  console.log(rows.map((row) => row.replace(/\s+/g, " ")).join(" ; "));
}

/** A screenshot of the page from its top down to the bottom of `below`. */
async function upTo(page, below, path) {
  const box = await below.boundingBox();
  await page.screenshot({
    path: OUT + path,
    fullPage: true,
    clip: {
      x: 0,
      y: 0,
      width: page.viewportSize().width,
      height: Math.ceil(box.y + box.height + 24),
    },
  });
}

const browser = await chromium.launch({ channel: "chrome" });
const viewport = { width: 1440, height: 1000 };
const fresh = async () => {
  const page = await browser.newPage({ viewport });
  await page.goto(`${APP}/fit`);
  await page.getByRole("radio", { name: "DPB", exact: true }).click();
  return page;
};

try {
  // Fe2VAl0.9Si0.1: two bands, S and ρ, with each mechanism.
  {
    const page = await fresh();
    await load(page, "01_Fe2VAl09Si01", ["see", "rho"]);
    for (const name of [
      "Alloy disorder",
      "Ionized impurities",
      "Acoustic phonons",
    ]) {
      await scattering(page, name);
      await runFit(page, `Fe2VAl S + ρ, ${name}`);
    }
    await upTo(
      page,
      page.getByRole("region", { name: "Chart 2" }),
      "fe2val.png",
    );
    await page.close();
  }

  // Si:P: with the default bounds, then with the gap allowed up to 1.5 eV.
  {
    const page = await fresh();
    await load(page, "02_SiP", ["see", "rho"]);
    await runFit(page, "Si:P S + ρ, default bounds");
    await upTo(
      page,
      page.getByRole("region", { name: "Chart 2" }),
      "sip-default.png",
    );
    await page.close();
  }
  // A new page for each, so that the fit starts from the default A and B, not the last fit's.
  // E_F is typed as 1.0805 eV, 6 K into the conduction band: the field shows 1,08, and a start
  // exactly at the band edge fails derivative validation.
  for (const [kinds, label, file] of [
    [["see", "rho"], "Si:P S + ρ, gap up to 1.5 eV", "sip-wide.png"],
    [
      ["see", "rho", "hall"],
      "Si:P S + ρ + R_H, gap up to 1.5 eV",
      "sip-hall.png",
    ],
  ]) {
    const page = await fresh();
    await load(page, "02_SiP", kinds);
    await page.getByRole("button", { name: "Edit bounds" }).click();
    const dialog = page.getByRole("dialog");
    for (const [symbol, lower, upper] of [
      ["E_g", "0,5", "1,5"],
      ["E_F", "-1,5", "1,6"],
    ]) {
      await dialog
        .getByRole("textbox", { name: `${symbol}, lower bound`, exact: true })
        .fill(lower);
      await dialog
        .getByRole("textbox", { name: `${symbol}, upper bound`, exact: true })
        .fill(upper);
    }
    await dialog.getByRole("button", { name: "Done" }).click();
    await dialog.waitFor({ state: "hidden" });
    for (const [symbol, value] of [
      ["m₂/m₁", "0,74"],
      ["E_g", "1,08"],
      ["E_F", "1,0805"],
    ]) {
      const field = page
        .getByRole("textbox", { name: new RegExp(`^${symbol}`) })
        .first();
      await field.click();
      await field.fill(value);
      await field.press("Enter");
    }
    await page.waitForTimeout(1500);
    await runFit(page, label);
    await upTo(
      page,
      page.getByRole("region", {
        name: kinds.length === 3 ? "Chart 3" : "Chart 2",
      }),
      file,
    );
    await page.close();
  }

  // AWI32: two bands, S, ρ and R_H, with each mechanism.
  {
    const page = await fresh();
    await load(page, "03_AWI32_SI", ["see", "rho", "hall"]);
    for (const name of [
      "Acoustic phonons",
      "Ionized impurities",
      "Alloy disorder",
    ]) {
      await scattering(page, name);
      await runFit(page, `AWI32 S + ρ + R_H, ${name}`);
    }
    await upTo(
      page,
      page.getByRole("region", { name: "Chart 3" }),
      "awi32.png",
    );
    await page.close();
  }
} finally {
  await browser.close();
}
