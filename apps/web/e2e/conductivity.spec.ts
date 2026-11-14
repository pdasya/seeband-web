import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

interface ParseBody {
  text: string;
  expected?: string;
  mapping?: { column: number; role: string; unit?: string }[];
}

// ρ = 1/σ of σ = 4e4 and 5e4 S/m, as the server gives it.
const RESISTIVITY = {
  temperature_k: [100, 200],
  values: [2.5e-5, 2e-5],
  points: 2,
  min_temperature_k: 100,
  max_temperature_k: 200,
  loaded_as: "conductivity",
};

function parsedSigma(unit: string, overrides: object = {}) {
  return {
    headers: ["T", "sigma"],
    column_count: 2,
    row_count: 2,
    preview: [
      [100, 4e4],
      [200, 5e4],
    ],
    preview_si: [
      [100, 4e4],
      [200, 5e4],
    ],
    mapping: [
      { column: 0, role: "temperature", unit: "K" },
      { column: 1, role: "conductivity", unit },
    ],
    measurements: { resistivity: RESISTIVITY },
    errors: [],
    warnings: [],
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    interpolation_failure_reasons: {},
    ...overrides,
  };
}

async function serveParse(page: Page, ...answers: object[]) {
  const bodies: ParseBody[] = [];
  await page.route("**/api/parse", (route: Route) => {
    bodies.push(route.request().postDataJSON() as ParseBody);
    const answer = answers[Math.min(bodies.length, answers.length) - 1];
    return route.fulfill({ status: 200, json: answer });
  });
  return bodies;
}

async function loadRhoSlot(page: Page, name = "sigma.txt") {
  await page
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from("T sigma\n100 4e4\n200 5e4\n"),
    });
}

const rhoSlot = (page: Page) => page.locator('[data-file-slot="resistivity"]');

test.beforeEach(async ({ page }) => {
  await serveModels(page);
});

test("the ρ slot reads a file as σ once σ is chosen, and the card says ρ = 1/σ", async ({
  page,
}) => {
  const bodies = await serveParse(page, parsedSigma("S/m"));
  await page.goto("/fit");

  const choice = page.getByRole("radiogroup", {
    name: "Load ρ, or σ in its place",
  });
  await expect(
    choice.getByRole("radio", { name: "Resistivity" }),
  ).toBeChecked();
  await choice.getByRole("radio", { name: "Conductivity" }).click();
  await loadRhoSlot(page);

  await expect(
    rhoSlot(page).getByText("2 points · 100–200 K · S/m · read as ρ = 1/σ"),
  ).toBeVisible();
  expect(bodies[0]?.expected).toBe("conductivity");
  await expect(
    page.getByRole("combobox", { name: "Unit of Conductivity" }),
  ).toHaveText("S/m");
  // The bar of a closed panel names σ, which the slot holds.
  await page.getByRole("button", { name: "Hide" }).click();
  await expect(page.getByText("σ · 2 pts")).toBeVisible();
});

test("choosing S/cm reads the σ column again in it", async ({ page }) => {
  const bodies = await serveParse(
    page,
    parsedSigma("S/m"),
    parsedSigma("S/cm"),
  );
  await page.goto("/fit");
  await page
    .getByRole("radiogroup", { name: "Load ρ, or σ in its place" })
    .getByRole("radio", { name: "Conductivity" })
    .click();
  await loadRhoSlot(page);

  await page.getByRole("combobox", { name: "Unit of Conductivity" }).click();
  await page.getByRole("option", { name: "S/cm", exact: true }).click();

  await expect(
    page.getByRole("combobox", { name: "Unit of Conductivity" }),
  ).toHaveText("S/cm");
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "K" },
    { column: 1, role: "conductivity", unit: "S/cm" },
  ]);
});

test("a σ of 0 is refused with its line, and loads nothing", async ({
  page,
}) => {
  await serveParse(
    page,
    parsedSigma("S/m", {
      measurements: {},
      errors: [{ code: "non_positive_conductivity", line: 3, column: 1 }],
    }),
  );
  await page.goto("/fit");
  await loadRhoSlot(page, "sigma.txt");

  await expect(
    page.getByText(
      "Line 3: A conductivity of 0 or below, which has no resistivity.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Unit of Conductivity" }),
  ).toHaveCount(0);
});

test("the charts name ρ from σ as 1/σ, and the RMSE compares with it", async ({
  page,
}) => {
  await serveParse(page, parsedSigma("S/m"));
  await page.goto("/fit");
  await loadRhoSlot(page, "sigma.txt");
  await expect(rhoSlot(page).getByText(/read as ρ = 1\/σ/)).toBeVisible();

  await expect(page.getByText("1/σ of the σ data").first()).toBeVisible();
});

test("a single table can map a column to σ, and not to both ρ and σ", async ({
  page,
}) => {
  const table = {
    headers: ["T", "a", "b"],
    column_count: 3,
    row_count: 2,
    preview: [
      [100, 2.5e-5, 4e4],
      [200, 2e-5, 5e4],
    ],
    preview_si: [
      [100, null, null],
      [200, null, null],
    ],
    mapping: [{ column: 0, role: "temperature", unit: "K" }],
    measurements: {},
    errors: [],
    warnings: [{ code: "no_quantity" }],
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    interpolation_failure_reasons: {},
  };
  const sigma = {
    ...table,
    preview_si: [
      [100, null, 4e4],
      [200, null, 5e4],
    ],
    mapping: [
      { column: 0, role: "temperature", unit: "K" },
      { column: 2, role: "conductivity", unit: "S/m" },
    ],
    measurements: { resistivity: RESISTIVITY },
    warnings: [],
  };
  const both = {
    ...table,
    mapping: [
      { column: 0, role: "temperature", unit: "K" },
      { column: 2, role: "conductivity", unit: "S/m" },
      { column: 1, role: "resistivity", unit: "Ohm*m" },
    ],
    errors: [{ code: "resistivity_and_conductivity", column: 2 }],
    warnings: [],
  };
  const bodies = await serveParse(page, table, sigma, both);
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "table.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T a b\n100 2.5e-5 4e4\n200 2e-5 5e4\n"),
  });

  await page.getByRole("combobox", { name: "Quantity for column b" }).click();
  await page.getByRole("option", { name: "σ", exact: true }).click();
  await expect(page.getByText("σ · 2 points · read as ρ = 1/σ")).toBeVisible();
  expect(bodies[1]?.mapping).toContainEqual({
    column: 2,
    role: "conductivity",
  });

  await page.getByRole("combobox", { name: "Quantity for column a" }).click();
  await page.getByRole("option", { name: "ρ", exact: true }).click();
  await expect(
    page.getByText("A file can hold ρ or σ, not both. Choose one of them."),
  ).toBeVisible();
});

test("a file with no header in the σ slot asks for its columns, naming σ", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsedSigma("S/m", { headers: undefined, measurements: {} }),
    parsedSigma("S/m"),
  );
  await page.goto("/fit");
  await page
    .getByRole("radiogroup", { name: "Load ρ, or σ in its place" })
    .getByRole("radio", { name: "Conductivity" })
    .click();
  await page
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name: "run.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("100 4e4\n200 5e4\n"),
    });

  await expect(
    page.getByText(/Choose the column that holds σ, or another quantity/),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Quantity for column Column 2" })
    .click();
  await page.getByRole("option", { name: "σ", exact: true }).click();

  await expect(rhoSlot(page).getByText(/read as ρ = 1\/σ/)).toBeVisible();
  expect(bodies[0]?.expected).toBe("conductivity");
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 1, role: "conductivity" },
  ]);
});
