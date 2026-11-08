import { expect, test, type Page } from "@playwright/test";

import { fitBadges } from "./support/fitScreen";
import { fakeFit } from "./support/fakeFit";
import { MODELS, serveModels } from "./support/models";

interface ModelsForTest {
  models: {
    fit_modes: {
      parameters: {
        name: string;
        bounds_editable: boolean;
        fit_scale: number;
        fit_bounds?: { lower: number; upper: number };
      }[];
    }[];
  }[];
}

const PARSED = (quantity: string) => ({
  headers: ["T", "x"],
  column_count: 2,
  row_count: 2,
  preview: [],
  mapping: [],
  measurements: {
    [quantity]: {
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
});

const RESULT = {
  parameters: { band_gap: 900 },
  status: "converged",
  iterations: 5,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};

/** DPB S + ρ with its data, with E_g starting at 1000 K, shown as 0,09 eV. */
async function open(page: Page) {
  await fakeFit(page);
  await serveModels(page);
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  for (const filled of [0, 1]) {
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles({
        name: `f${String(filled)}.txt`,
        mimeType: "text/plain",
        buffer: Buffer.from("T x\n100 1\n"),
      });
    await expect(page.getByText(/^2 points/)).toHaveCount(filled + 1);
  }
  await expect(run(page)).toBeEnabled();
}

const run = (page: Page) => page.getByRole("button", { name: "Run fit" });
const stop = (page: Page) => page.getByRole("button", { name: "Stop" });
const lower = (page: Page, symbol: string) =>
  page.getByRole("textbox", { name: `${symbol}, lower bound`, exact: true });
const upper = (page: Page, symbol: string) =>
  page.getByRole("textbox", { name: `${symbol}, upper bound`, exact: true });
const value = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const slider = (page: Page, name: string) =>
  page.getByRole("slider", { name, exact: true });
const defaults = (page: Page) =>
  page.getByRole("button", { name: "Default bounds" });
const row = (page: Page, symbol: string) =>
  page
    .getByRole("table", { name: "Parameters in use" })
    .getByRole("row")
    .filter({
      has: page.getByRole("cell", {
        name: new RegExp(`^${symbol}(?: at bound)?$`),
      }),
    });
const fitBodies = (page: Page) => page.evaluate(() => window.fitTest.bodies);
const send = (page: Page, event: object) =>
  page.evaluate((item) => {
    window.fitTest.send(item);
  }, event);

const editor = (page: Page) => page.getByRole("dialog");
const openEditor = (page: Page) =>
  page.getByRole("button", { name: "Edit bounds" }).click();
const done = (page: Page) => page.getByRole("button", { name: "Done" }).click();

/** Through the dialog, as the screen behind it is closed to the keyboard and to these queries. */
async function setBounds(
  page: Page,
  symbol: string,
  low: string,
  high: string,
) {
  await openEditor(page);
  await lower(page, symbol).fill(low);
  await upper(page, symbol).fill(high);
  await done(page);
  await expect(editor(page)).toHaveCount(0);
}

test("the button is beside the title, and the bounds open in a dialog", async ({
  page,
}) => {
  await open(page);
  const heading = await page
    .getByRole("heading", { name: "Parameters" })
    .boundingBox();
  const button = await page
    .getByRole("button", { name: "Edit bounds" })
    .boundingBox();
  expect(button?.y).toBeLessThanOrEqual(
    (heading?.y ?? 0) + (heading?.height ?? 0),
  );
  // A gear, which says what it does on hover.
  const gear = page.getByRole("button", { name: "Edit bounds" });
  await expect(gear).toHaveText("");
  await gear.hover();
  await expect(page.getByRole("tooltip")).toHaveText("Edit bounds");
  expect((button?.y ?? 0) + (button?.height ?? 0)).toBeGreaterThanOrEqual(
    heading?.y ?? Infinity,
  );
  await expect(editor(page)).toHaveCount(0);

  await openEditor(page);

  await expect(
    editor(page).getByRole("heading", { name: "Bounds of the fit" }),
  ).toBeVisible();
  // ±3000 K, in eV.
  await expect(lower(page, "E_g")).toHaveValue("-0,26");
  await expect(upper(page, "E_g")).toHaveValue("0,26");
  await expect(lower(page, "m₂/m₁")).toHaveValue("-3");
  await expect(lower(page, "B")).toHaveValue("0,9");
  await expect(lower(page, "F")).toHaveCount(0);

  await done(page);
  await expect(editor(page)).toHaveCount(0);
  await expect(gear).toBeFocused();
  // Focus coming back does not name the gear again, and a pointer on it still does.
  await page.waitForTimeout(300);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await gear.hover();
  await expect(page.getByRole("tooltip")).toHaveText("Edit bounds");
});

test("Escape closes the dialog, and drops what was being typed", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);
  await lower(page, "E_g").fill("0,04");

  await lower(page, "E_g").press("Escape");

  await expect(editor(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Edit bounds" })).toBeFocused();
  await page.waitForTimeout(300);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,26");
  await openEditor(page);
  await expect(lower(page, "E_g")).toHaveValue("-0,26");
});

test("a fit sends only the bounds changed, in core units", async ({ page }) => {
  await open(page);

  await setBounds(page, "E_g", "0,04", "0,13");
  await setBounds(page, "B", "0,95", "1.05");
  await run(page).click();

  const bodies = await fitBodies(page);
  expect(bodies[0]?.bounds).toEqual({
    // 0,04 and 0,13 eV.
    band_gap: { lower: 464.18072487, upper: 1508.58735583 },
    B: { lower: 0.95, upper: 1.05 },
  });
});

test("the result table shows them, and the slider and field follow them", async ({
  page,
}) => {
  await open(page);

  await setBounds(page, "E_g", "0,04", "0,35");

  await expect(row(page, "E_g")).toContainText("0,04 … 0,35");
  // Each bound goes to K and back, so it is 0,35 eV to within the last digits.
  const end = async (name: string) =>
    Number(await slider(page, "E_g").getAttribute(name));
  expect(await end("aria-valuemax")).toBeCloseTo(0.35, 9);
  expect(await end("aria-valuemin")).toBeCloseTo(0.04, 9);

  // Past the old end of its control, 0,26 eV, as the bound allows it now.
  await value(page, "E_g").fill("0,3");
  await value(page, "E_g").blur();
  await expect(value(page, "E_g")).toHaveValue("0,3");
  await expect(value(page, "E_g")).not.toHaveAttribute("aria-invalid", "true");

  await value(page, "E_g").fill("0,03");
  await value(page, "E_g").blur();
  await expect(value(page, "E_g")).toHaveAttribute("aria-invalid", "true");
});

test("bounds that do not make a range are refused, and the last ones stay", async ({
  page,
}) => {
  await open(page);

  // Below the lower bound, which counts together with it.
  await openEditor(page);
  await upper(page, "E_g").fill("-0,35");
  await upper(page, "E_g").blur();

  const message = page.getByText(/^The lower bound must be below the upper/);
  await expect(message).toBeVisible();
  await expect(upper(page, "E_g")).toHaveAttribute("aria-invalid", "true");

  await upper(page, "E_g").fill("abc");
  await upper(page, "E_g").blur();
  await expect(message).toBeVisible();

  // Equal, as it shows, is no range either.
  await upper(page, "E_g").fill("-0,26");
  await upper(page, "E_g").blur();
  await expect(message).toBeVisible();

  await upper(page, "E_g").fill("0,2");
  await upper(page, "E_g").blur();
  await expect(message).toHaveCount(0);
  await done(page);
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,2");
});

test("Done keeps the dialog open on bounds that make no range, and says why", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);
  await upper(page, "E_g").fill("-0,35");

  await done(page);

  await expect(editor(page)).toBeVisible();
  const message = page.getByText(/^The lower bound must be below the upper/);
  await expect(message).toBeVisible();

  await upper(page, "E_g").fill("0,2");
  await lower(page, "E_g").focus();
  await done(page);
  await expect(editor(page)).toHaveCount(0);
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,2");
});

test("a click beside the dialog does not close it, and Escape or the corner do", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);
  await upper(page, "E_g").fill("-0,35");

  await page.mouse.click(5, 5);
  await expect(editor(page)).toBeVisible();

  await page.getByRole("button", { name: "Close" }).click();
  await expect(editor(page)).toHaveCount(0);
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,26");

  await openEditor(page);
  await expect(page.getByText(/^The lower bound must/)).toHaveCount(0);
  await expect(upper(page, "E_g")).toHaveValue("0,26");
  await done(page);
  await expect(editor(page)).toHaveCount(0);
});

test("going from the lower field to the upper says nothing until the row is left", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);
  const message = page.getByText(/^The lower bound must/);

  await lower(page, "E_g").fill("0,4");
  await lower(page, "E_g").press("Tab");
  await expect(upper(page, "E_g")).toBeFocused();
  await expect(message).toHaveCount(0);

  await upper(page, "E_g").fill("0,5");
  await upper(page, "E_g").press("Tab");
  await expect(message).toHaveCount(0);
  await done(page);
  await expect(row(page, "E_g")).toContainText("0,4 … 0,5");
});

test("leaving a row with bounds that make no range says so at once", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);

  await lower(page, "E_g").fill("0,4");
  await lower(page, "m₂/m₁").focus();

  await expect(page.getByText(/^The lower bound must/)).toBeVisible();
  await expect(lower(page, "E_g")).toHaveAttribute("aria-invalid", "true");
});

const setStoredBounds = (page: Page, bounds: object) =>
  page.evaluate(async (value) => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          setCustomBounds: (mode: string, name: string, bounds: object) => void;
        };
      };
    };
    useSessionStore.getState().setCustomBounds("dpb_s_rho", "band_gap", value);
  }, bounds);

test("an end left as it is keeps its exact value, and the check uses that", async ({
  page,
}) => {
  await open(page);
  await setStoredBounds(page, { lower: 1000.0004, upper: 2000 });
  await openEditor(page);
  // 0,0861733 eV, rounded up as it shows.
  await expect(lower(page, "E_g")).toHaveValue("0,09");

  // Below what the field shows, but above the exact value it stands for.
  await upper(page, "E_g").fill("0,087");
  await upper(page, "E_g").blur();
  await expect(page.getByText(/^The lower bound must/)).toHaveCount(0);
  await done(page);

  // E_g starts at 1000, just below the exact bound, so a fit is held back by it. Both ends of
  // this range show as 0,09 eV, so the value inside it is set directly.
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          setParameter: (mode: string, name: string, value: number) => void;
        };
      };
    };
    useSessionStore.getState().setParameter("dpb_s_rho", "band_gap", 1005);
  });
  await run(page).click();
  expect((await fitBodies(page))[0]?.bounds).toEqual({
    band_gap: { lower: 1000.0004, upper: 1009.59307659 },
  });
});

test("the slider's keys stop at the bounds, not at its old range", async ({
  page,
}) => {
  await open(page);
  await setBounds(page, "E_g", "0,08", "0,11");
  const thumb = slider(page, "E_g");

  await thumb.press("ArrowRight");
  await thumb.press("ArrowRight");
  await thumb.press("ArrowRight");
  await expect(value(page, "E_g")).toHaveValue("0,11");

  await thumb.press("PageDown");
  await thumb.press("PageDown");
  await thumb.press("PageDown");
  await thumb.press("PageDown");
  await thumb.press("PageDown");
  await thumb.press("PageDown");
  await expect(value(page, "E_g")).toHaveValue("0,08");
});

test("a fit whose values read past the bounds goes on, and only the next is stopped", async ({
  page,
}) => {
  await open(page);
  await setBounds(page, "m₂/m₁", "0,5", "3");
  await run(page).click();
  await send(page, { type: "started" });
  await expect(stop(page)).toBeVisible();

  // With N₂/N₁ of 2, a value of 2 is reported as 4 (D12).
  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { m_eff: 4 },
  });
  await expect(value(page, "m₂/m₁")).toHaveValue("4");
  await page.waitForTimeout(200);

  await expect(stop(page)).toBeVisible();
  expect(await page.evaluate(() => window.fitTest.aborted)).toBe(0);
  await expect(page.getByText(/cannot start outside/)).toHaveCount(0);

  await send(page, {
    type: "done",
    result: { ...RESULT, parameters: { m_eff: 4 } },
  });
  await expect(
    page.locator('[data-slot="badge"]').filter({ hasText: /^Converged/ }),
  ).toBeVisible();
  await expect(run(page)).toBeDisabled();
  await expect(
    page.getByText("A fit cannot start outside its bounds: m₂/m₁."),
  ).toBeVisible();
});

test("a guess outside the bounds shows, and stops Run as any value would", async ({
  page,
}) => {
  await open(page);
  await setBounds(page, "E_g", "0,08", "0,1");
  await page.route("**/api/guess", (route) =>
    route.fulfill({
      json: {
        status: "guess",
        net_range: { min_temperature_k: 25, max_temperature_k: 750 },
        prediction: { m_eff: 1.57, band_gap_k: 554, fermi_energy_k: 1170 },
        start_values: { m_eff: 1.57, band_gap: 554, fermi_energy: 1170 },
        warnings: [],
      },
    }),
  );

  await page.getByRole("button", { name: "Initial guess" }).click();

  // 554 K.
  await expect(value(page, "E_g")).toHaveValue("0,05");
  await expect(row(page, "E_g")).toContainText("0,08 … 0,1");
  await expect(run(page)).toBeDisabled();
  await expect(
    page.getByText("A fit cannot start outside its bounds: E_g."),
  ).toBeVisible();
});

test("Enter sets them too, and a range can move past its old end", async ({
  page,
}) => {
  await open(page);
  await setBounds(page, "E_g", "0,01", "0,02");

  await openEditor(page);
  await upper(page, "E_g").fill("0,05");
  await lower(page, "E_g").fill("0,04");
  await lower(page, "E_g").press("Enter");
  await expect(upper(page, "E_g")).toHaveValue("0,05");
  await lower(page, "E_g").press("Escape");

  await expect(row(page, "E_g")).toContainText("0,04 … 0,05");
});

test("a start outside its bounds stops Run, and says which, and values do not move", async ({
  page,
}) => {
  await open(page);

  await setBounds(page, "E_g", "0,13", "0,17");

  await expect(value(page, "E_g")).toHaveValue("0,09");
  await expect(run(page)).toBeDisabled();
  await expect(
    page.getByText("A fit cannot start outside its bounds: E_g."),
  ).toBeVisible();

  await value(page, "E_g").fill("0,15");
  await value(page, "E_g").blur();
  await expect(run(page)).toBeEnabled();
  await expect(page.getByText(/cannot start outside/)).toHaveCount(0);
});

test("bounds of another scattering neither go with a fit nor stop it", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /Alloy disorder/ }).click();
  await setBounds(page, "G", "1,5", "2");
  await expect(run(page)).toBeDisabled();

  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /Acoustic phonons/ }).click();
  await expect(run(page)).toBeEnabled();
  await run(page).click();

  const bodies = await fitBodies(page);
  expect(bodies[0]?.bounds).toBeUndefined();
});

test("each mode has its own, and they stay when coming back", async ({
  page,
}) => {
  await open(page);
  await setBounds(page, "E_g", "0,04", "0,13");

  await page.getByRole("radio", { name: "S", exact: true }).click();
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,26");
  await openEditor(page);
  await expect(lower(page, "E_g")).toHaveValue("-0,26");
  await done(page);

  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await expect(row(page, "E_g")).toContainText("0,04 … 0,13");
  await openEditor(page);
  await expect(lower(page, "E_g")).toHaveValue("0,04");
});

test("Default bounds ends a change and what was being typed, and keeps the values", async ({
  page,
}) => {
  await open(page);
  await openEditor(page);
  await expect(defaults(page)).toHaveCount(0);
  await done(page);
  await value(page, "E_g").fill("0,1");
  await value(page, "E_g").blur();
  await setBounds(page, "E_g", "0,04", "0,13");
  await openEditor(page);
  await lower(page, "m₂/m₁").fill("5");
  await lower(page, "m₂/m₁").blur();
  await expect(page.getByText(/^The lower bound must/)).toBeVisible();

  await defaults(page).click();

  await expect(page.getByRole("button", { name: "Done" })).toBeFocused();
  await expect(lower(page, "E_g")).toHaveValue("-0,26");
  await expect(lower(page, "m₂/m₁")).toHaveValue("-3");
  await expect(page.getByText(/^The lower bound must/)).toHaveCount(0);
  await expect(defaults(page)).toHaveCount(0);
  await done(page);
  await expect(row(page, "E_g")).toContainText("-0,26 … 0,26");
  await expect(value(page, "E_g")).toHaveValue("0,1");

  await run(page).click();
  expect((await fitBodies(page))[0]?.bounds).toBeUndefined();
});

test("typing the default bounds back sends nothing", async ({ page }) => {
  await open(page);
  await setBounds(page, "E_g", "500", "1500");
  await setBounds(page, "E_g", "-3000", "3000");

  await openEditor(page);
  await expect(defaults(page)).toHaveCount(0);
  await done(page);
  await run(page).click();
  expect((await fitBodies(page))[0]?.bounds).toBeUndefined();
});

test("Reset restores the default bounds with the values", async ({ page }) => {
  await open(page);
  await setBounds(page, "E_g", "0,04", "0,13");

  await page.getByRole("button", { name: "Reset" }).click();

  await expect(row(page, "E_g")).toContainText("-0,26 … 0,26");
  await expect(slider(page, "E_g")).toHaveAttribute(
    "aria-valuemax",
    "0.25851999786",
  );
  await openEditor(page);
  await expect(lower(page, "E_g")).toHaveValue("-0,26");
  await done(page);
  await run(page).click();
  expect((await fitBodies(page))[0]?.bounds).toBeUndefined();
});

test("a change of bounds ends the last result, and a fit locks them", async ({
  page,
}) => {
  await open(page);
  await run(page).click();
  await send(page, { type: "started" });
  await expect(stop(page)).toBeVisible();
  await openEditor(page);
  await expect(lower(page, "E_g")).toBeDisabled();
  await done(page);

  await send(page, {
    type: "done",
    result: { ...RESULT, at_bounds: ["band_gap"] },
  });
  await expect(row(page, "E_g").getByText("at bound")).toBeVisible();
  await openEditor(page);
  await expect(lower(page, "E_g")).toBeEnabled();
  await done(page);

  await setBounds(page, "E_g", "0", "0,35");

  await expect(row(page, "E_g").getByText("at bound")).toHaveCount(0);
  await expect(fitBadges(page)).toHaveCount(0);
});

test("only editable bounds can be changed", async ({ page }) => {
  await open(page);
  await page.getByRole("radio", { name: "SPB", exact: true }).click();
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();

  // A, C and F are fixed here, so only E_F can change.
  await expect(row(page, "A")).toContainText("1 … 10000000");
  await openEditor(page);
  await expect(lower(page, "E_F")).toBeVisible();
  await expect(lower(page, "A")).toHaveCount(0);
});

test("with no editable bounds, there is no button", async ({ page }) => {
  await fakeFit(page);
  await serveModels(page);
  const models = structuredClone(MODELS) as ModelsForTest;
  for (const model of models.models) {
    for (const mode of model.fit_modes) {
      for (const parameter of mode.parameters) {
        parameter.bounds_editable = false;
      }
    }
  }
  await page.route("**/api/models", (route) => route.fulfill({ json: models }));
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();

  await expect(page.getByRole("button", { name: "Edit bounds" })).toHaveCount(
    0,
  );
});

test("bounds convert to core units, where the scales of a parameter differ", async ({
  page,
}) => {
  await fakeFit(page);
  await serveModels(page);
  const models = structuredClone(MODELS) as ModelsForTest;
  for (const model of models.models) {
    for (const mode of model.fit_modes) {
      for (const parameter of mode.parameters) {
        if (parameter.name === "B") {
          // Core units 100 times the displayed ones, as C has in SPB S + ρ.
          parameter.fit_scale = 1;
          parameter.fit_bounds = { lower: 90, upper: 110 };
        }
      }
    }
  }
  await page.route("**/api/models", (route) => route.fulfill({ json: models }));
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();

  await openEditor(page);
  await expect(lower(page, "B")).toHaveValue("0,9");
  await lower(page, "B").fill("0,5");
  await upper(page, "B").fill("2");
  await done(page);

  await expect(row(page, "B")).toContainText("0,5 … 2");
  await expect(slider(page, "B")).toHaveAttribute("aria-valuemax", "2");
  const stored = await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => { customBounds: Record<string, object> };
      };
    };
    return useSessionStore.getState().customBounds;
  });
  expect(stored.dpb_s_rho).toEqual({ B: { lower: 50, upper: 200 } });
});
