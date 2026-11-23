import { expect, test, type Page, type Route } from "@playwright/test";

import { chart, show } from "./support/fitScreen";
import { serveModels } from "./support/models";

// Energies come in K and show in eV.
const EV_PER_K = 8.617333262e-5;
const inEv = (values: (number | null)[]) =>
  values.map((value) => (value === null ? null : value * EV_PER_K));

const answerFor = (
  curves: Record<string, (number | null)[]>,
  reference_mass_assumed: boolean,
) => ({
  wavevector_nm_inv: [-2, 0, 2],
  curves,
  known_issues: [],
  reference_mass_assumed,
});
const DPB = answerFor(
  {
    band_1_energy_k: [-1768.52, 0, -1768.52],
    band_2_energy_k: [2768.52, 1000, 2768.52],
    fermi_energy_k: [-100, -100, -100],
  },
  true,
);
const SPB = answerFor(
  {
    band_1_energy_k: [1751.01, 0, 1751.01],
    fermi_energy_k: [100, 100, 100],
  },
  false,
);

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
  await expect(page.getByRole("slider", { name: "EF" })).toBeVisible();
  return bodies;
}

// The last chart shows the bands from the start.
const diagram = (page: Page) => chart(page, 4);
const legend = (page: Page) => diagram(page).locator("ul li");
const traces = (page: Page) =>
  diagram(page).locator(".js-plotly-plot .scatterlayer .trace");
const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const choose = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true }).click();

test("the last chart shows it from the start, with no data, in one request", async ({
  page,
}) => {
  const bodies = await open(page);

  await expect(traces(page)).toHaveCount(3);
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]).toMatchObject({
    model: "dpb",
    fit_mode: "dpb_s_rho",
    band_1_degeneracy: 1,
    band_2_degeneracy: 1,
  });
  expect(bodies[0]?.parameters.band_gap).toBe(1000);
});

test("Eg over the chart shows in eV, as its field does, and follows it", async ({
  page,
}) => {
  await open(page);

  // 1000 K by default.
  await expect(diagram(page).getByText("Eg = 0,09 eV")).toBeVisible();
  await expect(field(page, "Eg")).toHaveValue("0,09");
  await field(page, "Eg").fill("0,123");
  await field(page, "Eg").blur();
  await expect(diagram(page).getByText("Eg = 0,12 eV")).toBeVisible();
  await expect(field(page, "Eg")).toHaveValue("0,12");
});

test("it draws each band and EF over a k axis with no values, without fit range shading", async ({
  page,
}) => {
  await open(page);

  await expect(traces(page)).toHaveCount(3);
  await expect(legend(page)).toHaveText(["Band 1", "Band 2", "EF"]);
  await expect(diagram(page).locator(".xtitle")).toHaveText("k");
  await expect(diagram(page).locator(".ytitle")).toHaveText("E, eV");
  await expect(diagram(page).locator(".xtick text")).toHaveCount(0);
  await expect(diagram(page).locator(".shapelayer path")).toHaveCount(0);
});

test("the axis spans k, and a temperature tab goes back to its own", async ({
  page,
}) => {
  await open(page);
  await expect(traces(page)).toHaveCount(3);
  const range = () =>
    diagram(page)
      .locator(".js-plotly-plot")
      .evaluate((element) => {
        const plot = element as unknown as {
          layout: { xaxis: { range: number[] } };
        };
        return plot.layout.xaxis.range;
      });
  expect(await range()).toEqual([-2, 2]);

  await show(page, "Chemical potential μ(T)", 4);
  await expect(diagram(page).locator(".xtitle")).toHaveText("T, K");
  await expect(diagram(page).locator(".xtick text").first()).toBeVisible();
  expect((await range())[0]).toBe(0);
});

test("it follows the parameters and the degeneracies", async ({ page }) => {
  const bodies = await open(page);
  await expect(traces(page)).toHaveCount(3);

  await field(page, "Eg").fill("0,05");
  await field(page, "Eg").blur();
  await expect
    .poll(() => bodies.at(-1)?.parameters.band_gap)
    .toBe(580.225906087);

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
  await expect(traces(page)).toHaveCount(3);

  await choose(page, "SPB");
  await expect(legend(page)).toHaveCount(0);

  gate.release();
  await expect(legend(page)).toHaveText(["Band 1", "EF"]);
  await expect(traces(page)).toHaveCount(2);
  await expect(
    diagram(page).getByText(/so it is assumed to be mₑ/),
  ).toHaveCount(0);
});

test("it stops asking when no chart shows it, and asks again when one does", async ({
  page,
}) => {
  const bodies = await open(page);
  await expect(traces(page)).toHaveCount(3);
  await show(page, "Seebeck S(T)", 4);
  const asked = bodies.length;

  await field(page, "Eg").fill("0,05");
  await field(page, "Eg").blur();
  await page.waitForTimeout(500);

  expect(bodies).toHaveLength(asked);

  // In two charts at once, it is still one request.
  await show(page, "Band diagram E(k)", 1);
  await show(page, "Band diagram E(k)", 4);
  await expect(traces(page)).toHaveCount(3);
  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(asked + 1);
  expect(bodies.at(-1)?.parameters.band_gap).toBe(580.225906087);
});

test("it labels the assumed mass in DPB without Hall data", async ({
  page,
}) => {
  await open(page);

  await expect(
    diagram(page).getByText(/so it is assumed to be mₑ/),
  ).toBeVisible();
});

test("a band with no finite values leaves a gap, and the rest stay", async ({
  page,
}) => {
  const curves = { ...DPB.curves, band_2_energy_k: [null, null, null] };
  await open(page, (route) => route.fulfill({ json: { ...DPB, curves } }));

  await expect(legend(page)).toHaveText(["Band 1", "Band 2", "EF"]);
  await expect(diagram(page).getByRole("alert")).toHaveCount(0);
  const ys = await diagram(page)
    .locator(".js-plotly-plot")
    .evaluate((element) => {
      const plot = element as unknown as {
        data: { y: (number | null)[] }[];
      };
      return plot.data.map(({ y }) => y);
    });
  expect(ys).toEqual(Object.values(curves).map(inEv));
});

test("the k axis keeps its title and no values while awaiting the first answer", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: DPB });
  });

  await expect(diagram(page).locator(".js-plotly-plot")).toBeVisible();
  await expect(diagram(page).locator(".xtitle")).toHaveText("k");
  await expect(diagram(page).locator(".xtick text")).toHaveCount(0);
  gate.release();
  await expect(traces(page)).toHaveCount(3);
  await expect(diagram(page).locator(".xtick text")).toHaveCount(0);
});

test("a failure says so, and the last diagram stays", async ({ page }) => {
  let failing = false;
  await open(page, (route) =>
    failing
      ? route.fulfill({
          status: 422,
          json: { code: "invalid_band_diagram", message: "x", details: [] },
        })
      : route.fulfill({ json: DPB }),
  );
  await expect(traces(page)).toHaveCount(3);

  failing = true;
  await field(page, "Eg").fill("0,05");
  await field(page, "Eg").blur();

  await expect(diagram(page).getByRole("alert")).toContainText(
    "The last curve stays on the chart.",
  );
  await expect(traces(page)).toHaveCount(3);

  await show(page, "Seebeck S(T)", 4);
  await expect(diagram(page).getByRole("alert")).toHaveCount(0);
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
        headers: ["T", "x"],
        column_count: 2,
        row_count: 2,
        preview: [],
        preview_si: [],
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
        interpolation_failure_reasons: {},
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
  await expect(chart(page).getByRole("alert")).toBeVisible();

  await expect(traces(page)).toHaveCount(3);
  await expect(diagram(page).getByRole("alert")).toHaveCount(0);
  expect(asked.length).toBeGreaterThan(0);
});

test("the repaired SPB Hall mode requests its band diagram", async ({
  page,
}) => {
  const bodies = await open(page);
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          setSelection: (selection: object) => void;
        };
      };
    };
    const state = useSessionStore.getState();
    state.setSelection({ model: "spb", fitMode: "spb_s_rho_rh" });
  });
  const asked = bodies.length;
  await field(page, "EF").fill("0,05");
  await field(page, "EF").blur();
  await page.waitForTimeout(400);

  await expect.poll(() => bodies.length).toBeGreaterThan(asked);
  expect(bodies.at(-1)).toMatchObject({
    model: "spb",
    fit_mode: "spb_s_rho_rh",
  });
});
