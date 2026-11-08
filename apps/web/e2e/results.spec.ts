import { expect, test, type Page } from "@playwright/test";

import { fakeFit } from "./support/fakeFit";
import { CALC, DEMO, serveModels } from "./support/models";

const PARSED = (quantity: string) => ({
  headers: ["T", "x"],
  column_count: 2,
  row_count: 2,
  preview: [],
  mapping: [],
  measurements: {
    [quantity]: {
      temperature_k: [100, 200],
      values: [1e-5, 2e-5],
      points: 2,
      min_temperature_k: 100,
      max_temperature_k: 200,
    },
  },
  errors: [],
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
});

const RESULT = {
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 },
  status: "converged",
  iterations: 5,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};

const RMSE = {
  seebeck: { value: 111, unit: "uV/K" },
  resistivity: { value: 22, unit: "%" },
};

async function stub(page: Page) {
  await fakeFit(page);
  await serveModels(page);
  await page.route("**/api/calc", (route) =>
    route.fulfill({ json: { ...CALC, rmse: RMSE } }),
  );
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
}

/** DPB S + ρ with its data, the design's first state. */
async function openFit(page: Page) {
  await stub(page);
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  for (const filled of [0, 1]) {
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles({
        name: `f${String(filled)}.txt`,
        mimeType: "text/plain",
        buffer: Buffer.from("T x\n100 1\n"),
      });
    await expect(page.getByText(/^2 points/)).toHaveCount(filled + 1);
  }
  await expect(page.getByRole("button", { name: "Run fit" })).toBeEnabled();
}

const send = (page: Page, event: object) =>
  page.evaluate((value) => {
    window.fitTest.send(value);
  }, event);

async function finishWith(page: Page, result: object = {}) {
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await send(page, { type: "done", result: { ...RESULT, ...result } });
  await expect(page.getByRole("button", { name: "Run fit" })).toBeVisible();
}

// Inside the app, as a reload would start a new session.
const toResults = (page: Page) =>
  page.getByRole("link", { name: "Results", exact: true }).click();

const table = (page: Page) =>
  page.getByRole("table", { name: "Fit parameters" });
// By its first cell, which may also say that the value is at a bound.
const row = (page: Page, symbol: string) =>
  table(page)
    .getByRole("row")
    .filter({
      has: page.getByRole("cell", {
        name: new RegExp(
          `^${symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}( at bound)?$`,
        ),
      }),
    });
const kpi = (page: Page, label: string) =>
  page.locator("dl > div").filter({ hasText: label });

test("with no fit, it says so and leads to the fit", async ({ page }) => {
  await stub(page);
  await page.goto("/results");

  await expect(
    page.getByText("No fit yet. Run one on the model fit page."),
  ).toBeVisible();
  await expect(table(page)).toHaveCount(0);
  await page.getByRole("link", { name: "Run a fit" }).click();
  await expect(page).toHaveURL(/\/fit$/);
});

test("a fit sums up: status, KPIs and each parameter with its status", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  await toResults(page);

  await expect(
    page.locator('[data-slot="badge"]').filter({ hasText: /^Converged/ }),
  ).toHaveText("Converged in 5 iter.");
  await expect(
    page.getByText("DPB · acPh · S + ρ · range 50–800 K", { exact: true }),
  ).toBeVisible();

  await expect(kpi(page, "Model")).toContainText("DPB");
  await expect(kpi(page, "Model")).toContainText("Double parabolic band");
  await expect(kpi(page, "Scattering")).toContainText(
    "Acoustic phonons (acPh)",
  );
  await expect(kpi(page, "RMSE S")).toContainText("111 µV/K");
  await expect(kpi(page, "RMSE ρ")).toContainText("22 %");
  await expect(kpi(page, "RMSE R_H")).toHaveCount(0);
  await expect(kpi(page, "Iterations")).toContainText("5");
  await expect(kpi(page, "Iterations")).toContainText("limit 1000");

  await expect(row(page, "m₂/m₁")).toContainText("band mass ratio");
  await expect(row(page, "m₂/m₁")).toContainText("0,5");
  await expect(row(page, "m₂/m₁")).toContainText("fitted");
  await expect(row(page, "E_g")).toContainText("900 K");
  await expect(row(page, "N₁, N₂")).toContainText("1, 1");
  await expect(row(page, "N₁, N₂")).toContainText("fixed");
  await expect(row(page, "m₁")).toContainText("absolute mass");
  await expect(row(page, "m₁")).toContainText("needs R_H");

  // The design's stand-ins are gone.
  await expect(page.getByText("[N]")).toHaveCount(0);
  await expect(page.getByText(/synthetic/i)).toHaveCount(0);
});

test("known issues and bounds reached are named", async ({ page }) => {
  await openFit(page);
  await finishWith(page, {
    known_issues: ["dpb_loop_degeneracy"],
    at_bounds: ["band_gap"],
  });
  await toResults(page);

  await expect(
    page.getByText(/^Caution: With N₂\/N₁ other than 1/),
  ).toBeVisible();
  await expect(row(page, "E_g")).toContainText("at bound");
  await expect(row(page, "E_F")).not.toContainText("at bound");
});

test("a fit under way, or one that gave no values, has no summary", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await toResults(page);
  await expect(page.getByText(/^A fit is running/)).toBeVisible();

  await send(page, {
    type: "done",
    result: { ...RESULT, status: "failed", message: "x" },
  });
  await expect(page.getByText(/^The last fit gave no values/)).toBeVisible();
  await expect(table(page)).toHaveCount(0);
});

test("demo data say so on the results", async ({ page }) => {
  await stub(page);
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
  await page.goto("/fit?demo=1");
  await expect(page.getByRole("button", { name: "Details" })).toBeVisible();
  await finishWith(page);
  await toResults(page);

  await expect(page.getByText(/^Demo data · DPB/)).toBeVisible();
  await expect(page.getByText(/^Synthetic data, generated with/)).toBeVisible();
});

test("an RMSE that is on its way or failed says so, not that data are missing", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  // Every request waits, as the fit screen may still have one on its way.
  const pending: ((ok: boolean) => void)[] = [];
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", async (route) => {
    const ok = await new Promise<boolean>((resolve) => {
      pending.push(resolve);
    });
    await (ok
      ? route.fulfill({ json: { ...CALC, rmse: RMSE } })
      : route.fulfill({ status: 500, json: { code: "internal_error" } }));
  });
  await toResults(page);

  await expect(kpi(page, "RMSE S")).toContainText("calculating…");
  await expect(kpi(page, "RMSE S")).not.toContainText("needs measurements");
  await expect.poll(() => pending.length).toBeGreaterThan(0);
  for (const answer of pending) {
    answer(false);
  }

  await expect(kpi(page, "RMSE S")).toContainText("could not be calculated");
  await expect(
    page.getByText("The RMSE could not be calculated for the current values."),
  ).toBeVisible();
});
