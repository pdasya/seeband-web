import { expect, test, type Page, type Route } from "@playwright/test";

const MEASUREMENT = {
  temperature_k: [100, 200, 300],
  values: [1e-4, 2e-4, 3e-4],
  points: 3,
  min_temperature_k: 100,
  max_temperature_k: 300,
};
const INTERPOLATED = {
  temperature_k: [50, 425, 800],
  values: [1, 2, 3],
  extrapolated: false,
  measured_points_in_range: 3,
  underdetermined: false,
};

interface Body {
  text: string;
  expected?: string;
  interpolate?: { min_temperature_k: number; max_temperature_k: number };
  mapping?: unknown[];
}

function parsed(overrides: object = {}) {
  return {
    headers: ["T", "S"],
    column_count: 2,
    row_count: 3,
    preview: [],
    mapping: [
      { column: 0, role: "temperature" },
      { column: 1, role: "seebeck" },
    ],
    measurements: { seebeck: MEASUREMENT },
    errors: [],
    warnings: [],
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    ...overrides,
  };
}

// The summary also appears in a hidden status for a screen reader, so this looks at the cards.
const slots = (page: Page) => page.locator("[data-file-slot]");

async function setUp(
  page: Page,
  answer: (body: Body, route: Route) => Promise<void> | void,
) {
  const bodies: Body[] = [];
  await page.route("**/api/models", (route) =>
    route.fulfill({
      json: {
        models: [
          { default_min_temperature_k: 50, default_max_temperature_k: 800 },
        ],
      },
    }),
  );
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as Body;
    bodies.push(body);
    return answer(body, route);
  });
  await page.goto("/fit");
  return bodies;
}

async function loadSeebeck(page: Page, name = "s.txt") {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name,
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1e-4\n"),
    });
  await expect(
    slots(page).getByText("3 points · 100–300 K · V/K"),
  ).toBeVisible();
}

const interpolationSwitch = (page: Page) =>
  page.getByRole("switch", { name: /Interpolation/ });

test("turning it on asks for the default fit range, and off asks nothing", async ({
  page,
}) => {
  const bodies = await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : { interpolated: { seebeck: INTERPOLATED } },
      ),
    }),
  );
  await loadSeebeck(page);

  await interpolationSwitch(page).click();

  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[1]).toEqual({
    text: "T S\n100 1e-4\n",
    expected: "seebeck",
    interpolate: { min_temperature_k: 50, max_temperature_k: 800 },
  });

  await interpolationSwitch(page).click();
  await expect(page.getByText("Fit range 50–800 K")).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(bodies).toHaveLength(2);
  await expect(
    slots(page).getByText("3 points · 100–300 K · V/K"),
  ).toBeVisible();
});

test("with no data, it asks nothing, and a new file is interpolated", async ({
  page,
}) => {
  const bodies = await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : { interpolated: { seebeck: INTERPOLATED } },
      ),
    }),
  );

  await interpolationSwitch(page).click();
  await page.waitForTimeout(500);
  expect(bodies).toEqual([]);

  await loadSeebeck(page);

  await expect
    .poll(() => bodies.filter((body) => body.interpolate !== undefined).length)
    .toBe(1);
});

test("each flag is shown for its quantity", async ({ page }) => {
  await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : {
              interpolated: {
                seebeck: {
                  ...INTERPOLATED,
                  extrapolated: true,
                  underdetermined: true,
                },
              },
            },
      ),
    }),
  );
  await loadSeebeck(page);

  await interpolationSwitch(page).click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("S: the grid goes beyond the data");
  await expect(alert).toContainText("S: too few points set the polynomial");

  await interpolationSwitch(page).click();
  await expect(alert).toHaveCount(0);
});

test("no measured point in range says that every value is made up", async ({
  page,
}) => {
  await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : {
              interpolated: {
                seebeck: {
                  ...INTERPOLATED,
                  extrapolated: true,
                  measured_points_in_range: 0,
                },
              },
            },
      ),
    }),
  );
  await loadSeebeck(page);

  await interpolationSwitch(page).click();

  await expect(page.getByRole("alert")).toContainText("every value is made up");
  await expect(page.getByRole("alert")).not.toContainText("some values");
});

test("a quantity that fails or overflows is named", async ({ page }) => {
  await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : {
              interpolated: {
                seebeck: { ...INTERPOLATED, values: [1, null, 3] },
              },
              interpolation_failed: ["seebeck"],
            },
      ),
    }),
  );
  await loadSeebeck(page);

  await interpolationSwitch(page).click();

  await expect(page.getByRole("alert")).toContainText(
    "S: could not be interpolated",
  );
});

test("a range it cannot use, and a server that is down, have their messages", async ({
  page,
}) => {
  let down = false;
  await setUp(page, (body, route) => {
    if (body.interpolate === undefined) {
      return route.fulfill({ json: parsed() });
    }
    return down
      ? route.fulfill({ status: 502, contentType: "text/plain", body: "" })
      : route.fulfill({
          status: 422,
          json: {
            code: "invalid_parse_request",
            message: "x",
            details: [
              {
                location: ["body", "interpolate"],
                code: "invalid_interpolation_range",
                message: "SECRET-VALUE",
              },
            ],
          },
        });
  });
  await loadSeebeck(page);

  await interpolationSwitch(page).click();

  const refusal = page
    .getByRole("alert")
    .filter({ hasText: "span 20 to 200000 K" });
  await expect(refusal).toBeVisible();
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);

  down = true;
  await interpolationSwitch(page).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await interpolationSwitch(page).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "server is not responding" }),
  ).toBeVisible();
});

test("a single file asks once, with its mapping", async ({ page }) => {
  const bodies = await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : { interpolated: { seebeck: INTERPOLATED } },
      ),
    }),
  );
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T,S\n100,1e-4\n"),
  });
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await interpolationSwitch(page).click();

  await expect
    .poll(() => bodies.filter((body) => body.interpolate !== undefined))
    .toEqual([
      {
        text: "T,S\n100,1e-4\n",
        mapping: parsed().mapping,
        interpolate: { min_temperature_k: 50, max_temperature_k: 800 },
      },
    ]);
});

test("with no fit range to use, it says so", async ({ page }) => {
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 500,
      json: { code: "x", message: "x", details: [] },
    }),
  );
  await page.goto("/fit");

  await interpolationSwitch(page).click();

  await expect(page.getByText("The fit range is not known yet.")).toBeVisible();
});

test("removing a file during the wait does not leave the panel waiting", async ({
  page,
}) => {
  await setUp(page, async (body, route) => {
    if (body.interpolate === undefined) {
      return route.fulfill({ json: parsed() });
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return route.fulfill({
      json: parsed({ interpolated: { seebeck: INTERPOLATED } }),
    });
  });
  await loadSeebeck(page);
  await interpolationSwitch(page).click();
  await expect(page.getByText("Interpolating…")).toBeVisible();

  await page.getByRole("button", { name: "Remove file S" }).click();

  await expect(page.getByText("Interpolating…")).toHaveCount(0);
  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
});

test("one file failing names it, and leaves the other's flags", async ({
  page,
}) => {
  await setUp(page, (body, route) => {
    if (body.interpolate === undefined) {
      return route.fulfill({ json: parsed() });
    }
    return body.expected === "hall"
      ? route.fulfill({
          status: 429,
          headers: { "Retry-After": "5" },
          json: { code: "rate_limited", message: "x", details: [] },
        })
      : route.fulfill({
          json: parsed({
            interpolated: {
              seebeck: { ...INTERPOLATED, extrapolated: true },
            },
          }),
        });
  });
  await loadSeebeck(page);
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as Body;
    return body.interpolate === undefined
      ? route.fulfill({
          json: parsed({ measurements: { hall: MEASUREMENT } }),
        })
      : route.fallback();
  });
  await page
    .locator('input[type="file"]')
    .last()
    .setInputFiles({
      name: "h.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T R_H\n100 1e-7\n"),
    });
  await expect(slots(page).getByText("h.txt")).toBeVisible();

  await interpolationSwitch(page).click();

  const alerts = page.getByRole("alert");
  await expect(alerts.filter({ hasText: "Too many files" })).toBeVisible();
  const flags = alerts.filter({ hasText: "R_H:" });
  await expect(flags).toContainText("R_H: could not be interpolated");
  await expect(flags).toContainText("S: the grid goes beyond the data");
});

test("moving between screens sends nothing again, and it follows while away", async ({
  page,
}) => {
  const bodies = await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : { interpolated: { seebeck: INTERPOLATED } },
      ),
    }),
  );
  await loadSeebeck(page);
  await interpolationSwitch(page).click();
  await expect.poll(() => bodies.length).toBe(2);

  await page.getByRole("link", { name: "Results" }).click();
  await page.getByRole("link", { name: "Model fit" }).click();
  await expect(interpolationSwitch(page)).toBeChecked();
  await page.waitForTimeout(600);

  expect(bodies).toHaveLength(2);
});

test("a table with no data sends no request for values it cannot have", async ({
  page,
}) => {
  const bodies = await setUp(page, (body, route) =>
    route.fulfill({
      json:
        body.mapping === undefined
          ? parsed()
          : parsed({
              mapping: body.mapping,
              measurements: {},
              errors: [{ code: "missing_temperature" }],
            }),
    }),
  );
  await page.getByRole("tab", { name: "Single file" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from("T,S\n100,1e-4\n"),
  });
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "Ignore", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Check the mapping.");

  await interpolationSwitch(page).click();
  await page.waitForTimeout(600);

  expect(bodies.filter((body) => body.interpolate !== undefined)).toEqual([]);
  await expect(page.getByText("Interpolating…")).toHaveCount(0);
});

test("the switch stays when moving to another screen and back", async ({
  page,
}) => {
  await setUp(page, (body, route) =>
    route.fulfill({
      json: parsed(
        body.interpolate === undefined
          ? {}
          : { interpolated: { seebeck: INTERPOLATED } },
      ),
    }),
  );
  await loadSeebeck(page);
  await interpolationSwitch(page).click();
  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();

  await page.getByRole("link", { name: "Results" }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(interpolationSwitch(page)).toBeChecked();
  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
});
