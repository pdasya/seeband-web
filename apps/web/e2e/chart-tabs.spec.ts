import { expect, test, type Page } from "@playwright/test";

import { serveModels } from "./support/models";

interface CalcBody {
  kind?: string;
  fit_mode: string;
  measurements: Record<string, unknown>;
  parameters: Record<string, number>;
}

const CURVES: Record<string, Record<string, number[]>> = {
  measured: {
    seebeck_v_per_k: [1e-4, 2e-4, 1.5e-4],
    resistivity_ohm_m: [1e-5, 2e-5, 3e-5],
    hall_m3_per_c: [1e-9, 2e-9, 3e-9],
  },
  chemical_potential: { chemical_potential_k: [-100, -150, -200] },
  seebeck_by_band: {
    seebeck_band_1_v_per_k: [2e-4, 3e-4, 2e-4],
    seebeck_band_2_v_per_k: [-1e-4, -1e-4, -5e-5],
  },
};

const parsedFor = (quantity: string) => ({
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

async function open(page: Page) {
  await serveModels(page);
  const bodies: CalcBody[] = [];
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    bodies.push(body);
    return route.fulfill({
      json: {
        temperature_k: [100, 300, 500],
        curves: CURVES[body.kind ?? "measured"],
        known_issues: [],
        rmse: {},
      },
    });
  });
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: parsedFor(expected) });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  return bodies;
}

const tab = (page: Page, name: string) =>
  page.getByRole("tab", { name, exact: true });
const lines = (page: Page) => page.locator(".scatterlayer .trace path.js-line");
const legend = (page: Page, name: string) =>
  page.getByRole("listitem").filter({ hasText: new RegExp(`^${name}$`) });
const yTitle = (page: Page) => page.locator(".ytitle");

async function load(page: Page, slot: number) {
  await page
    .locator('input[type="file"]')
    .nth(slot)
    .setInputFiles({
      name: `f${String(slot)}.txt`,
      mimeType: "text/plain",
      buffer: Buffer.from("T x\n100 1\n"),
    });
  await expect(page.getByText(/^2 points/).first()).toBeVisible();
}

test("the tabs are tabs, with a panel, and work from the keyboard", async ({
  page,
}) => {
  await open(page);

  await expect(tab(page, "S(T)")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tablist", { name: "Charts" })).toBeVisible();

  await tab(page, "S(T)").focus();
  await page.keyboard.press("ArrowRight");

  await expect(tab(page, "ρ(T)")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "ρ(T)" })).toContainText(
    "No data for this quantity",
  );
});

test("each empty state matches its cause", async ({ page }) => {
  await open(page);

  await expect(page.getByText("No data for this quantity")).toBeVisible();

  await tab(page, "R_H(T)").click();
  await expect(page.getByText("No R_H(T) data")).toBeVisible();
  await expect(page.getByText("determines the absolute mass")).toBeVisible();
  await expect(page.getByText(/not part of this prototype/)).toHaveCount(0);

  await page.getByRole("radio", { name: "SPB" }).click();
  await tab(page, "Band contributions").click();
  await expect(page.getByText("DPB only")).toBeVisible();
  await expect(page.getByText("two-parabolic-band model")).toBeVisible();
});

test("ρ and R_H draw their own curves, units and points", async ({ page }) => {
  await open(page);
  await load(page, 1);

  await tab(page, "ρ(T)").click();

  await expect(yTitle(page)).toHaveText("ρ, µΩ·m");
  await expect(lines(page)).toHaveCount(1);
  await expect(legend(page, "Measurements")).toBeVisible();
  await expect(legend(page, "Model")).toBeVisible();

  await tab(page, "S(T)").click();
  await expect(page.getByText("No data for this quantity")).toBeVisible();
});

test("R_H has a curve only in the mode with it", async ({ page }) => {
  await open(page);
  await load(page, 2);
  await tab(page, "R_H(T)").click();

  await expect(yTitle(page)).toHaveText("R_H, m³/C");
  await expect(legend(page, "Measurements")).toBeVisible();
  await expect(legend(page, "Model")).toHaveCount(0);
  await expect(
    page.getByText("The R_H model is not calculated in this fit mode."),
  ).toBeVisible();

  await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();

  await expect(legend(page, "Model")).toBeVisible();
  await expect(page.getByText(/R_H model is not calculated/)).toHaveCount(0);
});

test("μ needs no data, has band edges, and follows E_g", async ({ page }) => {
  const bodies = await open(page);

  await tab(page, "μ(T)").click();

  await expect.poll(() => bodies.at(-1)?.kind).toBe("chemical_potential");
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]?.measurements).toEqual({});
  await expect(yTitle(page)).toHaveText("μ, K");
  await expect(lines(page)).toHaveCount(1);
  await expect(page.getByText("band 1 top")).toBeVisible();
  await expect(page.getByText("band 2 bottom (E_g)")).toBeVisible();

  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(page.getByText("band edge")).toBeVisible();
  await expect(page.getByText("band 1 top")).toHaveCount(0);
});

test("contributions draw the total and each band, with no data", async ({
  page,
}) => {
  const bodies = await open(page);

  await tab(page, "Band contributions").click();

  await expect(legend(page, "Total S")).toBeVisible();
  await expect(legend(page, "band 1 contribution")).toBeVisible();
  await expect(legend(page, "band 2 contribution")).toBeVisible();
  await expect(lines(page)).toHaveCount(3);
  await expect(yTitle(page)).toHaveText("S, µV/K");
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(2);
  expect(bodies.map(({ kind }) => kind).sort()).toEqual([
    "seebeck_by_band",
    undefined,
  ]);
});

test("other curves are asked for only while their tab is open", async ({
  page,
}) => {
  const bodies = await open(page);
  await load(page, 0);
  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0]?.kind).toBeUndefined();
  expect(Object.keys(bodies[0]?.measurements ?? {})).toEqual(["seebeck"]);

  await tab(page, "μ(T)").click();
  await expect
    .poll(() => bodies.filter(({ kind }) => kind !== undefined))
    .toHaveLength(1);

  // The API refuses measurements with other kinds of curve.
  expect(bodies.find(({ kind }) => kind !== undefined)?.measurements).toEqual(
    {},
  );

  await tab(page, "S(T)").click();
  const count = bodies.length;
  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");
  await expect.poll(() => bodies.length).toBe(count + 1);
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(count + 1);
  expect(bodies.at(-1)?.kind).toBeUndefined();
  expect(bodies.at(-1)?.parameters.band_gap).toBe(1010);
});

test("a change on a tab asks for both, and the RMSE stays live", async ({
  page,
}) => {
  const bodies = await open(page);
  await load(page, 0);
  await tab(page, "μ(T)").click();
  await expect
    .poll(() => bodies.filter(({ kind }) => kind !== undefined))
    .toHaveLength(1);
  const count = bodies.length;

  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");

  await expect.poll(() => bodies.length).toBe(count + 2);
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(count + 2);
  expect(
    bodies
      .slice(-2)
      .map(({ kind }) => kind)
      .sort(),
  ).toEqual(["chemical_potential", undefined]);
});

test("a failed curve of a tab says so there, and not on the others", async ({
  page,
}) => {
  await open(page);
  await load(page, 0);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return body.kind === "chemical_potential"
      ? route.fulfill({
          status: 422,
          json: { code: "calculation_failed", message: "x", details: [] },
        })
      : route.fulfill({
          json: {
            temperature_k: [100, 300, 500],
            curves: CURVES.measured,
            known_issues: [],
            rmse: {},
          },
        });
  });

  await tab(page, "μ(T)").click();
  await expect(page.getByRole("alert")).toContainText("no result");

  await tab(page, "S(T)").click();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a failure of S does not show on μ, and the RMSE says it is old", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return route.fulfill({
      json: {
        temperature_k: [100, 300, 500],
        curves: CURVES[body.kind ?? "measured"],
        known_issues: [],
        rmse: { seebeck: { value: 111, unit: "uV/K" } },
      },
    });
  });
  await load(page, 0);
  await expect(page.getByText("111 µV/K")).toBeVisible();
  await tab(page, "μ(T)").click();
  await expect(lines(page)).toHaveCount(1);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return body.kind === undefined
      ? route.fulfill({
          status: 422,
          json: { code: "calculation_failed", message: "x", details: [] },
        })
      : route.fulfill({
          json: {
            temperature_k: [100, 300, 500],
            curves: CURVES[body.kind],
            known_issues: [],
            rmse: {},
          },
        });
  });

  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");

  await expect(page.getByText("not from the current values")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await tab(page, "S(T)").click();
  await expect(page.getByRole("alert")).toContainText("no result");
});

test("known errors of a tab's curves are named while it is open", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return route.fulfill({
      json: {
        temperature_k: [100, 300, 500],
        curves: CURVES[body.kind ?? "measured"],
        known_issues: body.kind === undefined ? [] : ["acphdis_curve_scale"],
        rmse: {},
      },
    });
  });

  await tab(page, "Band contributions").click();
  await expect(page.getByText(/σ, κ and S by band/)).toBeVisible();

  await tab(page, "S(T)").click();
  await expect(page.getByText(/σ, κ and S by band/)).toHaveCount(0);
});

function hold() {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release: () => release() };
}

const answerFor = (body: CalcBody, issues: string[] = []) => ({
  temperature_k: [100, 300, 500],
  curves: CURVES[body.kind ?? "measured"],
  known_issues: issues,
  rmse: {},
});

test("known errors of a tab go with it at once, also if the next curve fails", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return route.fulfill({
      json: answerFor(
        body,
        body.kind === "seebeck_by_band" ? ["acphdis_curve_scale"] : [],
      ),
    });
  });
  await tab(page, "Band contributions").click();
  await expect(page.getByText(/σ, κ and S by band/)).toBeVisible();
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    await gate.held;
    await route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    });
  });

  await tab(page, "μ(T)").click();
  await expect(page.getByText(/σ, κ and S by band/)).toHaveCount(0);

  gate.release();
  await expect(page.getByRole("alert")).toContainText("no result");
  await expect(page.getByText(/σ, κ and S by band/)).toHaveCount(0);
  await expect(page.getByRole("alert")).not.toContainText("last curve");
});

test("a change of mode takes the old curve away at once, and says it waits", async ({
  page,
}) => {
  await open(page);
  await tab(page, "μ(T)").click();
  await expect(lines(page)).toHaveCount(1);
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    await gate.held;
    await route.fulfill({ json: answerFor(body) });
  });

  await page.getByRole("radio", { name: "S", exact: true }).click();

  await expect(lines(page)).toHaveCount(0);
  await expect(page.getByText("Updating…")).toBeVisible();

  gate.release();
  await expect(lines(page)).toHaveCount(1);
  await expect(page.getByText("Updating…")).toHaveCount(0);
});

test("a failed curve of a new mode leaves no old curve", async ({ page }) => {
  await open(page);
  await load(page, 0);
  await expect(lines(page)).toHaveCount(1);
  await page.route("**/api/calc", (route) =>
    route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    }),
  );

  await page.getByRole("radio", { name: "S", exact: true }).click();

  await expect(page.getByRole("alert")).toContainText("no result");
  await expect(page.getByRole("alert")).not.toContainText("last curve");
  await expect(lines(page)).toHaveCount(0);
});

test("a failure of the last mode goes at once with the change of mode", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/calc", (route) =>
    route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    }),
  );
  await load(page, 0);
  await expect(page.getByRole("alert")).toContainText("no result");
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    await gate.held;
    await route.fulfill({ json: answerFor(body) });
  });

  await page.getByRole("radio", { name: "S", exact: true }).click();

  await expect(page.getByRole("alert")).toHaveCount(0);
  gate.release();
});

test("failed contributions beside the total do not call it the last curve", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return body.kind === "seebeck_by_band"
      ? route.fulfill({
          status: 422,
          json: { code: "calculation_failed", message: "x", details: [] },
        })
      : route.fulfill({ json: answerFor(body) });
  });

  await tab(page, "Band contributions").click();

  await expect(lines(page)).toHaveCount(1);
  await expect(page.getByRole("alert")).toContainText("no result");
  await expect(page.getByRole("alert")).not.toContainText("last curve");
});

test("a new value keeps the curve while waiting", async ({ page }) => {
  await open(page);
  await tab(page, "μ(T)").click();
  await expect(lines(page)).toHaveCount(1);
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    await gate.held;
    await route.fulfill({ json: answerFor(body) });
  });

  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");
  await page.waitForTimeout(400);

  await expect(lines(page)).toHaveCount(1);
  gate.release();
});

test("a tab says nothing about curves it does not draw", async ({ page }) => {
  await open(page);
  await load(page, 0);
  await expect(lines(page)).toHaveCount(1);
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    await gate.held;
    await route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    });
  });
  await page.getByRole("radio", { name: "SPB" }).click();
  await tab(page, "Band contributions").click();
  await expect(page.getByText("DPB only")).toBeVisible();

  // Well past the indicator's delay, which the next tab shows has come.
  await page.waitForTimeout(1000);
  await expect(page.getByText("Updating…")).toHaveCount(0);
  await tab(page, "S(T)").click();
  await expect(page.getByText("Updating…")).toBeVisible();

  gate.release();
  await expect(page.getByRole("alert")).toContainText("no result");

  // With the failure known to have arrived, the tabs that do not draw it stay quiet.
  await tab(page, "ρ(T)").click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await tab(page, "Band contributions").click();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

const countRedraws = (page: Page) =>
  page.evaluate(() => {
    const plot = document.querySelector(".js-plotly-plot") as unknown as {
      on: (event: string, listener: () => void) => void;
    };
    Object.assign(window, { redraws: 0 });
    plot.on("plotly_afterplot", () => {
      const counter = window as unknown as { redraws: number };
      counter.redraws += 1;
    });
  });
const redraws = (page: Page) =>
  page.evaluate(() => (window as unknown as { redraws: number }).redraws);

test("a slider does not redraw a chart whose values have not changed", async ({
  page,
}) => {
  await open(page);
  await load(page, 0);
  await expect(lines(page)).toHaveCount(1);
  await page.waitForTimeout(300);
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    await gate.held;
    await route.fulfill({ json: answerFor(body) });
  });
  await countRedraws(page);

  for (let move = 0; move < 5; move += 1) {
    await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");
  }
  await page.waitForTimeout(300);

  expect(await redraws(page)).toBe(0);

  // The same plot is still there, as an answer does redraw it.
  gate.release();
  await expect.poll(() => redraws(page)).toBeGreaterThan(0);
});

test("on μ, an answer about S does not redraw the chart", async ({ page }) => {
  await open(page);
  await load(page, 0);
  await tab(page, "μ(T)").click();
  await expect(lines(page)).toHaveCount(1);
  await expect(page.getByText("band 1 top")).toBeVisible();
  await page.waitForTimeout(300);
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    if (body.kind !== undefined) {
      await gate.held;
    }
    await route.fulfill({
      json: {
        ...answerFor(body),
        rmse: { seebeck: { value: 333, unit: "uV/K" } },
      },
    });
  });
  await countRedraws(page);

  // E_F does not reach this tab's lines, unlike E_g.
  await page.getByRole("slider", { name: "E_F" }).press("ArrowRight");

  await expect(page.getByText("333 µV/K")).toBeVisible();
  expect(await redraws(page)).toBe(0);

  gate.release();
  await expect.poll(() => redraws(page)).toBeGreaterThan(0);
});

test("the panel does not ask for data that are loaded", async ({ page }) => {
  await open(page);
  await expect(page.getByText("appears here once")).toBeVisible();
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as CalcBody;
    return route.fulfill({
      json: {
        ...answerFor(body),
        rmse: { seebeck: { value: 111, unit: "uV/K" } },
      },
    });
  });
  await load(page, 0);
  await expect(page.getByText("111 µV/K")).toBeVisible();
  const gate = hold();
  await page.route("**/api/calc", async (route) => {
    await gate.held;
    await route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    });
  });

  await page.getByRole("radio", { name: "S", exact: true }).click();

  // While it waits, the old value has gone, and nothing asks for data.
  await expect(page.getByText("111 µV/K")).toHaveCount(0);
  await expect(page.getByText("appears here once")).toHaveCount(0);
  await expect(page.getByText("could not be calculated")).toHaveCount(0);

  gate.release();

  await expect(
    page.getByText("The RMSE could not be calculated for the current values."),
  ).toBeVisible();
  await expect(page.getByText("appears here once")).toHaveCount(0);
});

test("removing the data asks for them again", async ({ page }) => {
  await open(page);
  await load(page, 0);
  await expect(page.getByText("appears here once")).toHaveCount(0);

  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();

  await expect(page.getByText("appears here once")).toBeVisible();
});

test("the open tab stays when moving to another screen and back", async ({
  page,
}) => {
  await open(page);
  await tab(page, "μ(T)").click();

  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(tab(page, "μ(T)")).toHaveAttribute("aria-selected", "true");
});
