import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

// Against a real API, as the mock's answers do not depend on the file. See the README.
test.skip(
  process.env.SEEBAND_API_TARGET === undefined,
  "Needs a real API, through SEEBAND_API_TARGET",
);

const slots = (page: Page) => page.locator("[data-file-slot]");

const EXAMPLES = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/",
    import.meta.url,
  ),
);

for (const example of ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]) {
  test(`all files of ${example} load`, async ({ page }) => {
    await page.goto("/fit");

    for (const suffix of ["see", "rho", "hall"]) {
      const name = `${example}_${suffix}.txt`;
      // A slot with a file has no input, so the first input left is the next slot.
      await page
        .locator('input[type="file"]')
        .first()
        .setInputFiles(`${EXAMPLES}${name}`);
      await expect(slots(page).getByText(name)).toBeVisible();
    }

    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(
      slots(page).getByText(/\d+ points · .* K · V\/K/),
    ).toBeVisible();
    await expect(
      slots(page).getByText(/\d+ points · .* K · Ω·m/),
    ).toBeVisible();
    await expect(
      slots(page).getByText(/\d+ points · .* K · m³\/C/),
    ).toBeVisible();
  });
}

test("a broken file shows a specific error from the real parser", async ({
  page,
}) => {
  await page.goto("/fit");
  const good = readFileSync(`${EXAMPLES}01_Fe2VAl09Si01_see.txt`, "utf8");
  const lines = good.split("\n");
  lines[3] = "300 not-a-number";

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "broken.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(lines.join("\n")),
    });

  await expect(page.getByRole("alert")).toContainText("broken.txt");
  await expect(page.getByRole("alert")).toContainText("Line 4");
});

test("a single file maps its columns through the real parser", async ({
  page,
}) => {
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
  const table =
    "T,S,rho\n100,1e-4,1e-5\n200,2e-4,2e-5\n300,3e-4,3e-5\n400,4e-4,4e-5\n500,5e-4,5e-5\n600,6e-4,6e-5\n";

  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from(table),
  });

  await expect(page.getByText("S · 6 points")).toBeVisible();
  await expect(page.getByText("ρ · 6 points")).toBeVisible();
  await expect(page.getByText("R_H · not found")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column rho" }).click();
  await page.getByRole("option", { name: "R_H", exact: true }).click();
  await expect(page.getByText("R_H · 6 points")).toBeVisible();
  await expect(page.getByText("ρ · not found")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "Ignore", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "No column holds the temperature",
  );

  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "T", exact: true }).click();
  await expect(page.getByText("S · 6 points")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column rho" }).click();
  await page.getByRole("option", { name: "S", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("assigned twice");
});

test("interpolation of an example through the real API has its flags", async ({
  page,
}) => {
  await page.goto("/fit");
  // Its data run from 25 to 750 K, and the default range ends at 800 K.
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles(`${EXAMPLES}01_Fe2VAl09Si01_see.txt`);
  await expect(slots(page).getByText(/\d+ points/)).toBeVisible();

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "S: the grid goes beyond the data",
  );

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(
    slots(page).getByText("30 points · 25–750 K · V/K"),
  ).toBeVisible();
});

test("the real model descriptions fill the model panel", async ({ page }) => {
  await page.goto("/fit");

  await expect(page.getByRole("radio", { name: "DPB" })).toBeChecked();
  await expect(
    page.getByRole("radio", { name: "S + ρ", exact: true }),
  ).toBeChecked();

  await page.getByRole("radio", { name: "SPB" }).click();

  await expect(
    page.getByRole("radio", { name: "S + ρ + R_H", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText(/fails on the desktop/)).toBeVisible();
});

test("the real descriptions fill the parameters", async ({ page }) => {
  await page.goto("/fit");

  await expect(
    page.getByRole("textbox", { name: "E_F", exact: true }),
  ).toHaveValue("-100");
  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(
    page.getByRole("slider", { name: "m", exact: true }),
  ).toHaveAttribute("aria-valuemin", "-3");
});

test("an example through the real API draws the curve, with its RMSE", async ({
  page,
}) => {
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles(`${EXAMPLES}01_Fe2VAl09Si01_see.txt`);

  await expect(page.getByText("RMSE, S")).toBeVisible();
  await expect(page.getByText(/^[\d,]+ µV\/K$/)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const before = await page.getByText(/^[\d,]+ µV\/K$/).textContent();

  await page.getByRole("slider", { name: "E_F" }).press("PageUp");

  await expect(page.getByText(/^[\d,]+ µV\/K$/)).not.toHaveText(before ?? "");
});
