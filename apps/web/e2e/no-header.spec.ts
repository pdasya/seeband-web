import { expect, test, type Page } from "@playwright/test";

import { DEMO, serveModels } from "./support/models";

interface ParseBody {
  text: string;
  expected?: string;
  mapping?: { column: number; role: string }[];
}

const MEASUREMENT = {
  temperature_k: [100, 200],
  values: [1e-5, 2e-5],
  points: 2,
  min_temperature_k: 100,
  max_temperature_k: 200,
};

const answer = (extra: object) => ({
  column_count: 2,
  row_count: 2,
  preview: [
    [100, 1e-5, 7],
    [200, 2e-5, 8],
  ],
  mapping: [],
  measurements: {},
  errors: [],
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
  ...extra,
});

/**
 * As the API answers: with no header it leaves `headers` out, and with a mapping it gives the
 * quantity chosen. `columns` is how many the file has. A text that starts with `T ` has a header.
 */
async function open(page: Page, { columns = 2, errors = [] as object[] } = {}) {
  await serveModels(page);
  const bodies: ParseBody[] = [];
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
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as ParseBody;
    bodies.push(body);
    if (body.text.startsWith("T ")) {
      return route.fulfill({
        json: answer({
          headers: ["T", "x"],
          measurements: { [body.expected ?? "seebeck"]: MEASUREMENT },
        }),
      });
    }
    if (body.mapping === undefined) {
      return route.fulfill({ json: answer({ column_count: columns }) });
    }
    const role = body.mapping.find(({ role: r }) => r !== "temperature")?.role;
    return route.fulfill({
      json: answer({
        column_count: columns,
        errors,
        measurements:
          errors.length > 0 || role === undefined
            ? {}
            : { [role]: MEASUREMENT },
        warnings: [{ code: "few_rows" }],
      }),
    });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  return { bodies, guesses };
}

async function choose(page: Page, name: string, slot = 0, header = false) {
  await page
    .locator('input[type="file"]')
    .nth(slot)
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from(header ? "T x\n100 1\n200 2\n" : "100 1\n200 2\n"),
    });
}

const question = (page: Page) =>
  page.getByText(
    "This file has no column names. Choose what its columns hold.",
    { exact: true },
  );
const role = (page: Page, column: number) =>
  page.getByRole("combobox", {
    name: `Quantity for column Column ${String(column)}`,
  });
const load = (page: Page) => page.getByRole("button", { name: /^Load as / });
const slot = (page: Page, quantity: string) =>
  page.locator(`[data-file-slot="${quantity}"]`);

async function pick(page: Page, column: number, option: string) {
  await role(page, column).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

const fileReads = (page: Page) =>
  page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: { getState: () => { fileReads: number } };
    };
    return useSessionStore.getState().fileReads;
  });

test("two columns come chosen, and wait for one click before any use", async ({
  page,
}) => {
  const { guesses, bodies } = await open(page);

  await choose(page, "mine.txt");

  await expect(question(page)).toBeVisible();
  await expect(slot(page, "seebeck")).toContainText("2 rows · 2 columns");
  await expect(role(page, 1)).toHaveText("T");
  await expect(role(page, 2)).toHaveText("S");
  await expect(role(page, 2)).toBeFocused();
  await expect(load(page)).toHaveText("Load as S");
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
  await expect(
    page.getByText("This fit mode needs data for S, ρ."),
  ).toBeVisible();
  await page.waitForTimeout(300);
  expect(guesses).toEqual([]);

  await load(page).click();

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();
  await expect(page.getByText("This fit mode needs data for ρ.")).toBeVisible();
  await expect(page.getByText(/^Fewer than 6 temperatures/)).toBeVisible();
  await expect.poll(() => guesses.length).toBe(1);
  expect(await fileReads(page)).toBe(0);
  expect(bodies.at(-1)?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 1, role: "seebeck" },
  ]);
  await expect(
    page.getByRole("button", { name: "Remove file S" }),
  ).toBeFocused();
});

test("a name of another quantity says so, and leaves the choice to the user", async ({
  page,
}) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_rho.txt");

  await expect(page.getByText("Its name suggests Resistivity.")).toBeVisible();
  await expect(role(page, 2)).toHaveText("Ignore");
  await expect(load(page)).toBeDisabled();
  await expect(page.getByText("Choose T and one quantity.")).toBeVisible();
});

test("a choice of another quantity puts the file in its slot", async ({
  page,
}) => {
  const { bodies } = await open(page);
  await choose(page, "01_Fe2VAl09Si01_rho.txt");

  await pick(page, 2, "ρ");
  await expect(
    page.getByText("It goes to the slot of Resistivity."),
  ).toBeVisible();
  await load(page).click();

  await expect(
    slot(page, "resistivity").getByText("01_Fe2VAl09Si01_rho.txt"),
  ).toBeVisible();
  await expect(slot(page, "seebeck")).toContainText("Drop a file");
  await expect(question(page)).toHaveCount(0);
  expect(bodies.at(-1)?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 1, role: "resistivity" },
  ]);
  expect(await fileReads(page)).toBe(0);
});

test("a slot that holds a file is not taken, and says so", async ({ page }) => {
  await open(page);
  await choose(page, "theirs.txt", 1, true);
  await expect(slot(page, "resistivity").getByText("theirs.txt")).toBeVisible();

  await choose(page, "x_rho.txt");
  await pick(page, 2, "ρ");
  await load(page).click();

  await expect(
    page.getByText(
      "The slot of Resistivity holds a file. Remove it first, or choose another quantity.",
    ),
  ).toBeVisible();
  await expect(slot(page, "resistivity").getByText("theirs.txt")).toBeVisible();
  await expect(question(page)).toBeVisible();

  // A new choice ends what was said about the last.
  await pick(page, 2, "S");
  await expect(page.getByText(/^The slot of Resistivity holds/)).toHaveCount(0);
});

test("with more columns, only T comes chosen, and the rest is up to the user", async ({
  page,
}) => {
  const { bodies } = await open(page, { columns: 3 });

  await choose(page, "mine.txt");

  await expect(role(page, 1)).toHaveText("T");
  await expect(role(page, 2)).toHaveText("Ignore");
  await expect(role(page, 3)).toHaveText("Ignore");
  await expect(role(page, 2)).toBeFocused();
  await expect(load(page)).toBeDisabled();

  await pick(page, 3, "S");
  await load(page).click();

  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();
  expect(bodies.at(-1)?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 2, role: "seebeck" },
  ]);
});

test("two quantities, or none, cannot be loaded", async ({ page }) => {
  await open(page, { columns: 3 });
  await choose(page, "mine.txt");

  await pick(page, 2, "S");
  await pick(page, 3, "ρ");
  await expect(load(page)).toBeDisabled();
  await expect(page.getByText("Choose T and one quantity.")).toBeVisible();

  await pick(page, 1, "Ignore");
  await pick(page, 3, "Ignore");
  await expect(load(page)).toBeDisabled();
});

test("what the server finds wrong with a choice shows, and the file waits", async ({
  page,
}) => {
  await open(page, {
    errors: [{ code: "negative_resistivity", line: 2, column: 1 }],
  });
  await choose(page, "x.txt");
  await pick(page, 2, "ρ");

  await load(page).click();

  await expect(page.getByRole("alert")).toContainText(
    "Line 2: A resistivity below 0, which no measurement gives.",
  );
  await expect(question(page)).toBeVisible();
  await expect(load(page)).toBeEnabled();
  await expect(slot(page, "resistivity")).toContainText("Drop a file");
});

test("a name of the slot's own quantity says nothing more", async ({
  page,
}) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_see.txt");

  await expect(question(page)).toBeVisible();
  await expect(role(page, 2)).toHaveText("S");
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
});

test("removing it instead leaves the slot empty, and counts no read", async ({
  page,
}) => {
  await open(page);
  await choose(page, "x_rho.txt");
  await expect(question(page)).toBeVisible();

  await page.getByRole("button", { name: "Remove file S" }).click();

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page, "seebeck")).toContainText("Drop a file");
  expect(await fileReads(page)).toBe(0);
});

test("a file with a header needs no choice", async ({ page }) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_rho.txt", 0, true);

  await expect(
    slot(page, "seebeck").getByText("01_Fe2VAl09Si01_rho.txt"),
  ).toBeVisible();
  await expect(question(page)).toHaveCount(0);
});

test("the demo leaves a file that waits for a choice alone", async ({
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

test("a negative resistivity in a file with a header is refused on its line", async ({
  page,
}) => {
  await serveModels(page);
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: answer({
        headers: ["T", "rho"],
        errors: [{ code: "negative_resistivity", line: 3, column: 1 }],
      }),
    }),
  );
  await page.goto("/fit");
  await choose(page, "rho.txt", 1, true);

  await expect(page.getByRole("alert")).toContainText(
    "Line 3: A resistivity below 0, which no measurement gives.",
  );
});
