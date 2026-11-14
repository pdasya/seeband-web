import { expect, test, type Page, type Route } from "@playwright/test";

import { fitBadges } from "./support/fitScreen";
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
  preview_si: [
    [100, null, null],
    [200, null, null],
  ],
  mapping: [],
  measurements: {},
  errors: [],
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
  interpolation_failure_reasons: {},
  ...extra,
});

interface Stub {
  columns?: number;
  /** Of the read with a mapping. */
  errors?: object[];
  /** Of the first read, with no mapping. */
  firstErrors?: object[];
  firstWarnings?: object[];
  /** Holds or fails the read with a mapping. */
  apply?: (route: Route) => Promise<boolean>;
}

/**
 * As the API answers: with no header it leaves `headers` out, and with a mapping it gives the
 * quantity chosen. A text that starts with `T ` has a header.
 */
async function open(
  page: Page,
  {
    columns = 2,
    errors = [],
    firstErrors = [],
    firstWarnings = [],
    apply,
  }: Stub = {},
) {
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
  await page.route("**/api/parse", async (route) => {
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
      return route.fulfill({
        json: answer({
          column_count: columns,
          errors: firstErrors,
          warnings: firstWarnings,
        }),
      });
    }
    if (apply !== undefined && !(await apply(route))) {
      return undefined;
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

function hold() {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release: () => release() };
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
const hint = (page: Page) => page.getByText(/^Choose the column that holds /);
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
      useSessionStore: { getState: () => { slotsReading: string[] } };
    };
    return useSessionStore.getState().slotsReading.length;
  });

test("only T comes chosen, and the file waits for its quantity before any use", async ({
  page,
}) => {
  const { guesses, bodies } = await open(page);

  await choose(page, "mine.txt");

  await expect(question(page)).toBeVisible();
  await expect(slot(page, "seebeck")).toContainText("2 rows · 2 columns");
  await expect(role(page, 1)).toHaveText("T");
  await expect(role(page, 2)).toHaveText("Ignore");
  await expect(role(page, 2)).toBeFocused();
  await expect(hint(page)).toHaveText(
    "Choose the column that holds S, or another quantity. The file loads once T and one quantity are chosen.",
  );
  await expect(page.getByText(/^Its name suggests/)).toHaveCount(0);
  await expect(fitBadges(page)).toHaveText("Missing data: S, ρ");
  await page.waitForTimeout(300);
  expect(guesses).toEqual([]);
  expect(bodies).toHaveLength(1);

  await pick(page, 2, "S");

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();
  await expect(fitBadges(page)).toHaveText("Missing data: ρ");
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
  await expect(hint(page)).toBeVisible();
});

test("a choice of another quantity puts the file in its slot", async ({
  page,
}) => {
  const { bodies } = await open(page);
  await choose(page, "01_Fe2VAl09Si01_rho.txt");

  await pick(page, 2, "ρ");

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

  await expect(
    page.getByText(
      "The slot of Resistivity holds a file. Remove it first, or choose another quantity.",
    ),
  ).toBeVisible();
  await expect(slot(page, "resistivity").getByText("theirs.txt")).toBeVisible();
  await expect(question(page)).toBeVisible();

  // A new choice ends what was said about the last, and loads the file where it can go.
  await pick(page, 2, "S");
  await expect(page.getByText(/^The slot of Resistivity holds/)).toHaveCount(0);
  await expect(slot(page, "seebeck").getByText("x_rho.txt")).toBeVisible();
});

test("Try again reads the choice once the full slot is emptied", async ({
  page,
}) => {
  const { bodies } = await open(page);
  await choose(page, "theirs.txt", 1, true);
  await expect(slot(page, "resistivity").getByText("theirs.txt")).toBeVisible();
  await choose(page, "x_rho.txt");
  await pick(page, 2, "ρ");
  await expect(page.getByText(/^The slot of Resistivity holds/)).toBeVisible();
  const reads = bodies.length;

  await page.getByRole("button", { name: "Remove file ρ" }).click();
  await page.getByRole("button", { name: "Try again" }).click();

  await expect(slot(page, "resistivity").getByText("x_rho.txt")).toBeVisible();
  await expect(question(page)).toHaveCount(0);
  expect(bodies).toHaveLength(reads + 1);
});

test("a unit chosen after a problem reads the choice again", async ({
  page,
}) => {
  let reads = 0;
  const { bodies } = await open(page, {
    apply: async (route) => {
      reads += 1;
      if (reads > 1) {
        return true;
      }
      await route.fulfill({
        json: answer({
          errors: [{ code: "non_positive_temperature", line: 1, column: 0 }],
        }),
      });
      return false;
    },
  });
  await choose(page, "mine.txt");
  await pick(page, 2, "S");
  await expect(page.getByRole("alert")).toContainText("Line 1:");

  await page.getByRole("combobox", { name: "Unit of Column 1" }).click();
  await page.getByRole("option", { name: "°C", exact: true }).click();

  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();
  expect(bodies.at(-1)?.mapping).toEqual([
    { column: 0, role: "temperature", unit: "C" },
    { column: 1, role: "seebeck" },
  ]);
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
  await expect(hint(page)).toBeVisible();

  await pick(page, 3, "S");

  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();
  expect(bodies.at(-1)?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 2, role: "seebeck" },
  ]);
});

test("a quantity with no T, or two quantities, load nothing", async ({
  page,
}) => {
  const { bodies } = await open(page, { columns: 3 });
  await choose(page, "mine.txt");

  await pick(page, 1, "Ignore");
  await pick(page, 2, "S");
  await pick(page, 3, "ρ");
  await pick(page, 1, "T");

  await expect(question(page)).toBeVisible();
  await expect(hint(page)).toBeVisible();
  await page.waitForTimeout(300);
  expect(bodies).toHaveLength(1);
  expect(await fileReads(page)).toBe(1);
});

test("what the server finds wrong with a choice shows, and the file waits", async ({
  page,
}) => {
  await open(page, {
    errors: [{ code: "negative_resistivity", line: 2, column: 1 }],
  });
  await choose(page, "x.txt");
  await pick(page, 2, "ρ");

  await expect(page.getByRole("alert")).toContainText(
    "Line 2: A resistivity below 0, which no measurement gives.",
  );
  await expect(question(page)).toBeVisible();
  await expect(role(page, 2)).toBeEnabled();
  await expect(slot(page, "resistivity")).toContainText("Drop a file");
});

test("a name of the slot's own quantity says nothing more", async ({
  page,
}) => {
  await open(page);

  await choose(page, "01_Fe2VAl09Si01_see.txt");

  await expect(question(page)).toBeVisible();
  await expect(role(page, 2)).toHaveText("Ignore");
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

test("interpolating sends the chosen columns again, not a guess", async ({
  page,
}) => {
  const { bodies } = await open(page, { columns: 3 });
  await choose(page, "mine.txt");
  await pick(page, 3, "S");
  await expect(slot(page, "seebeck").getByText("mine.txt")).toBeVisible();

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect.poll(() => bodies.at(-1)?.text).toBeDefined();
  await expect
    .poll(() => bodies.find((body) => "interpolate" in body))
    .toBeTruthy();
  const sent = bodies.find((body) => "interpolate" in body);
  expect(sent?.mapping).toEqual([
    { column: 0, role: "temperature" },
    { column: 2, role: "seebeck" },
  ]);
  expect(sent?.expected).toBeUndefined();
});

test("a file with a header interpolates as before, by its quantity", async ({
  page,
}) => {
  const { bodies } = await open(page);
  await choose(page, "theirs.txt", 0, true);
  await expect(slot(page, "seebeck").getByText("theirs.txt")).toBeVisible();

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect
    .poll(() => bodies.find((body) => "interpolate" in body))
    .toBeTruthy();
  const sent = bodies.find((body) => "interpolate" in body);
  expect(sent?.expected).toBe("seebeck");
  expect(sent?.mapping).toBeUndefined();
});

test("a slot whose own file waits for a choice is not taken", async ({
  page,
}) => {
  await open(page);
  await choose(page, "b.txt", 1);
  await expect(role(page, 1)).toBeVisible();

  await choose(page, "x_rho.txt");
  await page
    .locator('[data-file-slot="seebeck"]')
    .getByRole("combobox", { name: "Quantity for column Column 2" })
    .click();
  await page.getByRole("option", { name: "ρ", exact: true }).click();

  await expect(
    page.getByText(
      "The slot of Resistivity has a file on its way. Finish there first, or choose another quantity.",
    ),
  ).toBeVisible();
  await expect(slot(page, "resistivity")).toContainText("b.txt");
  expect(await fileReads(page)).toBe(2);

  // Ending one choice leaves the other slot's file on its way.
  await page.getByRole("button", { name: "Remove file S" }).click();
  expect(await fileReads(page)).toBe(1);
  await expect(page.getByRole("link", { name: "Try demo data" })).toHaveCount(
    0,
  );
});

test("values below 0 in the ρ slot leave the choice open, and S can take them", async ({
  page,
}) => {
  await open(page, {
    firstErrors: [{ code: "negative_resistivity", line: 1, column: 1 }],
  });

  await choose(page, "n_type.txt", 1);

  await expect(
    page.getByText("Some values are below 0, which a resistivity cannot have."),
  ).toBeVisible();
  await expect(role(page, 2)).toHaveText("Ignore");
  await expect(page.getByRole("alert")).toHaveCount(0);

  await pick(page, 2, "S");

  await expect(slot(page, "seebeck").getByText("n_type.txt")).toBeVisible();
  await expect(slot(page, "resistivity")).toContainText("Drop a file");
});

test("a header that does not fit says so, and its warning stays after the choice", async ({
  page,
}) => {
  await open(page, { firstWarnings: [{ code: "header_mismatch" }] });

  await choose(page, "mine.txt");

  await expect(
    page.getByText(
      "The column names of this file do not match its columns. Choose what its columns hold.",
    ),
  ).toBeVisible();
  await expect(question(page)).toHaveCount(0);
  await pick(page, 2, "S");
  await expect(
    page.getByText("The header has a different number of columns."),
  ).toBeVisible();
});

test("the choice cannot change while it is read, and a removal then ends it", async ({
  page,
}) => {
  const gate = hold();
  await open(page, {
    apply: async () => {
      await gate.held;
      return true;
    },
  });
  await choose(page, "mine.txt");

  await pick(page, 2, "S");
  await expect(role(page, 2)).toBeDisabled();
  await expect(role(page, 1)).toBeDisabled();

  await page.getByRole("button", { name: "Remove file S" }).click();
  gate.release();
  await page.waitForTimeout(300);

  await expect(slot(page, "seebeck")).toContainText("Drop a file");
  await expect(fitBadges(page)).toHaveText("Missing data: S, ρ");
  expect(await fileReads(page)).toBe(0);
});

test("a lost connection while the choice is read says so, and the file waits", async ({
  page,
}) => {
  await open(page, {
    apply: async (route) => {
      await route.abort();
      return false;
    },
  });
  await choose(page, "mine.txt");

  await pick(page, 2, "S");

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(question(page)).toBeVisible();
  await expect(role(page, 2)).toBeEnabled();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  expect(await fileReads(page)).toBe(1);
});

test("a switch of the way of loading ends a choice, and counts no read", async ({
  page,
}) => {
  await open(page);
  await choose(page, "mine.txt");
  await expect(question(page)).toBeVisible();

  await page.getByRole("tab", { name: "Single file" }).click();
  await page.getByRole("tab", { name: "Separate files" }).click();

  await expect(question(page)).toHaveCount(0);
  await expect(slot(page, "seebeck")).toContainText("Drop a file");
  expect(await fileReads(page)).toBe(0);
});
