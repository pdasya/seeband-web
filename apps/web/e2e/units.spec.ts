import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

const SEEBECK = {
  temperature_k: [100, 200, 300],
  values: [1e-4, 2e-4, 3e-4],
  points: 3,
  min_temperature_k: 100,
  max_temperature_k: 300,
};

interface ColumnRole {
  column: number;
  role: string;
  unit?: string;
}

interface ParseBody {
  text: string;
  expected?: string;
  mapping?: ColumnRole[];
}

/** An answer of `POST /api/parse` for a file of T and S, read in these units. */
function parsedS(
  temperatureUnit: string,
  seebeckUnit: string,
  warnings: object[] = [],
) {
  return {
    headers: ["T", "S"],
    column_count: 2,
    row_count: 3,
    preview: [
      [100, 100],
      [200, 200],
      [300, 300],
    ],
    preview_si: [
      [100, 1e-4],
      [200, 2e-4],
      [300, 3e-4],
    ],
    mapping: [
      { column: 0, role: "temperature", unit: temperatureUnit },
      { column: 1, role: "seebeck", unit: seebeckUnit },
    ],
    measurements: { seebeck: SEEBECK },
    errors: [],
    warnings,
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
  };
}

const IMPLAUSIBLE = [{ code: "implausible_magnitude", column: 1 }];

/** Answers each request with the next answer, and keeps the bodies sent. */
async function serveParse(page: Page, ...answers: object[]) {
  const bodies: ParseBody[] = [];
  await page.route("**/api/parse", (route: Route) => {
    bodies.push(route.request().postDataJSON() as ParseBody);
    const answer = answers[Math.min(bodies.length, answers.length) - 1];
    return route.fulfill({ status: 200, json: answer });
  });
  return bodies;
}

async function loadSeebeck(page: Page, text = "T S\n100 100\n") {
  await page
    .locator('input[type="file"]')
    .nth(0)
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(text),
    });
}

const seebeckUnit = (page: Page) =>
  page.getByRole("combobox", { name: "Unit of Seebeck coefficient" });
const temperatureUnit = (page: Page) =>
  page.getByRole("combobox", {
    name: "Unit of Temperature, Seebeck coefficient",
  });

async function pick(
  page: Page,
  combobox: ReturnType<Page["getByRole"]>,
  option: string,
) {
  await combobox.click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await serveModels(page);
});

test("values that look like µV/K read as V/K show an alert, and keep the data open", async ({
  page,
}) => {
  await serveParse(page, parsedS("K", "V/K", IMPLAUSIBLE));
  await page.goto("/fit");
  await loadSeebeck(page);

  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();
  await expect(seebeckUnit(page)).toHaveText("V/K");
  // The panel stays open, so the alert is in view before a fit.
  await expect(page.getByRole("button", { name: "Hide" })).toBeVisible();
});

test("choosing µV/K reads the file again in it, and the alert goes", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsedS("K", "V/K", IMPLAUSIBLE),
    parsedS("K", "uV/K"),
  );
  await page.goto("/fit");
  await loadSeebeck(page);
  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();

  await pick(page, seebeckUnit(page), "µV/K");

  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
  await expect(seebeckUnit(page)).toHaveText("µV/K");
  expect(bodies).toHaveLength(2);
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "K" },
    { column: 1, role: "seebeck", unit: "uV/K" },
  ]);
});

test("the temperature can be in °C, which goes with the request", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsedS("K", "V/K"),
    parsedS("C", "V/K"),
  );
  await page.goto("/fit");
  await loadSeebeck(page);

  await pick(page, temperatureUnit(page), "°C");

  await expect(temperatureUnit(page)).toHaveText("°C");
  expect(bodies[1]?.mapping?.[0]).toEqual({
    column: 0,
    role: "temperature",
    unit: "C",
  });
});

test("a unit the header names is the one shown", async ({ page }) => {
  await serveParse(page, parsedS("C", "uV/K"));
  await page.goto("/fit");
  await loadSeebeck(page, "T (°C)\tS (uV/K)\n-173.15\t100\n");

  await expect(temperatureUnit(page)).toHaveText("°C");
  await expect(seebeckUnit(page)).toHaveText("µV/K");
});

test("a file with no header sends the units chosen with its columns", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    {
      ...parsedS("K", "V/K"),
      headers: undefined,
      mapping: [{ column: 0, role: "temperature", unit: "K" }],
      measurements: {},
      errors: [{ code: "missing_temperature" }],
      column_count: 3,
      preview: [[100, 100, 7]],
      preview_si: [[100, null, null]],
    },
    parsedS("C", "V/K"),
    parsedS("C", "uV/K"),
  );
  await page.goto("/fit");
  await loadSeebeck(page, "100 100 7\n");

  // T's unit is chosen before the quantity, as naming the quantity loads the file.
  await pick(
    page,
    page.getByRole("combobox", { name: "Unit of Column 1" }),
    "°C",
  );
  await pick(
    page,
    page.getByRole("combobox", { name: "Quantity for column Column 2" }),
    "S",
  );

  await expect(temperatureUnit(page)).toHaveText("°C");
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "C" },
    { column: 1, role: "seebeck" },
  ]);

  // The quantity's unit is chosen on the loaded file.
  await pick(page, seebeckUnit(page), "µV/K");
  await expect(seebeckUnit(page)).toHaveText("µV/K");
  expect(bodies[2]?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "C" },
    { column: 1, role: "seebeck", unit: "uV/K" },
  ]);
});

test("a table shows the first value in SI next to its unit", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsedS("K", "V/K"),
    parsedS("K", "uV/K"),
  );
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "table.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 100\n"),
    });
  await expect(page.getByText("1,000e+2 V/K")).toBeVisible();

  await pick(page, page.getByRole("combobox", { name: "Unit of S" }), "µV/K");

  await expect(
    page.getByText("1,000e+2 µV/K = 1,000e-4 V/K in SI"),
  ).toBeVisible();
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "K" },
    { column: 1, role: "seebeck", unit: "uV/K" },
  ]);
});

test("values that look wrong in a column the slot does not use leave it alone", async ({
  page,
}) => {
  await serveParse(
    page,
    parsedS("K", "uV/K", [{ code: "implausible_magnitude", column: 2 }]),
  );
  await page.goto("/fit");
  await loadSeebeck(page);

  await expect(seebeckUnit(page)).toHaveText("µV/K");
  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
});

test("a unit the header names that SeeBand cannot read shows as an alert", async ({
  page,
}) => {
  await serveParse(
    page,
    parsedS("K", "V/K", [{ code: "unit_assumed", column: 1 }]),
  );
  await page.goto("/fit");
  await loadSeebeck(page);

  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      /so the values are read in SI\. Choose the unit they are in/,
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Hide" })).toBeVisible();
});
