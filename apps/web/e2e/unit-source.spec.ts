import { expect, test, type Page, type Route } from "@playwright/test";

import { fakeFit } from "./support/fakeFit";
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
  previewText = ["100", "1e-4"],
  previewSi = [100, 1e-4],
  rangeK = [100, 300],
  warnings = [],
}: {
  quantity?: string;
  units?: [string, string];
  sources?: [Source, Source];
  preview?: [number, number];
  previewText?: [string, string];
  previewSi?: [number, number];
  rangeK?: [number, number];
  warnings?: object[];
} = {}) {
  return {
    headers: ["T", "x"],
    column_count: 2,
    row_count: 2,
    preview: [preview],
    preview_text: [previewText],
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

  await seebeckUnit(page).click();
  await page.getByRole("option", { name: "V/K", exact: true }).click();

  await expect(seebeckUnit(page)).toHaveAccessibleName(
    "Unit of Seebeck coefficient",
  );
  await expect(seebeckUnit(page)).toHaveText("V/K");
  await expect(temperatureUnit(page)).toHaveAccessibleName(ASSUMED);
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
      previewText: ["26.85", "1.0E+2"],
      previewSi: [300, 1e-4],
    }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(
    page.getByText(
      // As the file writes it, so that the user can find it there.
      "First row: T 26.85 °C = 300 K in SI · S 1.0E+2 µV/K = 1,000e-4 V/K in SI",
      { exact: true },
    ),
  ).toBeVisible();
});

test("a doubt about a unit says which way it likely went, and Hide leaves a warning on its chip", async ({
  page,
}) => {
  await serveParse(
    page,
    parsed({
      warnings: [
        { code: "implausible_magnitude", column: 1, direction: "above" },
      ],
    }),
  );
  await page.goto("/fit");
  await load(page, "seebeck");

  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "These values are far larger than any usual Seebeck coefficient in V/K, the unit assumed. If the file is in µV/K or mV/K, choose it.",
    ),
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
});

test("the units of ρ come grouped by metre and centimetre, and µΩ·cm reads the file again", async ({
  page,
}) => {
  const bodies = await serveParse(
    page,
    parsed({ quantity: "resistivity", units: ["K", "Ohm*m"] }),
    parsed({
      quantity: "resistivity",
      units: ["K", "uOhm*cm"],
      sources: ["default", "chosen"],
    }),
  );
  await page.goto("/fit");
  await load(page, "resistivity", "rho.txt");

  const unitOfRho = page.getByRole("combobox", {
    name: /^Unit of Resistivity/,
  });
  await unitOfRho.click();
  await expect(page.getByRole("group")).toHaveCount(2);
  await expect(
    page.getByRole("group", { name: "Per metre" }).getByRole("option"),
  ).toHaveText(["Ω·m", "µΩ·m"]);
  await expect(
    page.getByRole("group", { name: "Per centimetre" }).getByRole("option"),
  ).toHaveText(["Ω·cm", "mΩ·cm", "µΩ·cm"]);
  await page.getByRole("option", { name: "µΩ·cm", exact: true }).click();

  await expect(unitOfRho).toHaveText("µΩ·cm");
  expect(bodies[1]?.mapping?.[1]).toEqual({
    column: 1,
    role: "resistivity",
    unit: "uOhm*cm",
  });
});

test("a fit and a guess wait while a unit is in doubt, and run once the values are confirmed", async ({
  page,
}) => {
  await serveParse(
    page,
    parsed({
      rangeK: [300, 800],
      warnings: [
        { code: "implausible_magnitude", column: 1, direction: "above" },
      ],
    }),
  );
  const guesses: unknown[] = [];
  await page.route("**/api/guess", (route) => {
    guesses.push(route.request().postDataJSON());
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await load(page, "seebeck");

  const run = page.getByRole("button", { name: "Run fit" });
  const guess = page.getByRole("button", { name: "Initial guess" });
  await expect(run).toBeDisabled();
  await expect(
    page.getByText(
      "Check the unit of S first, or confirm under Data that the values are right.",
    ),
  ).toBeVisible();
  await expect(guess).toBeDisabled();
  await expect(guess).toHaveAttribute("title", /Check the unit of S first/);
  // S in doubt does not start the guess that a new S file starts.
  await page.waitForTimeout(300);
  expect(guesses).toHaveLength(0);

  await page.getByRole("button", { name: /^Values are right/ }).click();

  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByText(/You confirmed these values despite the unit check/),
  ).toBeVisible();
  await expect(run).toBeEnabled();
  await expect.poll(() => guesses.length).toBe(1);

  // Confirmed, the data fold like any others.
  await page.getByRole("button", { name: "Hide" }).click();
  await expect(
    page
      .getByRole("region", { name: "Data" })
      .getByRole("listitem")
      .filter({ hasText: /^S/ }),
  ).toHaveText("S · 2 pts");
});

test("a confirmation ends when the unit changes", async ({ page }) => {
  const doubt = [
    { code: "implausible_magnitude", column: 1, direction: "above" },
  ];
  await serveParse(
    page,
    parsed({ rangeK: [300, 800], warnings: doubt }),
    parsed({
      rangeK: [300, 800],
      units: ["K", "mV/K"],
      sources: ["default", "chosen"],
      warnings: doubt,
    }),
  );
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await load(page, "seebeck");
  await page.getByRole("button", { name: /^Values are right/ }).click();
  await expect(page.getByRole("button", { name: "Run fit" })).toBeEnabled();

  await seebeckUnit(page).click();
  await page.getByRole("option", { name: "mV/K", exact: true }).click();

  await expect(page.getByText("Check the unit", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run fit" })).toBeDisabled();
});

test("a single table's doubt is confirmed there too, and then a fit runs", async ({
  page,
}) => {
  await serveParse(page, {
    ...parsed({
      rangeK: [300, 800],
      warnings: [
        { code: "implausible_magnitude", column: 1, direction: "above" },
      ],
    }),
    headers: ["T", "S"],
  });
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T,S\n300,200\n"),
  });
  const run = page.getByRole("button", { name: "Run fit" });
  await expect(run).toBeDisabled();

  await page.getByRole("button", { name: /^Values are right/ }).click();

  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
  await expect(run).toBeEnabled();
});

const DOUBT = [
  { code: "implausible_magnitude", column: 1, direction: "above" },
];

test("two quantities in doubt are confirmed each by its own named button", async ({
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
              rangeK: [300, 800],
              warnings: DOUBT,
            })
          : parsed({ rangeK: [300, 800], warnings: DOUBT }),
    });
  });
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await load(page, "seebeck");
  await load(page, "resistivity", "rho.txt");
  const run = page.getByRole("button", { name: "Run fit" });
  await expect(run).toBeDisabled();
  await expect(
    page.getByText("Check the unit of S, ρ first", { exact: false }),
  ).toBeVisible();
  // The reason is Run fit's description, and a screen reader hears it as it changes.
  await expect(run).toHaveAccessibleDescription(/Check the unit of S, ρ first/);

  await page.getByRole("button", { name: "Values are right for S" }).click();

  await expect(run).toBeDisabled();
  await expect(run).toHaveAccessibleDescription(/Check the unit of ρ first/);
  await expect(
    page.getByRole("button", { name: "Values are right for S" }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Values are right for ρ" }).click();

  await expect(run).toBeEnabled();
  await expect(
    page.getByRole("status").filter({ hasText: /You confirmed these values/ }),
  ).toHaveCount(2);
});

test("a single table keeps the confirmation of a column whose values do not change", async ({
  page,
}) => {
  const table = (seebeckUnit: string) => ({
    ...parsed({ rangeK: [300, 800] }),
    headers: ["T", "S", "rho"],
    column_count: 3,
    preview: [[300, 1e-4, 5]],
    preview_text: [["300", "1e-4", "5"]],
    preview_si: [[300, 1e-4, 5]],
    mapping: [
      { column: 0, role: "temperature", unit: "K", unit_source: "default" },
      {
        column: 1,
        role: "seebeck",
        unit: seebeckUnit,
        unit_source: seebeckUnit === "V/K" ? "default" : "chosen",
      },
      { column: 2, role: "resistivity", unit: "Ohm*m", unit_source: "default" },
    ],
    measurements: {
      seebeck: {
        temperature_k: [300, 800],
        values: seebeckUnit === "V/K" ? [1e-4, 2e-4] : [1e-10, 2e-10],
        points: 2,
        min_temperature_k: 300,
        max_temperature_k: 800,
        loaded_as: "seebeck",
      },
      resistivity: {
        temperature_k: [300, 800],
        values: [5, 6],
        points: 2,
        min_temperature_k: 300,
        max_temperature_k: 800,
        loaded_as: "resistivity",
      },
    },
    warnings: [
      { code: "implausible_magnitude", column: 2, direction: "above" },
    ],
  });
  await serveParse(page, table("V/K"), table("uV/K"));
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T,S,rho\n300,1e-4,5\n"),
  });
  await page.getByRole("button", { name: "Values are right for ρ" }).click();
  const run = page.getByRole("button", { name: "Run fit" });
  await expect(run).toBeEnabled();

  // S in another unit gives new S, but ρ reads the same, so it stays confirmed.
  await page.getByRole("combobox", { name: /^Unit of S/ }).click();
  await page.getByRole("option", { name: "µV/K", exact: true }).click();
  await expect(page.getByRole("combobox", { name: /^Unit of S/ })).toHaveText(
    "µV/K",
  );

  await expect(run).toBeEnabled();
  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
});

test("a running fit stops when its data come back in doubt", async ({
  page,
}) => {
  await fakeFit(page);
  await serveParse(
    page,
    parsed({ rangeK: [300, 800] }),
    parsed({
      rangeK: [300, 800],
      units: ["K", "uV/K"],
      sources: ["default", "chosen"],
      warnings: [
        { code: "implausible_magnitude", column: 1, direction: "below" },
      ],
    }),
  );
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await load(page, "seebeck");
  await page.getByRole("button", { name: "Run fit" }).click();
  await expect
    .poll(() => page.evaluate(() => window.fitTest.bodies.length))
    .toBe(1);
  await page.evaluate(() => {
    window.fitTest.send({ type: "started" });
  });
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();

  await seebeckUnit(page).click();
  await page.getByRole("option", { name: "µV/K", exact: true }).click();

  await expect.poll(() => page.evaluate(() => window.fitTest.aborted)).toBe(1);
  await expect(page.getByRole("button", { name: "Run fit" })).toBeDisabled();
});
