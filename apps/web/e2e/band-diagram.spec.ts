import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

const answerFor = (curves: Record<string, (number | null)[]>) => ({
  wavevector: [-40, 0, 40],
  curves,
  known_issues: ["band_diagram_formula"],
});
const DPB = answerFor({
  band_1_energy_k: [-1954, 0, -1954],
  band_2_energy_k: [2954, 1000, 2954],
  fermi_energy_k: [-100, -100, -100],
});
const SPB = answerFor({
  band_1_energy_k: [1935, 0, 1935],
  fermi_energy_k: [100, 100, 100],
});

interface DiagramBody {
  model: string;
  fit_mode: string;
  parameters: Record<string, number>;
  band_1_degeneracy: number;
  band_2_degeneracy: number;
}

function hold() {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release: () => release() };
}

async function open(
  page: Page,
  answer: (route: Route, body: DiagramBody) => Promise<void> = (route, body) =>
    route.fulfill({ json: body.model === "spb" ? SPB : DPB }),
) {
  await serveModels(page);
  const bodies: DiagramBody[] = [];
  await page.route("**/api/band-diagram", (route) => {
    const body = route.request().postDataJSON() as DiagramBody;
    bodies.push(body);
    return answer(route, body);
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  return bodies;
}

const tab = (page: Page, name = "E(k)") => page.getByRole("tab", { name });
const legend = (page: Page) => page.locator("ul li");
const traces = (page: Page) =>
  page.locator(".js-plotly-plot .scatterlayer .trace");
const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const choose = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true }).click();

test("it asks for nothing until its tab is open, and needs no data", async ({
  page,
}) => {
  const bodies = await open(page);
  await page.waitForTimeout(400);
  expect(bodies).toEqual([]);

  await tab(page).click();

  await expect(traces(page)).toHaveCount(3);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]).toMatchObject({
    model: "dpb",
    fit_mode: "dpb_s_rho",
    band_1_degeneracy: 1,
    band_2_degeneracy: 1,
  });
  expect(bodies[0]?.parameters.band_gap).toBe(1000);
});

test("it draws each band and E_F, with a k axis with no ticks or range shading", async ({
  page,
}) => {
  await open(page);

  await tab(page).click();

  await expect(traces(page)).toHaveCount(3);
  await expect(legend(page)).toHaveText(["Band 1", "Band 2", "E_F"]);
  await expect(page.locator(".xtitle")).toHaveText("k");
  await expect(page.locator(".ytitle")).toHaveText("E, K");
  await expect(page.locator(".xtick text")).toHaveCount(0);
  await expect(page.locator(".shapelayer path")).toHaveCount(0);
  await expect(page.getByText(/^Show measurements/)).toHaveCount(0);
});

test("the axis spans k, and a temperature tab goes back to its own", async ({
  page,
}) => {
  await open(page);
  await tab(page).click();
  await expect(traces(page)).toHaveCount(3);
  const range = () =>
    page.evaluate(() => {
      const plot = document.querySelector(".js-plotly-plot") as unknown as {
        layout: { xaxis: { range: number[] } };
      };
      return plot.layout.xaxis.range;
    });
  expect(await range()).toEqual([-40, 40]);

  await tab(page, "μ(T)").click();
  await expect(page.locator(".xtitle")).toHaveText("T, K");
  await expect(page.locator(".xtick text").first()).toBeVisible();
  expect((await range())[0]).toBe(0);
});

test("it follows the parameters and the degeneracies", async ({ page }) => {
  const bodies = await open(page);
  await tab(page).click();
  await expect(traces(page)).toHaveCount(3);

  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();
  await expect.poll(() => bodies.at(-1)?.parameters.band_gap).toBe(500);

  await page.getByLabel("N₂").fill("2");
  await page.getByLabel("N₂").blur();
  await expect.poll(() => bodies.at(-1)?.band_2_degeneracy).toBe(2);
});

test("SPB draws what its answer holds, and an old mode's bands do not stay", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route, body) => {
    if (body.model === "spb") {
      await gate.held;
      await route.fulfill({ json: SPB });
    } else {
      await route.fulfill({ json: DPB });
    }
  });
  await tab(page).click();
  await expect(traces(page)).toHaveCount(3);

  await choose(page, "SPB");
  await expect(legend(page)).toHaveCount(0);

  gate.release();
  await expect(legend(page)).toHaveText(["Band 1", "E_F"]);
  await expect(traces(page)).toHaveCount(2);
});

test("it stops asking when another tab opens", async ({ page }) => {
  const bodies = await open(page);
  await tab(page).click();
  await expect(traces(page)).toHaveCount(3);
  await tab(page, "S(T)").click();
  const asked = bodies.length;

  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();
  await page.waitForTimeout(500);

  expect(bodies).toHaveLength(asked);
});

test("it says what is known to be wrong with it", async ({ page }) => {
  await open(page);

  await tab(page).click();

  await expect(
    page.getByText(/^Caution: This is a sketch, as on the desktop\./),
  ).toBeVisible();
  await expect(page.getByText(/band_diagram_formula/)).toHaveCount(0);
});

test("a band with no finite values leaves a gap, and the rest stay", async ({
  page,
}) => {
  await open(page, (route) =>
    route.fulfill({
      json: answerFor({
        band_1_energy_k: [-1954, 0, -1954],
        band_2_energy_k: [null, null, null],
        fermi_energy_k: [-100, -100, -100],
      }),
    }),
  );

  await tab(page).click();

  await expect(legend(page)).toHaveText(["Band 1", "Band 2", "E_F"]);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a failure says so, and the last sketch stays", async ({ page }) => {
  let failing = false;
  await open(page, (route) =>
    failing
      ? route.fulfill({
          status: 422,
          json: { code: "invalid_band_diagram", message: "x", details: [] },
        })
      : route.fulfill({ json: DPB }),
  );
  await tab(page).click();
  await expect(traces(page)).toHaveCount(3);

  failing = true;
  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();

  await expect(page.getByRole("alert")).toContainText(
    "The last curve stays on the chart.",
  );
  await expect(traces(page)).toHaveCount(3);

  await tab(page, "S(T)").click();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a failure of the curves does not show on it", async ({ page }) => {
  const asked: unknown[] = [];
  await open(page);
  await page.route("**/api/calc", (route) => {
    asked.push(route.request().postDataJSON());
    return route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    });
  });
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: {
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
      },
    }),
  );
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(page.getByRole("alert")).toBeVisible();

  await tab(page).click();

  await expect(traces(page)).toHaveCount(3);
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(asked.length).toBeGreaterThan(0);
});

test("a disabled mode asks for nothing", async ({ page }) => {
  const bodies = await open(page);
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          setSelection: (selection: object) => void;
          setChartTab: (tab: string) => void;
        };
      };
    };
    const state = useSessionStore.getState();
    state.setSelection({ model: "spb", fitMode: "spb_s_rho_rh" });
    state.setChartTab("band_diagram");
  });
  await expect(tab(page)).toHaveAttribute("aria-selected", "true");
  await page.waitForTimeout(400);

  expect(bodies).toEqual([]);
});
