import { expect, test, type Page } from "@playwright/test";

import { serveModels } from "./support/models";

const parsedFor = (quantity: string, points = 2) => ({
  headers: ["T", "x"],
  column_count: 2,
  row_count: points,
  preview: [],
  preview_si: [],
  mapping: [],
  measurements: {
    [quantity]: {
      temperature_k: Array.from({ length: points }, (_, at) => 100 + at),
      values: Array.from({ length: points }, () => 1e-5),
      points,
      min_temperature_k: 100,
      max_temperature_k: 100 + points - 1,
    },
  },
  errors: [],
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
});

async function open(page: Page) {
  await serveModels(page);
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({
      json: parsedFor(expected, expected === "seebeck" ? 31 : 12),
    });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
}

async function load(page: Page, quantity: string, name: string) {
  await page
    .locator(`[data-file-slot="${quantity}"] input[type="file"]`)
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from("T x\n100 1\n"),
    });
}

const heading = (page: Page) => page.getByRole("heading", { name: "Data" });
const summary = (page: Page) => page.getByRole("region", { name: "Data" });
const details = (page: Page) => page.getByRole("button", { name: "Details" });

async function loadSAndRho(page: Page) {
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await load(page, "seebeck", "seebeck.txt");
  await expect(page.getByText(/^31 points/)).toBeVisible();
  await load(page, "resistivity", "rho.txt");
}

test("the data fold into one line once the fit mode has all it needs", async ({
  page,
}) => {
  await open(page);
  await loadSAndRho(page);

  await expect(heading(page)).toBeHidden();
  await expect(summary(page)).toContainText("Data loaded");
  await expect(summary(page)).toContainText("seebeck.txt · rho.txt");
  await expect(summary(page).getByRole("listitem")).toHaveText([
    "S · 31 pts",
    "ρ · 12 pts",
    "R_H · not loaded",
  ]);
  await expect(details(page)).toHaveAttribute("aria-expanded", "false");
});

test("Details opens the data with what they hold, and Hide folds them", async ({
  page,
}) => {
  await open(page);
  await loadSAndRho(page);

  await details(page).click();
  await expect(heading(page)).toBeVisible();
  await expect(page.locator("[data-file-slot]").nth(0)).toContainText(
    "seebeck.txt",
  );
  const hide = page.getByRole("button", { name: "Hide" });
  await expect(hide).toHaveAttribute("aria-expanded", "true");
  await expect(hide).toBeFocused();

  await hide.click();
  await expect(heading(page)).toBeHidden();
  await expect(details(page)).toBeVisible();
  await expect(details(page)).toBeFocused();

  // The keyboard goes the same way.
  await page.keyboard.press("Enter");
  await expect(hide).toBeFocused();
});

test("the data open again once the fit mode needs more", async ({ page }) => {
  await open(page);
  await loadSAndRho(page);
  await expect(heading(page)).toBeHidden();

  await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();
  await expect(heading(page)).toBeVisible();
  await expect(summary(page).getByText("Data loaded")).toHaveCount(0);
});

test("the data stay open while they lack some", async ({ page }) => {
  await open(page);
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await load(page, "seebeck", "seebeck.txt");
  await expect(page.getByText(/^31 points/)).toBeVisible();

  await expect(heading(page)).toBeVisible();
  await expect(details(page)).toHaveCount(0);
});

test("a single file stays open, as its mapping is what a user checks", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.unroute("**/api/parse");
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: {
        ...parsedFor("seebeck", 3),
        measurements: {
          ...parsedFor("seebeck", 3).measurements,
          ...parsedFor("resistivity", 3).measurements,
          ...parsedFor("hall", 3).measurements,
        },
      },
    }),
  );
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T,S,rho,R_H\n100,1,1,1\n"),
  });

  await expect(page.locator('[data-file-slot="table"]')).toContainText(
    "all.csv",
  );
  await expect(heading(page)).toBeVisible();
  await expect(details(page)).toHaveCount(0);
});
