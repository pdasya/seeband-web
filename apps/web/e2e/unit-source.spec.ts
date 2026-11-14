import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

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

type Source = "chosen" | "header" | "default";

function measurement(minK: number, maxK: number, loadedAs: string) {
  return {
    temperature_k: [minK, maxK],
    values: [1e-4, 2e-4],
    points: 2,
    min_temperature_k: minK,
    max_temperature_k: maxK,
    loaded_as: loadedAs,
  };
}

/** An answer of `POST /api/parse` for T and one quantity, with where each unit came from. */
function parsed({
  quantity = "seebeck",
  units = ["K", "V/K"],
  sources = ["default", "default"],
  preview = [100, 1e-4],
  previewSi = [100, 1e-4],
  rangeK = [100, 300],
  warnings = [],
}: {
  quantity?: string;
  units?: [string, string];
  sources?: [Source, Source];
  preview?: [number, number];
  previewSi?: [number, number];
  rangeK?: [number, number];
  warnings?: object[];
} = {}) {
  return {
    headers: ["T", "x"],
    column_count: 2,
    row_count: 2,
    preview: [preview],
    preview_si: [previewSi],
    mapping: [
      {
        column: 0,
        role: "temperature",
        unit: units[0],
        unit_source: sources[0],
      },
      { column: 1, role: quantity, unit: units[1], unit_source: sources[1] },
    ],
    measurements: {
      [quantity]: measurement(rangeK[0], rangeK[1], quantity),
    },
    errors: [],
    warnings,
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    interpolation_failure_reasons: {},
  };
}

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

async function load(page: Page, quantity: string, name = "s.txt") {
  await page
    .locator(`[data-file-slot="${quantity}"] input[type="file"]`)
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from("T x\n100 1\n"),
    });
}

const seebeckUnit = (page: Page) =>
  page.getByRole("combobox", { name: "Unit of Seebeck coefficient" });
const temperatureUnit = (page: Page) =>
  page.getByRole("combobox", {
    name: "Unit of Temperature, Seebeck coefficient",
  });

const ASSUMED = /, assumed$/;

test.beforeEach(async ({ page }) => {
  await serveModels(page);
});

test("a unit nothing named is marked as assumed, and choosing one, even SI, removes the mark", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsed(),
    parsed({ sources: ["default", "chosen"] }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(seebeckUnit(page)).toHaveText("V/K");
  // The name replaces the text shown, so it names the unit as well.
  await expect(seebeckUnit(page)).toHaveAccessibleName(
    "Unit of Seebeck coefficient: V/K, assumed",
  );
  await expect(temperatureUnit(page)).toHaveText("K");
  await expect(temperatureUnit(page)).toHaveAccessibleName(ASSUMED);
  await expect(
    page.getByText(
      "SI is assumed for T, S, as no unit SeeBand reads was named.",
      {
        exact: false,
      },
    ),
  ).toBeVisible();

  await seebeckUnit(page).click();
  await page.getByRole("option", { name: "V/K", exact: true }).click();

  await expect(seebeckUnit(page)).toHaveAccessibleName(
    "Unit of Seebeck coefficient",
  );
  await expect(seebeckUnit(page)).toHaveText("V/K");
  await expect(temperatureUnit(page)).toHaveAccessibleName(ASSUMED);
  await expect(
    page.getByText("SI is assumed for T, as no unit SeeBand reads was named.", {
      exact: false,
    }),
  ).toBeVisible();
  // T was not chosen, so it goes again with no unit and stays assumed.
  expect(bodies[1]?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 1, role: "seebeck", unit: "V/K" },
  ]);
});

test("a unit from the header is never marked as assumed", async ({ page }) => {
  await serveParse(
    page,
    parsed({ units: ["K", "uV/K"], sources: ["header", "header"] }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(seebeckUnit(page)).toHaveText("µV/K");
  await expect(seebeckUnit(page)).not.toHaveAccessibleName(ASSUMED);
  await expect(temperatureUnit(page)).toHaveText("K");
  await expect(temperatureUnit(page)).not.toHaveAccessibleName(ASSUMED);
  await expect(page.getByText(/assumed/)).toHaveCount(0);
});

test("a file card shows its first row as written, and in SI where the unit is another", async ({
  page,
}) => {
  await serveParse(
    page,
    parsed({
      units: ["C", "uV/K"],
      sources: ["header", "header"],
      preview: [26.85, 100],
      previewSi: [300, 1e-4],
    }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(
    page.getByText(
      "First row: T 26,85 °C = 300 K in SI · S 1,000e+2 µV/K = 1,000e-4 V/K in SI",
      { exact: true },
    ),
  ).toBeVisible();
});

test("a doubt about a unit says which way it likely went, and Hide leaves a warning on its chip", async ({
  page,
}) => {
  await serveParse(
    page,
    parsed({ warnings: [{ code: "implausible_magnitude", column: 1 }] }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/If the file is in µV\/K, choose µV\/K\. If it is in mV\/K/),
  ).toBeVisible();

  await page.getByRole("button", { name: "Hide" }).click();

  const summary = page.getByRole("region", { name: "Data" });
  await expect(
    summary.getByRole("listitem").filter({ hasText: /^S/ }),
  ).toHaveText("S · 2 pts · check the unit");
});

test("separate files whose T is about 273 K apart are flagged, as °C read as K gives", async ({
  page,
}) => {
  await page.route("**/api/parse", (route: Route) => {
    const { expected } = route.request().postDataJSON() as ParseBody;
    return route.fulfill({
      json:
        expected === "resistivity"
          ? parsed({
              quantity: "resistivity",
              units: ["K", "Ohm*m"],
              rangeK: [27, 527],
            })
          : parsed({ rangeK: [300, 800] }),
    });
  });
  await page.goto("/fit");
  await load(page, "seebeck");
  await expect(seebeckUnit(page)).toBeVisible();
  await expect(page.getByText("Check the unit of T")).toHaveCount(0);

  await load(page, "resistivity", "rho.txt");

  await expect(page.getByText("Check the unit of T")).toBeVisible();
  await expect(
    page.getByText(
      /T of ρ \(27–527 K\) is about 273 K below T of S \(300–800 K\) at both ends.*If the file of ρ gives T in °C, choose °C for its T\. If both give T in K, nothing needs to change\./,
    ),
  ).toBeVisible();

  // A hint, not a doubt: Hide still folds the data, and the bar says it in words.
  await page.getByRole("button", { name: "Hide" }).click();
  await expect(
    page.getByRole("region", { name: "Data" }).getByRole("listitem"),
  ).toContainText(["T · check the unit"]);
});

test("a column of a single table read in SI by default is marked as assumed", async ({
  page,
}) => {
  await serveParse(page, {
    ...parsed({ sources: ["header", "default"] }),
    headers: ["T (K)", "S"],
  });
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T (K),S\n100,1e-4\n"),
  });

  const unitOfS = page.getByRole("combobox", { name: "Unit of S" });
  await expect(unitOfS).toHaveText("V/K");
  await expect(unitOfS).toHaveAccessibleName(ASSUMED);
  const unitOfT = page.getByRole("combobox", { name: "Unit of T (K)" });
  await expect(unitOfT).toHaveText("K");
  await expect(unitOfT).not.toHaveAccessibleName(ASSUMED);
  await expect(
    page.getByText("SI is assumed for S, as no unit SeeBand reads was named.", {
      exact: false,
    }),
  ).toBeVisible();
});
