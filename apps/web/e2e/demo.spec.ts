import { expect, test, type Page, type Route } from "@playwright/test";

import { DEMO, MODELS, serveModels } from "./support/models";

const POINTS = String(DEMO.measurements.seebeck?.points);

const PARSED = {
  headers: ["T", "x"],
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

async function upload(page: Page) {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
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

test("the link in the panel loads the demo, and comes back once it is cleared", async ({
  page,
}) => {
  const demos = await open(page, "/fit");
  const link = page.getByRole("link", { name: "Try demo data" });
  await expect(link).toBeVisible();
  expect(demos).toEqual([]);

  await link.click();

  await expect(notice(page)).toBeVisible();
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);
  await expect(page).toHaveURL(/\/fit$/);
  await expect(link).toHaveCount(0);

  await clear(page).click();
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);
  await link.click();
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);
  await expect(radio(page, "S + ρ + R_H")).toBeChecked();
});

test("the link is there only with no files, of either way of loading", async ({
  page,
}) => {
  await open(page, "/fit");
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  const link = page.getByRole("link", { name: "Try demo data" });
  await expect(link).toBeVisible();

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "mine.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(slots(page).getByText("mine.txt")).toBeVisible();
  await expect(link).toHaveCount(0);

  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(link).toHaveCount(0);
});

test("the link from the Single file tab goes to the slots, where interpolating works", async ({
  page,
}) => {
  const parses: unknown[] = [];
  await open(page, "/fit");
  await page.route("**/api/parse", (route) => {
    parses.push(route.request().postDataJSON());
    return route.fulfill({ json: PARSED });
  });
  await page.getByRole("tab", { name: "Single file" }).click();

  await page.getByRole("link", { name: "Try demo data" }).click();

  await expect(
    page.getByRole("tab", { name: "Separate files" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(slots(page).getByText("Demo data")).toHaveCount(3);

  await page.getByRole("switch", { name: /Interpolation/ }).click();
  await expect.poll(() => parses.length).toBe(3);
});

test("Back does not bring back a demo the user cleared", async ({ page }) => {
  const demos = await open(page, "/fit");
  await page.getByRole("link", { name: "Try demo data" }).click();
  await expect(notice(page)).toBeVisible();
  await clear(page).click();
  await expect(notice(page)).toHaveCount(0);
  const asked = demos.length;

  await page.goBack();
  await expect(page).toHaveURL(/\/fit$/);
  await page.waitForTimeout(300);
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);

  await page.goForward();
  await expect(page).toHaveURL(/\/fit$/);
  await page.waitForTimeout(300);
  await expect(slots(page).getByText("Demo data")).toHaveCount(0);
  expect(demos).toHaveLength(asked);
});

test("clearing moves focus to the first slot, for the keyboard", async ({
  page,
}) => {
  await open(page);
  await expect(notice(page)).toBeVisible();

  await clear(page).click();

  await expect(slots(page).first().locator("input")).toBeFocused();

  // Only that once: a later change of the data leaves focus where the user took it.
  const field = page.getByLabel("Lower bound, K");
  await field.focus();
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => { removeData: (quantity: string) => void };
      };
    };
    useSessionStore.getState().removeData("hall");
  });
  await page.waitForTimeout(100);
  await expect(field).toBeFocused();
});

for (const [name, answer, shows] of [
  [
    "that then loads",
    (route: Route) => route.fulfill({ json: PARSED }),
    (page: Page) => slots(page).getByText("mine.txt"),
  ],
  [
    "that then fails",
    (route: Route) =>
      route.fulfill({
        status: 422,
        json: { code: "calculation_failed", message: "x", details: [] },
      }),
    (page: Page) => page.getByRole("alert"),
  ],
] as const) {
  test(`a demo that arrives during a read leaves the file alone, ${name}`, async ({
    page,
  }) => {
    const demoGate = hold();
    const parseGate = hold();
    await open(page, "/fit?demo=1", async (route) => {
      await demoGate.held;
      await route.fulfill({ json: DEMO });
    });
    await page.route("**/api/parse", async (route) => {
      await parseGate.held;
      await answer(route);
    });
    await upload(page);
    await expect(page.getByText("Reading…", { exact: true })).toBeVisible();

    const answered = page.waitForResponse("**/api/demo");
    demoGate.release();
    await answered;
    await expect(page).toHaveURL(/\/fit$/);
    await expect(slots(page).getByText("Demo data")).toHaveCount(0);

    parseGate.release();

    await expect(shows(page)).toBeVisible();
    await expect(slots(page).getByText("Demo data")).toHaveCount(0);
    await expect(notice(page)).toHaveCount(0);
  });
}

test("a demo that arrives during a read of a table leaves it alone", async ({
  page,
}) => {
  const demoGate = hold();
  const parseGate = hold();
  await open(page, "/fit?demo=1", async (route) => {
    await demoGate.held;
    await route.fulfill({ json: DEMO });
  });
  await page.route("**/api/parse", async (route) => {
    await parseGate.held;
    await route.fulfill({ json: PARSED });
  });
  await page.getByRole("tab", { name: "Single file" }).click();
  await upload(page);
  await expect(page.getByText("mine.txt", { exact: true })).toBeVisible();

  const answered = page.waitForResponse("**/api/demo");
  demoGate.release();
  await answered;
  await expect(page).toHaveURL(/\/fit$/);
  parseGate.release();

  await expect(page.getByText(/^S · 2 points/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Single file" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(notice(page)).toHaveCount(0);
});

test("the link goes away during a read, and comes back if the file fails", async ({
  page,
}) => {
  await open(page, "/fit");
  const gate = hold();
  await page.route("**/api/parse", async (route) => {
    await gate.held;
    await route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    });
  });
  const link = page.getByRole("link", { name: "Try demo data" });
  await expect(link).toBeVisible();

  await upload(page);
  await expect(page.getByText("Reading…", { exact: true })).toBeVisible();
  await expect(link).toHaveCount(0);

  // A file that failed left nothing, so the link is on offer again.
  gate.release();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(link).toBeVisible();
});

test("with no model descriptions it says the demo failed, not that it is loading", async ({
  page,
}) => {
  await serveModels(page);
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    }),
  );
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));

  await page.goto("/fit?demo=1");

  await expect(
    page.getByText(/^The demo data could not be loaded/),
  ).toBeVisible();
  await expect(page.getByText("Loading the demo data…")).toHaveCount(0);
  await expect(page).toHaveURL(/demo=1/);
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

test("another screen and back keeps what the user did to the demo", async ({
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
  await expect(page.getByRole("link", { name: "Try demo data" })).toHaveCount(
    0,
  );

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
  await expect(page.getByRole("link", { name: "Try demo data" })).toHaveCount(
    0,
  );
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
