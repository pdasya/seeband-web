// Takes the site's worked-example screenshots from the running app, on the three example sets of
// the desktop SeeBand, and prints every number the example pages quote: for each fit its start,
// status, RMSEs and parameter table, and for the Si:P fits the full-precision parameter file. It
// needs the API on port 8000, the app on port 5173 (`pnpm --filter @seeband/web dev:api`) and
// Chrome:
//   node apps/web/scripts/capture-examples.mjs
// The images go to apps/site/public/examples. The pages' numbers are copied from its output by
// hand, so run it again, and check the pages, when the screens or the core change.
import { readFileSync } from "node:fs";
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

/** Chooses a scattering mechanism and, if `guess`, the neural net's start, which must exist. */
async function scattering(page, name, guess) {
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: new RegExp(`^${name}`) }).click();
  await page.waitForTimeout(800);
  if (guess) {
    const button = page.getByRole("button", { name: "Initial guess" });
    if (!(await button.isEnabled())) {
      throw new Error(`No neural-net start for ${name}`);
    }
    await button.click();
    await page.waitForTimeout(1500);
  }
}

/** The parameter fields' values, as the fit will start from them. */
async function starts(page) {
  const card = page
    .getByRole("heading", { name: "Parameters", exact: true })
    .locator("xpath=ancestor::section[1]");
  // The fields' accessible names and values, from the card's accessibility tree.
  const values = (await card.ariaSnapshot())
    .split("\n")
    .filter((line) => line.includes("textbox"))
    .map((line) => line.replace(/^\s*- textbox /, "").replace(/\s+/g, " "));
  return values.join(" ; ");
}

/**
 * Runs a fit, waits for its end, and prints its start and what the screen says of it. A fit too
 * fast to show Stop is still waited for: its request must have been answered first.
 */
async function runFit(page, label) {
  console.log(`== ${label}`);
  console.log(`start: ${await starts(page)}`);
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/fit") && r.request().method() === "POST",
    { timeout: 300_000 },
  );
  await page.getByRole("button", { name: "Run fit" }).click();
  await response;
  const stop = page.getByRole("button", { name: "Stop" });
  await stop.waitFor({ state: "visible", timeout: 5000 }).catch(() => {});
  await stop.waitFor({ state: "detached", timeout: 300_000 });
  await page.waitForTimeout(1500);
  const badges = await page.locator('[data-slot="badge"]').allInnerTexts();
  const rmse = await page.getByText(/^RMSE \d/).allInnerTexts();
  const notes = await page.getByText(/^(Unreliable|Caution):/).allInnerTexts();
  const rows = await page
    .locator("table")
    .first()
    .locator("tbody tr")
    .allInnerTexts();
  console.log(`status: ${badges.join(", ")} | ${rmse.join(" ")}`);
  console.log(rows.map((row) => row.replace(/\s+/g, " ")).join(" ; "));
  for (const note of notes) console.log(`note: ${note.replace(/\s+/g, " ")}`);
}

/** Prints the parameter file of the last fit, at full precision. */
async function parameterFile(page) {
  const name = "Parameters to file";
  await page.getByRole("button", { name }).click();
  await page.getByRole("radio", { name: /^Text/ }).click();
  const download = page.waitForEvent("download");
  await page
    .getByRole("dialog", { name, exact: true })
    .getByRole("button", { name: "Download", exact: true })
    .click();
  const text = readFileSync(await (await download).path(), "utf8");
  console.log(text.trim().replace(/^/gm, "  "));
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

/** Si:P with E_g allowed up to 1.5 eV, from the paper's gap and the given E_F start. */
async function widen(page, fermiEnergy) {
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
    ["E_F", fermiEnergy],
  ]) {
    const field = page
      .getByRole("textbox", { name: new RegExp(`^${symbol}`) })
      .first();
    await field.click();
    await field.fill(value);
    await field.press("Enter");
  }
  await page.waitForTimeout(1500);
}

const browser = await chromium.launch({ channel: "chrome" });
const viewport = { width: 1440, height: 1000 };
/** A new page, so that nothing carries over from an earlier fit. */
const fresh = async () => {
  const page = await browser.newPage({ viewport, acceptDownloads: true });
  await page.goto(`${APP}/fit`);
  await page.getByRole("radio", { name: "DPB", exact: true }).click();
  return page;
};

try {
  // Fe2VAl0.9Si0.1: two bands, S and ρ, with each mechanism in turn. The net has no start for
  // ionized impurities, so that fit starts from the values the app holds then; the script prints
  // them.
  {
    const page = await fresh();
    await load(page, "01_Fe2VAl09Si01", ["see", "rho"]);
    for (const [name, guess] of [
      ["Alloy disorder", true],
      ["Ionized impurities", false],
      ["Acoustic phonons", true],
    ]) {
      await scattering(page, name, guess);
      await runFit(page, `Fe2VAl S + ρ, ${name}`);
    }
    await upTo(
      page,
      page.getByRole("region", { name: "Chart 2" }),
      "fe2val.png",
    );
    await page.close();
  }

  // Si:P with the default bounds and start. No net covers its range.
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

  // Si:P with E_g allowed up to 1.5 eV. E_F is typed as 1.0805 eV, 6 K into the conduction band
  // (the field shows 1,08); the runs after these show what other starts do.
  for (const kinds of [
    ["see", "rho"],
    ["see", "rho", "hall"],
  ]) {
    const page = await fresh();
    await load(page, "02_SiP", kinds);
    await widen(page, "1,0805");
    await runFit(page, `Si:P ${MODE[kinds.at(-1)]}, gap up to 1.5 eV`);
    if (kinds.length === 3) {
      await upTo(
        page,
        page.getByRole("region", { name: "Chart 3" }),
        "sip-hall.png",
      );
    }
    // After the screenshot: the export dialog scrolls the page.
    await parameterFile(page);
    await page.close();
  }
  for (const [fermiEnergy, method] of [
    ["1,08", "Verified sequential"],
    ["1,09", "Verified sequential"],
    ["1,08", "Legacy sequential (reproduce earlier results)"],
  ]) {
    const page = await fresh();
    await load(page, "02_SiP", ["see", "rho", "hall"]);
    await widen(page, fermiEnergy);
    await page
      .getByRole("combobox", { name: "Fitting method" })
      .selectOption({ label: method });
    await runFit(
      page,
      `Si:P S + ρ + R_H, gap up to 1.5 eV, E_F from ${fermiEnergy} eV, ${method}`,
    );
    await page.close();
  }

  // AWI32: two bands, S, ρ and R_H, with each mechanism in turn.
  {
    const page = await fresh();
    await load(page, "03_AWI32_SI", ["see", "rho", "hall"]);
    for (const [name, guess] of [
      ["Acoustic phonons", true],
      ["Ionized impurities", false],
      ["Alloy disorder", true],
    ]) {
      await scattering(page, name, guess);
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
