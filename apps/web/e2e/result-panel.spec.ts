import { expect, test, type Page } from "@playwright/test";

import { fakeFit } from "./support/fakeFit";
import { CALC, serveModels } from "./support/models";

const PARSED = (quantity: string) => ({
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

/** DPB S + ρ with its data, the design's first state. */
async function open(page: Page, calc: object = { ...CALC, rmse: RMSE }) {
  await fakeFit(page);
  await serveModels(page);
  await page.route("**/api/calc", (route) => route.fulfill({ json: calc }));
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
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

async function startFit(page: Page) {
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();
}

async function finishWith(page: Page, result: object) {
  await startFit(page);
  await send(page, { type: "done", result: { ...RESULT, ...result } });
  await expect(page.getByRole("button", { name: "Run fit" })).toBeVisible();
}

const table = (page: Page) =>
  page.getByRole("table", { name: "Parameters in use" });
const row = (page: Page, symbol: string) =>
  table(page)
    .getByRole("row")
    .filter({
      has: page.getByRole("cell", {
        name: new RegExp(`^${symbol}(?: at bound)?$`),
      }),
    });
const metric = (page: Page, label: string) =>
  page.locator("dl > div").filter({ hasText: label });
const iterations = (page: Page) => metric(page, "Iterations");
const choose = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true }).click();

test("the metrics, and the table with values and bounds, as the design has them", async ({
  page,
}) => {
  await open(page);

  await expect(
    page.getByText("DPB · acPh · range 50–800 K", { exact: true }),
  ).toBeVisible();
  await expect(metric(page, "RMSE, S")).toContainText("111 µV/K");
  await expect(metric(page, "RMSE, ρ")).toContainText("22 %");
  await expect(iterations(page)).toContainText("—");
  await expect(iterations(page)).toContainText("limit 1000");

  await expect(row(page, "E_g")).toContainText("1000 K");
  await expect(row(page, "E_g")).toContainText("-3000 … 3000");
  await expect(row(page, "m₂/m₁")).toContainText("1,01");
  await expect(row(page, "m₂/m₁")).toContainText("-3 … 3");
  // Only what this scattering uses.
  await expect(row(page, "A")).toHaveCount(1);
  await expect(row(page, "F")).toHaveCount(0);
});

test("a single-pass mode has no iterations, also after a fit", async ({
  page,
}) => {
  await open(page);

  await choose(page, "S");
  await expect(
    page.getByText("DPB · range 50–800 K", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Iterations")).toHaveCount(0);
  await expect(page.getByText(/limit \d/)).toHaveCount(0);

  await finishWith(page, { iterations: null });
  await expect(page.getByText("Iterations")).toHaveCount(0);
});

test("a parameter a fit does not change says so instead of bounds", async ({
  page,
}) => {
  await open(page);

  await choose(page, "SPB");
  await choose(page, "S");

  await expect(row(page, "m")).toContainText("1,01 mₑ");
  await expect(row(page, "m")).toContainText("not fitted");
});

test("the table and counter follow a fit", async ({ page }) => {
  await open(page);
  await startFit(page);

  await send(page, {
    type: "iteration",
    iteration: 3,
    parameters: { band_gap: 850.123456 },
  });
  await expect(iterations(page)).toContainText("3");
  await expect(row(page, "E_g")).toContainText("850,123 K");

  await send(page, { type: "done", result: RESULT });
  await expect(iterations(page)).toContainText("5");
  await expect(row(page, "E_g")).toContainText("900 K");
  await expect(row(page, "m₂/m₁")).toContainText("0,5");
  await expect(page.getByText(/not a converged result/)).toHaveCount(0);
});

test("a value at a bound is marked, and only that one", async ({ page }) => {
  await open(page);

  await finishWith(page, { at_bounds: ["band_gap"] });

  await expect(row(page, "E_g").getByText("at bound")).toBeVisible();
  await expect(table(page).getByText("at bound")).toHaveCount(1);
  await expect(page.getByText(/may have been set by that bound/)).toBeVisible();
});

test("an edit ends what was said about the fit", async ({ page }) => {
  await open(page);
  await finishWith(page, {
    at_bounds: ["band_gap"],
    known_issues: ["acphdis_early_stop"],
    iterations: 5,
  });
  await expect(page.getByText(/stops when C and D alone settle/)).toBeVisible();

  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");

  await expect(table(page).getByText("at bound")).toHaveCount(0);
  await expect(page.getByText(/may have been set/)).toHaveCount(0);
  await expect(page.getByText(/stops when C and D alone settle/)).toHaveCount(
    0,
  );
  await expect(iterations(page)).toContainText("—");
});

test("a fit at its iteration limit says it did not converge", async ({
  page,
}) => {
  await open(page);

  await finishWith(page, { status: "iteration_limit", iterations: 1000 });

  await expect(
    page.getByText(
      "The fit reached its limit of 1000 iterations before it converged, so these values are not a converged result.",
    ),
  ).toBeVisible();
  await expect(iterations(page)).toContainText("1000");
});

test("a stopped fit says what its values are", async ({ page }) => {
  await open(page);
  await startFit(page);
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText(/the values it started from/)).toBeVisible();

  await startFit(page);
  await send(page, {
    type: "iteration",
    iteration: 2,
    parameters: { band_gap: 850 },
  });
  await expect(iterations(page)).toContainText("2");
  await page.getByRole("button", { name: "Stop" }).click();

  await expect(page.getByText(/these are its last values/)).toBeVisible();
  await expect(iterations(page)).toContainText("2");
});

test("a failed fit marks no bounds, and says the values are not fitted", async ({
  page,
}) => {
  await open(page);

  await finishWith(page, {
    status: "failed",
    message: "solver_failed",
    iterations: null,
    at_bounds: ["band_gap"],
  });

  await expect(
    page.getByText("The fit failed, so these are not fitted values."),
  ).toBeVisible();
  await expect(table(page).getByText("at bound")).toHaveCount(0);
});

test("a refused fit also says the values are not fitted", async ({ page }) => {
  await open(page);
  await page.evaluate(() => {
    window.fitTest.refuse = {
      status: 422,
      body: { code: "calculation_failed", message: "x", details: [] },
    };
  });

  await page.getByRole("button", { name: "Run fit" }).click();

  await expect(page.getByText(/these are not fitted values/)).toBeVisible();
});

test("an error of one quantity marks that RMSE, with its text beside it", async ({
  page,
}) => {
  await open(page, {
    ...CALC,
    rmse: RMSE,
    known_issues: ["acphdis_band_weight"],
  });

  await expect(metric(page, "RMSE, S").getByText("unreliable")).toBeVisible();
  await expect(metric(page, "RMSE, ρ").getByText("unreliable")).toHaveCount(0);
  const text = page.getByText(
    "Unreliable: With acPhDis, the band weight of the last temperature applies to all of S.",
  );
  await expect(text).toBeVisible();

  const note = await text.boundingBox();
  const cards = await metric(page, "RMSE, S").boundingBox();
  const parameters = await table(page).boundingBox();
  expect(note?.y).toBeGreaterThan(cards?.y ?? Infinity);
  expect(note?.y).toBeLessThan(parameters?.y ?? 0);
});

test("an error with every measured curve marks each RMSE", async ({ page }) => {
  await open(page, {
    ...CALC,
    rmse: RMSE,
    known_issues: ["negative_m_eff_weight"],
  });

  await expect(metric(page, "RMSE, S").getByText("caution")).toBeVisible();
  await expect(metric(page, "RMSE, ρ").getByText("caution")).toBeVisible();
  await expect(page.getByText(/^Caution: With m₂\/m₁ below 0/)).toBeVisible();
});

test("an error of the fit alone goes under the fitted values, once", async ({
  page,
}) => {
  await open(page, {
    ...CALC,
    rmse: RMSE,
    known_issues: ["acphdis_early_stop"],
  });
  await finishWith(page, { known_issues: ["acphdis_early_stop"] });

  const text = page.getByText(/stops when C and D alone settle/);
  await expect(text).toHaveCount(1);
  await expect(page.locator("dl").getByText("unreliable")).toHaveCount(0);

  const note = await text.boundingBox();
  const parameters = await table(page).boundingBox();
  expect(note?.y).toBeGreaterThan(parameters?.y ?? Infinity);
});

test("an unknown error is shown without its id", async ({ page }) => {
  await open(page, {
    ...CALC,
    rmse: RMSE,
    known_issues: ["some_new_issue"],
  });

  await expect(
    page.getByText("Unreliable: A known error applies to this result."),
  ).toBeVisible();
  await expect(page.getByText(/some_new_issue/)).toHaveCount(0);
});

test("More graphs opens μ with the chart in view, and Results is a link", async ({
  page,
}) => {
  await open(page);
  const more = page.getByRole("button", { name: "More graphs" });
  await more.scrollIntoViewIfNeeded();

  await more.click();

  const tab = page.getByRole("tab", { name: "μ(T)" });
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(tab).toBeInViewport();

  await page.getByRole("link", { name: "Open results" }).click();
  await expect(page).toHaveURL(/\/results$/);
});
