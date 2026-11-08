import { expect, test, type Page } from "@playwright/test";

import { DEMO, serveModels } from "./support/models";

// As the API answers: with no header, it leaves `headers` out.
const parsed = (headers: string[] | null) => ({
  ...(headers === null ? {} : { headers }),
  column_count: 2,
  row_count: 2,
  preview: [],
  mapping: [],
  measurements: {
    seebeck: {
      temperature_k: [100, 200],
      values: [1e-5, 2e-5],
      points: 2,
      min_temperature_k: 100,
      max_temperature_k: 200,
    },
  },
  errors: [],
  warnings: [{ code: "few_rows" }],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
});

async function open(page: Page, headers: string[] | null = null) {
  await serveModels(page);
  const guesses: unknown[] = [];
  await page.route("**/api/guess", (route) => {
    guesses.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        status: "no_net",
        reason: "temperature_span",
        first_temperature_k: 100,
        last_temperature_k: 200,
        available_ranges: [],
        warnings: [],
      },
    });
  });
  await page.route("**/api/parse", (route) =>
    route.fulfill({ json: parsed(headers) }),
  );
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  return guesses;
}

async function choose(page: Page, name: string) {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from("100 1e-5\n200 2e-5\n"),
    });
}

const question = (page: Page) =>
  page.getByText(
    "This file has no column names. Does its second column hold Seebeck coefficient (S)?",
    { exact: true },
  );
const confirm = (page: Page) =>
  page.getByRole("button", { name: "Yes, it holds S" });
const slot = (page: Page) => page.locator('[data-file-slot="seebeck"]');

test("a file with no header waits for the user, and is not used until then", async ({
  page,
}) => {
  const guesses = await open(page);

  await choose(page, "mine.txt");

  await expect(question(page)).toBeVisible();
  await expect(slot(page)).toContainText("2 points · 100–200 K · V/K");
  await expect(confirm(page)).toBeFocused();
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
  await expect(
    page.getByText("This fit mode needs data for S, ρ."),
  ).toBeVisible();
  await page.waitForTimeout(300);
  expect(guesses).toEqual([]);

  await confirm(page).click();

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page).getByText("mine.txt")).toBeVisible();
  await expect(page.getByText("This fit mode needs data for ρ.")).toBeVisible();
  await expect(page.getByText(/^Fewer than 6 temperatures/)).toBeVisible();
  await expect.poll(() => guesses.length).toBe(1);
  // The file is no longer on its way, so nothing counts it as being read.
  expect(
    await page.evaluate(async () => {
      const path = "/src/session/store.ts";
      const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
        useSessionStore: { getState: () => { fileReads: number } };
      };
      return useSessionStore.getState().fileReads;
    }),
  ).toBe(0);
  await expect(
    page.getByRole("button", { name: "Remove file S" }),
  ).toBeFocused();
});

test("a name that names another quantity says so", async ({ page }) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_rho.txt");

  await expect(question(page)).toBeVisible();
  await expect(page.getByText("Its name suggests Resistivity.")).toBeVisible();
});

test("a name of the slot's own quantity says nothing more", async ({
  page,
}) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_see.txt");

  await expect(question(page)).toBeVisible();
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
});

test("removing it instead leaves the slot empty, and it can take another", async ({
  page,
}) => {
  await open(page);
  await choose(page, "x_rho.txt");
  await expect(question(page)).toBeVisible();

  await page.getByRole("button", { name: "Remove file S" }).click();

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page)).toContainText("Drop a file");
  await choose(page, "mine.txt");
  await expect(question(page)).toBeVisible();
});

test("a file with a header needs no answer", async ({ page }) => {
  await open(page, ["T", "S"]);

  await choose(page, "01_Fe2VAl09Si01_rho.txt");

  await expect(slot(page).getByText("01_Fe2VAl09Si01_rho.txt")).toBeVisible();
  await expect(question(page)).toHaveCount(0);
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
});

test("the demo leaves a file that waits for an answer alone", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
  await choose(page, "mine.txt");
  await expect(question(page)).toBeVisible();
  await expect(page.getByRole("link", { name: "Try demo data" })).toHaveCount(
    0,
  );

  await page.evaluate(() => {
    history.pushState({}, "", "/fit?demo=1");
    dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page).toHaveURL(/\/fit$/);

  await expect(question(page)).toBeVisible();
  await expect(
    page.locator("[data-file-slot]").getByText("Demo data"),
  ).toHaveCount(0);
});

test("a negative resistivity is refused on its line", async ({ page }) => {
  await serveModels(page);
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: {
        ...parsed(["T", "rho"]),
        measurements: {},
        errors: [{ code: "negative_resistivity", line: 3, column: 1 }],
        warnings: [],
      },
    }),
  );
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name: "rho.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T rho\n100 1e-5\n200 -2e-5\n"),
    });

  await expect(page.getByRole("alert")).toContainText(
    "Line 3: A resistivity below 0, which no measurement gives.",
  );
});
