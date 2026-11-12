import { expect, test, type Page, type Route } from "@playwright/test";

import { fitBadges } from "./support/fitScreen";
import { serveModels } from "./support/models";

async function open(page: Page) {
  await serveModels(page);
  await page.goto("/fit");
  await expect(page.getByRole("radio", { name: "DPB" })).toBeVisible();
}

async function serveParse(page: Page, bodies: object[]) {
  await page.route("**/api/parse", (route: Route) => {
    bodies.push(route.request().postDataJSON() as object);
    return route.fulfill({
      json: {
        headers: ["T", "x"],
        column_count: 2,
        row_count: 3,
        preview: [],
        preview_si: [],
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
  await expect(
    page.getByRole("radio", { name: "DPB" }),
  ).toHaveAccessibleDescription("Double parabolic band");
  await expect(page.getByText("Double parabolic band")).toBeHidden();
  // The chosen one looks chosen.
  const background = (name: string) =>
    page
      .getByRole("radio", { name, exact: true })
      .evaluate((item) => getComputedStyle(item).backgroundColor);
  expect(await background("DPB")).not.toBe(await background("SPB"));
  expect(await background("DPB")).toBe(await background("S + ρ"));
  await page.getByRole("radio", { name: "SPB" }).hover();
  await expect(page.getByRole("tooltip")).toHaveText("Single parabolic band");
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
  await page.getByLabel("N₂").blur();

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
        headers: ["T", "x"],
        column_count: 2,
        row_count: 3,
        preview: [],
        preview_si: [],
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
  // The fit panel names what is missing, and Model no longer repeats it.
  const note = fitBadges(page);
  await expect(page.getByRole("note")).toHaveCount(0);
  await expect(note).toHaveText("Missing data: S, ρ");

  await mode(page, "S + ρ + R_H").click();
  await expect(note).toHaveText("Missing data: S, ρ, R_H");

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(note).toHaveText("Missing data: ρ, R_H");

  await mode(page, "S").click();
  await expect(note).toHaveCount(0);
});

test("a range that holds reaches interpolation, and one that does not says so", async ({
  page,
}) => {
  const bodies: { interpolate?: object }[] = [];
  await serveParse(page, bodies);
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
  await page.getByLabel("Upper bound, K").blur();

  await expect
    .poll(() => bodies.at(-1)?.interpolate)
    .toEqual({ min_temperature_k: 50, max_temperature_k: 600 });

  const before = bodies.length;
  await page.getByLabel("Upper bound, K").fill("10");
  await page.getByLabel("Upper bound, K").press("Enter");
  await expect(page.getByRole("alert")).toContainText(
    "lower bound must be below the upper",
  );
  await page.waitForTimeout(500);
  expect(bodies).toHaveLength(before);
  await expect(page.getByText("Fit range 50–600 K")).toBeVisible();
});

for (const value of ["0.5", "2.5"]) {
  test(`a degeneracy of ${value} is kept`, async ({ page }) => {
    await open(page);

    await page.getByLabel("N₁").fill(value);
    await page.getByLabel("N₁").blur();

    await expect(page.getByLabel("N₁")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
    await expect(page.getByRole("alert")).toHaveCount(0);

    await page.getByRole("link", { name: "Results", exact: true }).click();
    await page.getByRole("link", { name: "Model fit" }).click();
    await expect(page.getByLabel("N₁")).toHaveValue(value.replace(".", ","));
  });
}

for (const value of ["0", "-1", "", "abc"]) {
  test(`a degeneracy of "${value}" says so and stays out of the session`, async ({
    page,
  }) => {
    await open(page);
    await page.getByLabel("N₁").fill("2");
    await page.getByLabel("N₁").press("Enter");

    await page.getByLabel("N₁").fill(value);
    await page.getByLabel("N₁").blur();

    await expect(page.getByLabel("N₁")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByLabel("N₂")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
    await expect(page.getByRole("alert")).toContainText("must be above 0");

    await page.getByRole("link", { name: "Results", exact: true }).click();
    await page.getByRole("link", { name: "Model fit" }).click();
    await expect(page.getByLabel("N₁")).toHaveValue("2");
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("typing a correction clears the message about a degeneracy", async ({
  page,
}) => {
  await open(page);
  await page.getByLabel("N₁").fill("0");
  await page.getByLabel("N₁").blur();
  await expect(page.getByRole("alert")).toBeVisible();

  await page.getByLabel("N₁").fill("3");

  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("not fitted")).toBeVisible();
});

test("the data panel shows numbers with a comma too", async ({ page }) => {
  await page.route("**/api/parse", (route: Route) =>
    route.fulfill({
      json: {
        headers: ["T", "x"],
        column_count: 2,
        row_count: 2,
        preview: [],
        preview_si: [],
        mapping: [],
        measurements: {
          seebeck: {
            temperature_k: [100.5, 200.5],
            values: [1, 2],
            points: 2,
            min_temperature_k: 100.5,
            max_temperature_k: 200.5,
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
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100.5 1\n200.5 2\n"),
    });
  await expect(
    page.getByText("2 points · 100,5–200,5 K · V/K", { exact: true }),
  ).toBeVisible();

  await page.getByLabel("Lower bound, K").fill("50.5");
  await page.getByLabel("Lower bound, K").blur();
  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.getByText("Fit range 50,5–800 K")).toBeVisible();
});

test("a fractional range is kept", async ({ page }) => {
  await open(page);

  await page.getByLabel("Lower bound, K").fill("50.5");
  await page.getByLabel("Upper bound, K").fill("600.25");
  await page.getByLabel("Upper bound, K").blur();

  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();
  await expect(page.getByLabel("Lower bound, K")).toHaveValue("50,5");
  await expect(page.getByLabel("Upper bound, K")).toHaveValue("600,25");
});

test("a range being typed sends nothing until it is finished", async ({
  page,
}) => {
  const bodies: object[] = [];
  await serveParse(page, bodies);
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

  const upper = page.getByLabel("Upper bound, K");
  await upper.clear();
  // On the way to 600, 6 is below the lower bound, and 60 is a valid range.
  await upper.pressSequentially("60");
  await page.waitForTimeout(500);
  expect(bodies).toHaveLength(2);
  await expect(page.getByRole("alert")).toHaveCount(0);

  await upper.pressSequentially("0");
  await upper.press("Enter");

  await expect.poll(() => bodies.length).toBe(3);
  await expect(page.getByText("Fit range 50–600 K")).toBeVisible();
});

test("leaving a field unchanged keeps a result, and changing one clears it", async ({
  page,
}) => {
  await open(page);
  const fitStatus = () =>
    page.evaluate(async () => {
      const path = "/src/session/store.ts";
      const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
        useSessionStore: { getState: () => { fit: { status: string } } };
      };
      return useSessionStore.getState().fit.status;
    });
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          fitRequested: () => number;
          fitEvent: (run: number, event: object) => void;
        };
      };
    };
    const state = useSessionStore.getState();
    state.fitEvent(state.fitRequested(), {
      type: "done",
      result: {
        parameters: {},
        status: "converged",
        parameter_errors: {},
        at_bounds: [],
        known_issues: [],
      },
    });
  });
  expect(await fitStatus()).not.toBe("idle");

  for (const label of ["N₁", "N₂", "Lower bound, K", "Upper bound, K"]) {
    await page.getByLabel(label).focus();
    await page.getByLabel(label).press("Enter");
    await page.getByLabel(label).blur();
  }
  expect(await fitStatus()).not.toBe("idle");

  await page.getByLabel("N₁").fill("2");
  await page.getByLabel("N₁").blur();
  await expect.poll(fitStatus).toBe("idle");
});

test("the choices stay when moving to another screen and back", async ({
  page,
}) => {
  await open(page);
  await mode(page, "S").click();
  await page.getByLabel("Upper bound, K").fill("700");

  await page.getByRole("link", { name: "Results", exact: true }).click();
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

test("Parameters and Model stand in a row, of one size", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page);
  const box = (name: string) =>
    page
      .locator("section", { has: page.getByRole("heading", { name }) })
      .boundingBox();
  const parameters = await box("Parameters");
  const model = await box("Model");

  expect(model?.y).toBe(parameters?.y);
  expect(model?.x).toBeGreaterThan(parameters?.x ?? 0);
  expect(model?.width).toBeCloseTo(parameters?.width ?? 0, 0);
  expect(model?.height).toBeCloseTo(parameters?.height ?? 0, 0);
});

test("the choice of bands has no visible label, and keeps its name", async ({
  page,
}) => {
  await open(page);

  await expect(page.getByText("Number of bands")).toHaveCount(0);
  await expect(
    page.getByRole("radiogroup", { name: "Number of bands" }),
  ).toBeVisible();
  await expect(page.getByText("Fit mode", { exact: true })).toBeVisible();
});
