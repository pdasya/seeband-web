import { expect, test, type Page, type Route } from "@playwright/test";

import { DEMO, MODELS, serveModels } from "./support/models";

const POINTS = String(DEMO.measurements.seebeck?.points);

const PARSED = {
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
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
};

function hold() {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release: () => release() };
}

async function open(
  page: Page,
  address = "/fit?demo=1",
  answer: (route: Route) => Promise<void> = (route) =>
    route.fulfill({ json: DEMO }),
) {
  await serveModels(page);
  const demos: string[] = [];
  await page.route("**/api/demo", (route) => {
    demos.push(route.request().url());
    return answer(route);
  });
  await page.goto(address);
  return demos;
}

const notice = (page: Page) => page.getByText(/^Synthetic data/);
const clear = (page: Page) =>
  page.getByRole("button", { name: "Clear demo data" });
const slots = (page: Page) => page.locator("[data-file-slot]");
const radio = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true });

test("the link opens the fit with all the demo's data, labelled as synthetic", async ({
  page,
}) => {
  await open(page);

  await expect(notice(page)).toBeVisible();
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);
  await expect(page.getByText(new RegExp(`^${POINTS} points`))).toHaveCount(3);
  await expect(page).toHaveURL(/\/fit$/);
});

test("it opens the fit the demo was made for", async ({ page }) => {
  await open(page);
  await expect(notice(page)).toBeVisible();

  await expect(radio(page, "DPB")).toBeChecked();
  await expect(radio(page, "S + ρ + R_H")).toBeChecked();
  await expect(
    page.getByRole("combobox", { name: "Scattering" }),
  ).toContainText("acPh");
  await expect(page.getByLabel("Lower bound, K")).toHaveValue("50");
  await expect(page.getByRole("button", { name: "Run fit" })).toBeEnabled();
});

test("a demo that comes before the model descriptions still opens its fit", async ({
  page,
}) => {
  await serveModels(page);
  const gate = hold();
  await page.route("**/api/models", async (route) => {
    await gate.held;
    await route.fulfill({ json: MODELS });
  });
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
  const answered = page.waitForResponse("**/api/demo");
  await page.goto("/fit?demo=1");
  await answered;

  gate.release();

  await expect(notice(page)).toBeVisible();
  await expect(radio(page, "S + ρ + R_H")).toBeChecked();
});

test("the chart says its points are demo data", async ({ page }) => {
  await open(page);

  await expect(page.getByText("Measurements (demo)")).toBeVisible();
});

test("a fit screen with no link asks for no demo", async ({ page }) => {
  const demos = await open(page, "/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();

  await page.waitForTimeout(200);

  expect(demos).toEqual([]);
  await expect(notice(page)).toHaveCount(0);
  await expect(page.getByText("Measurements (demo)")).toHaveCount(0);
});

test("clearing takes the demo away, and a user's own file goes in its place", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await expect(notice(page)).toBeVisible();

  await clear(page).click();

  await expect(notice(page)).toHaveCount(0);
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(slots(page).getByText("mine.txt")).toBeVisible();
  await expect(notice(page)).toHaveCount(0);
  await expect(page.getByText("Measurements (demo)")).toHaveCount(0);
  await expect(page.getByText("Measurements", { exact: true })).toBeVisible();
});

test("the notice stays while any demo data remain, and clearing keeps a user's file", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await expect(notice(page)).toBeVisible();

  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  await expect(slots(page).getByText("Demo data")).toHaveCount(2);
  await expect(notice(page)).toBeVisible();

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(slots(page).getByText("mine.txt")).toBeVisible();
  // S is the user's now, so its points are not called demo data.
  await expect(page.getByText("Measurements (demo)")).toHaveCount(0);
  await expect(notice(page)).toBeVisible();

  await clear(page).click();

  await expect(slots(page).getByText("mine.txt")).toBeVisible();
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);
  await expect(notice(page)).toHaveCount(0);
});

test("the notice comes back with the data, after the other way of loading", async ({
  page,
}) => {
  await open(page);
  await expect(notice(page)).toBeVisible();

  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(notice(page)).toHaveCount(0);

  await page.getByRole("tab", { name: "Separate files" }).click();
  await expect(notice(page)).toBeVisible();
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);
});

test("coming back to the screen keeps what the user did to the demo", async ({
  page,
}) => {
  const demos = await open(page);
  await expect(notice(page)).toBeVisible();
  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  const asked = demos.length;

  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();
  await expect(notice(page)).toBeVisible();

  await expect(slots(page).getByText("Demo data")).toHaveCount(2);
  await page.waitForTimeout(200);
  expect(demos).toHaveLength(asked);
});

test("it says it is loading, and a user's file that comes first stays", async ({
  page,
}) => {
  const gate = hold();
  await open(page, "/fit?demo=1", async (route) => {
    await gate.held;
    await route.fulfill({ json: DEMO });
  });
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await expect(page.getByText("Loading the demo data…")).toBeVisible();

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(slots(page).getByText("mine.txt")).toBeVisible();

  const answered = page.waitForResponse("**/api/demo");
  gate.release();
  await answered;

  await expect(page).toHaveURL(/\/fit$/);
  await expect(page.getByText("Loading the demo data…")).toHaveCount(0);
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);
  await expect(notice(page)).toHaveCount(0);
  await expect(slots(page).getByText("mine.txt")).toBeVisible();
});

test("a failure says so, a reload tries again, and own data end the message", async ({
  page,
}) => {
  let failing = true;
  await open(page, "/fit?demo=1", (route) =>
    failing
      ? route.fulfill({
          status: 422,
          json: { code: "calculation_failed", message: "SECRET", details: [] },
        })
      : route.fulfill({ json: DEMO }),
  );
  const message = page.getByText(/^The demo data could not be loaded/);
  await expect(message).toBeVisible();
  await expect(page.getByText("Loading the demo data…")).toHaveCount(0);
  await expect(page.getByText("SECRET")).toHaveCount(0);
  await expect(page).toHaveURL(/demo=1/);

  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(slots(page).getByText("mine.txt")).toBeVisible();
  await expect(message).toHaveCount(0);

  failing = false;
  page.on("dialog", (dialog) => void dialog.accept());
  await page.evaluate(() => {
    location.reload();
  });
  await expect(notice(page)).toBeVisible();
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);
});

test("its data take the same paths as a file: guess, curve and interpolation", async ({
  page,
}) => {
  const guesses: unknown[] = [];
  const parses: { text: string; expected: string }[] = [];
  await serveModels(page);
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
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
    parses.push(
      route.request().postDataJSON() as { text: string; expected: string },
    );
    return route.fulfill({ json: PARSED });
  });

  await page.goto("/fit?demo=1");
  await expect(notice(page)).toBeVisible();
  await expect.poll(() => guesses.length).toBe(1);
  // Loading it is no parse: only interpolating sends its text again.
  expect(parses).toEqual([]);

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect.poll(() => parses.length).toBe(3);
  expect(parses.map(({ expected }) => expected).sort()).toEqual([
    "hall",
    "resistivity",
    "seebeck",
  ]);
  const lines = parses[0]?.text.split("\n") ?? [];
  expect(lines).toHaveLength(Number(POINTS));
  expect(lines[0]).toMatch(/^\S+ \S+$/);
});
