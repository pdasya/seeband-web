import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

async function open(page: Page) {
  await serveModels(page);
  await page.goto("/fit");
  await expect(page.getByRole("radio", { name: "DPB" })).toBeVisible();
}

const mode = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true });

test("starts as the design does, with options from the API", async ({
  page,
}) => {
  await open(page);

  await expect(page.getByRole("radio", { name: "DPB" })).toBeChecked();
  await expect(page.getByRole("radio", { name: "SPB" })).not.toBeChecked();
  await expect(mode(page, "S + ρ")).toBeChecked();
  await expect(page.getByText("Double parabolic band")).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Scattering" }),
  ).toContainText("Acoustic phonons (acPh)");
  await expect(page.getByLabel("N₁")).toHaveValue("1");
  await expect(page.getByLabel("Lower bound, K")).toHaveValue("50");
  await expect(page.getByLabel("Upper bound, K")).toHaveValue("800");
});

test("SPB S + ρ + R_H cannot be chosen, and says why", async ({ page }) => {
  await open(page);

  await page.getByRole("radio", { name: "SPB" }).click();

  const disabled = mode(page, "S + ρ + R_H");
  await expect(disabled).toBeDisabled();
  await expect(disabled).not.toBeChecked();
  await expect(
    page.getByText(/S \+ ρ \+ R_H: .*fails on the desktop/),
  ).toBeVisible();
  await disabled.click({ force: true });
  await expect(disabled).not.toBeChecked();
});

test("DPB's S + ρ + R_H can be chosen, with no such text", async ({ page }) => {
  await open(page);

  await mode(page, "S + ρ + R_H").click();

  await expect(mode(page, "S + ρ + R_H")).toBeChecked();
  await expect(page.getByText(/known error/)).toHaveCount(0);
});

test("controls follow the mode: S alone has no scattering, SPB no degeneracy", async ({
  page,
}) => {
  await open(page);

  await mode(page, "S").click();
  await expect(page.getByRole("combobox", { name: "Scattering" })).toHaveCount(
    0,
  );
  await expect(page.getByLabel("N₁")).toBeVisible();

  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(page.getByLabel("N₁")).toHaveCount(0);
});

test("each model keeps its own choices", async ({ page }) => {
  await open(page);
  await mode(page, "S + ρ + R_H").click();
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /acPhDis/ }).click();
  await page.getByLabel("N₂").fill("3");

  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(mode(page, "S")).toBeChecked();
  await mode(page, "S + ρ").click();

  await page.getByRole("radio", { name: "DPB" }).click();
  await expect(mode(page, "S + ρ + R_H")).toBeChecked();
  await expect(
    page.getByRole("combobox", { name: "Scattering" }),
  ).toContainText("acPhDis");
  await expect(page.getByLabel("N₂")).toHaveValue("3");

  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(mode(page, "S + ρ")).toBeChecked();
});

test("pressing the chosen option keeps it", async ({ page }) => {
  await open(page);

  await page.getByRole("radio", { name: "DPB" }).click();
  await mode(page, "S + ρ").click();

  await expect(page.getByRole("radio", { name: "DPB" })).toBeChecked();
  await expect(mode(page, "S + ρ")).toBeChecked();
});

test("missing data are named for the mode, and go as data load", async ({
  page,
}) => {
  await page.route("**/api/parse", (route: Route) =>
    route.fulfill({
      json: {
        column_count: 2,
        row_count: 3,
        preview: [],
        mapping: [],
        measurements: {
          seebeck: {
            temperature_k: [100],
            values: [1],
            points: 1,
            min_temperature_k: 100,
            max_temperature_k: 100,
          },
        },
        errors: [],
        warnings: [],
        warnings_omitted: 0,
        interpolated: {},
        interpolation_failed: [],
      },
    }),
  );
  await open(page);
  const note = page.getByRole("note");
  await expect(note).toContainText("Missing data: S, ρ.");

  await mode(page, "S + ρ + R_H").click();
  await expect(note).toContainText("Missing data: S, ρ, R_H.");

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(note).toContainText("Missing data: ρ, R_H.");

  await mode(page, "S").click();
  await expect(note).toHaveCount(0);
});

test("a range that holds reaches interpolation, and one that does not says so", async ({
  page,
}) => {
  const bodies: { interpolate?: object }[] = [];
  await page.route("**/api/parse", (route: Route) => {
    bodies.push(route.request().postDataJSON() as { interpolate?: object });
    return route.fulfill({
      json: {
        column_count: 2,
        row_count: 3,
        preview: [],
        mapping: [],
        measurements: {
          seebeck: {
            temperature_k: [100],
            values: [1],
            points: 1,
            min_temperature_k: 100,
            max_temperature_k: 100,
          },
        },
        errors: [],
        warnings: [],
        warnings_omitted: 0,
        interpolated: {},
        interpolation_failed: [],
      },
    });
  });
  await open(page);
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await page.getByRole("switch", { name: /Interpolation/ }).click();
  await expect.poll(() => bodies.length).toBe(2);

  await page.getByLabel("Upper bound, K").fill("600");

  await expect
    .poll(() => bodies.at(-1)?.interpolate)
    .toEqual({ min_temperature_k: 50, max_temperature_k: 600 });

  const before = bodies.length;
  await page.getByLabel("Upper bound, K").fill("10");
  await expect(page.getByRole("alert")).toContainText(
    "lower bound must be below the upper",
  );
  await page.waitForTimeout(500);
  expect(bodies).toHaveLength(before);
  await expect(page.getByText("Fit range 50–600 K")).toBeVisible();
});

test("a degeneracy that cannot be used stays out of the session", async ({
  page,
}) => {
  await open(page);

  await page.getByLabel("N₁").fill("0");

  await expect(page.getByLabel("N₁")).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("N₁").fill("2");
  await expect(page.getByLabel("N₁")).toHaveAttribute("aria-invalid", "false");
});

test("the choices stay when moving to another screen and back", async ({
  page,
}) => {
  await open(page);
  await mode(page, "S").click();
  await page.getByLabel("Upper bound, K").fill("700");

  await page.getByRole("link", { name: "Results" }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(mode(page, "S")).toBeChecked();
  await expect(page.getByLabel("Upper bound, K")).toHaveValue("700");
});

test("descriptions that cannot load say so", async ({ page }) => {
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 400,
      json: { code: "x", message: "SECRET-VALUE", details: [] },
    }),
  );

  await page.goto("/fit");

  await expect(page.getByRole("alert")).toContainText("could not be loaded");
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);
});
