import { readFileSync } from "node:fs";

import { strFromU8, unzipSync } from "fflate";

import { expect, test, type Page } from "@playwright/test";

import { fakeFit } from "./support/fakeFit";
import { CALC, DEMO, serveModels } from "./support/models";

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
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 },
  status: "converged",
  iterations: 5,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};

const RMSE = {
  seebeck: { value: 111, unit: "uV/K" },
  resistivity: { value: 22, unit: "%" },
};

async function stub(page: Page) {
  await fakeFit(page);
  await serveModels(page);
  await page.route("**/api/calc", (route) =>
    route.fulfill({ json: { ...CALC, rmse: RMSE } }),
  );
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
}

/** DPB S + ρ with its data, the design's first state. */
async function openFit(
  page: Page,
  // After the stubs, as a later route takes over from them.
  more: (page: Page) => Promise<unknown> = async () => {},
) {
  await stub(page);
  await more(page);
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
  await expect(page.getByRole("button", { name: "Run fit" })).toBeEnabled();
}

const send = (page: Page, event: object) =>
  page.evaluate((value) => {
    window.fitTest.send(value);
  }, event);

async function finishWith(page: Page, result: object = {}) {
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await send(page, { type: "done", result: { ...RESULT, ...result } });
  await expect(page.getByRole("button", { name: "Run fit" })).toBeVisible();
}

// Inside the app, as a reload would start a new session.
const toResults = (page: Page) =>
  page.getByRole("link", { name: "Results", exact: true }).click();

const table = (page: Page) =>
  page.getByRole("table", { name: "Fit parameters" });
// By its first cell, which may also say that the value is at a bound.
const row = (page: Page, symbol: string) =>
  table(page)
    .getByRole("row")
    .filter({
      has: page.getByRole("cell", {
        name: new RegExp(
          `^${symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}( at bound)?$`,
        ),
      }),
    });
const kpi = (page: Page, label: string) =>
  page.locator("dl > div").filter({ hasText: label });

test("with no fit, it says so and leads to the fit", async ({ page }) => {
  await stub(page);
  await page.goto("/results");

  await expect(
    page.getByText(
      "No fit for the current values. Run one on the model fit page.",
    ),
  ).toBeVisible();
  await expect(table(page)).toHaveCount(0);
  // No empty line under the title.
  await expect(page.locator("main p:empty")).toHaveCount(0);
  await page.getByRole("link", { name: "Run a fit" }).click();
  await expect(page).toHaveURL(/\/fit$/);
});

test("a fit sums up: status, KPIs and each parameter with its status", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  await toResults(page);

  await expect(
    page.locator('[data-slot="badge"]').filter({ hasText: /^Converged/ }),
  ).toHaveText("Converged in 5 iter.");
  await expect(
    page.getByText("DPB · acPh · S + ρ · range 50–800 K", { exact: true }),
  ).toBeVisible();

  await expect(kpi(page, "Model")).toContainText("DPB");
  await expect(kpi(page, "Model")).toContainText("Double parabolic band");
  await expect(kpi(page, "Scattering")).toContainText(
    "Acoustic phonons (acPh)",
  );
  await expect(kpi(page, "RMSE S")).toContainText("111 µV/K");
  await expect(kpi(page, "RMSE ρ")).toContainText("22 %");
  await expect(kpi(page, "RMSE R_H")).toHaveCount(0);
  await expect(kpi(page, "Iterations")).toContainText("5");
  await expect(kpi(page, "Iterations")).toContainText("limit 1000");

  await expect(row(page, "m₂/m₁")).toContainText("band mass ratio");
  await expect(row(page, "m₂/m₁")).toContainText("0,5");
  await expect(row(page, "m₂/m₁")).toContainText("fitted");
  await expect(row(page, "E_g")).toContainText("0,08 eV");
  await expect(row(page, "N₁, N₂")).toContainText("1, 1");
  await expect(row(page, "N₁, N₂")).toContainText("fixed");
  await expect(row(page, "m₁")).toContainText("absolute mass");
  await expect(row(page, "m₁")).toContainText("needs R_H");

  // The design's stand-ins are gone.
  await expect(page.getByText("[N]")).toHaveCount(0);
  await expect(page.getByText(/synthetic/i)).toHaveCount(0);
});

test("known issues and bounds reached are named", async ({ page }) => {
  await openFit(page);
  await finishWith(page, {
    known_issues: ["dpb_loop_degeneracy"],
    at_bounds: ["band_gap"],
  });
  await toResults(page);

  await expect(
    page.getByText(/^Caution: With N₂\/N₁ other than 1/),
  ).toBeVisible();
  await expect(row(page, "E_g")).toContainText("at bound");
  await expect(row(page, "E_F")).not.toContainText("at bound");
});

test("a fit under way, or one that gave no values, has no summary", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await toResults(page);
  await expect(page.getByText(/^A fit is running/)).toBeVisible();

  await send(page, {
    type: "done",
    result: { ...RESULT, status: "failed", message: "x" },
  });
  await expect(page.getByText(/^The last fit gave no values/)).toBeVisible();
  await expect(table(page)).toHaveCount(0);
});

test("demo data say so on the results", async ({ page }) => {
  await stub(page);
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
  await page.goto("/fit?demo=1");
  await expect(page.getByRole("button", { name: "Details" })).toBeVisible();
  await finishWith(page);
  await toResults(page);

  await expect(page.getByText(/^Demo data · DPB/)).toBeVisible();
  await expect(page.getByText(/^Synthetic data, generated with/)).toBeVisible();
});

test("an RMSE that is on its way or failed says so, not that data are missing", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  // Every request waits, as the fit screen may still have one on its way.
  const pending: ((ok: boolean) => void)[] = [];
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", async (route) => {
    const ok = await new Promise<boolean>((resolve) => {
      pending.push(resolve);
    });
    await (ok
      ? route.fulfill({ json: { ...CALC, rmse: RMSE } })
      : route.fulfill({ status: 500, json: { code: "internal_error" } }));
  });
  await toResults(page);

  await expect(kpi(page, "RMSE S")).toContainText("calculating…");
  await expect(kpi(page, "RMSE S")).not.toContainText("needs measurements");
  await expect.poll(() => pending.length).toBeGreaterThan(0);
  for (const answer of pending) {
    answer(false);
  }

  await expect(kpi(page, "RMSE S")).toContainText("could not be calculated");
  await expect(
    page.getByText("The RMSE could not be calculated for the current values."),
  ).toBeVisible();
});

test("a change after the fit leaves no summary, for values it did not fit", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");
  await toResults(page);

  await expect(
    page.getByText(
      "No fit for the current values. Run one on the model fit page.",
    ),
  ).toBeVisible();
  await expect(table(page)).toHaveCount(0);
});

test("while the models load or fail, it says that, not that a fit gave nothing", async ({
  page,
}) => {
  await page.route("**/api/models", (route) =>
    route.fulfill({ status: 500, json: { code: "internal_error" } }),
  );
  await page.goto("/results");

  await expect(page.getByText(/^The models could not be loaded/)).toBeVisible();
  await expect(page.getByText(/gave no values/)).toHaveCount(0);
});

const logSteps = (page: Page) =>
  page.getByRole("list", { name: "Fit log" }).getByRole("listitem");

test("the fit log follows the stages of the mode and how the fit ended", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page, { iterations: 3 });
  await toResults(page);

  await expect(logSteps(page)).toHaveText([
    /^\dStart values\s*The values on the fit screen$/,
    /^\dFit to S\s*Finds m₂\/m₁, E_g, E_F, in each of 3 iterations$/,
    /^\dFit to ρ\s*Finds A, B, in each of 3 iterations$/,
    /^\dConverged\s*The fit met its stop rule, a change of at most 10 %, in iteration 3\.$/,
  ]);
});

test("a fit stopped by the user says where", async ({ page }) => {
  await openFit(page);
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await send(page, {
    type: "iteration",
    iteration: 2,
    parameters: { band_gap: 950 },
  });
  await page.getByRole("button", { name: "Stop" }).click();
  await toResults(page);

  await expect(logSteps(page).last()).toHaveText(
    /^\dStopped\s*Stopped by the user after iteration 2\.$/,
  );
});

test("a start from the neural net says which net", async ({ page }) => {
  await openFit(page, (opened) =>
    opened.route("**/api/guess", (route) =>
      route.fulfill({
        json: {
          status: "guess",
          net_range: { min_temperature_k: 300, max_temperature_k: 800 },
          prediction: { m_eff: 1.5, band_gap_k: 554, fermi_energy_k: 100 },
          start_values: { m_eff: 1.5, band_gap: 554, fermi_energy: 100 },
          warnings: [],
        },
      }),
    ),
  );
  await expect(
    page.locator('[data-slot="badge"]').filter({ hasText: /^Initial guess/ }),
  ).toBeVisible();
  await finishWith(page);
  await toResults(page);

  await expect(logSteps(page).first()).toHaveText(
    /^\dStart values\s*The neural net's guess, from its net for 300–800 K$/,
  );
});

// Each kind of curve, with flags the server would add for acPhDis.
const DERIVED: Record<string, Record<string, number[]>> = {
  chemical_potential: { chemical_potential_k: [-100, 0, 100] },
  electrical_conductivity: { electrical_conductivity_s_per_m: [1e5, 8e4, 6e4] },
  thermal_conductivity: { thermal_conductivity_w_per_m_k: [0.5, 1, 1.5] },
  seebeck_by_band: {
    seebeck_band_1_v_per_k: [2e-4, 3e-4, 2e-4],
    seebeck_band_2_v_per_k: [-1e-4, -1e-4, -5e-5],
  },
  carrier_concentration_by_band: {
    carrier_concentration_band_1_per_cm3: [1e19, 2e19, 3e19],
    carrier_concentration_band_2_per_cm3: [1e18, 2e18, 3e18],
  },
};
const SCALED = [
  "electrical_conductivity",
  "thermal_conductivity",
  "seebeck_by_band",
];

async function serveCurves(page: Page) {
  const kinds: string[] = [];
  await page.route("**/api/calc", (route) => {
    const body = route.request().postDataJSON() as {
      kind?: string;
      scattering: string | null;
    };
    const kind = body.kind ?? "measured";
    kinds.push(kind);
    return route.fulfill({
      json: {
        ...CALC,
        curves:
          kind === "measured"
            ? { ...CALC.curves, resistivity_ohm_m: [1e-5, 2e-5, 3e-5] }
            : DERIVED[kind],
        rmse: kind === "measured" ? RMSE : {},
        known_issues:
          body.scattering !== "acPhDis"
            ? []
            : SCALED.includes(kind)
              ? ["acphdis_curve_scale"]
              : // On the total of S, and on R_H, which no additional graph draws.
                kind === "measured"
                ? ["acphdis_band_weight"]
                : [],
      },
    });
  });
  return kinds;
}

const graph = (page: Page, name: string) =>
  page.getByRole("region", { name: "Additional graphs" }).getByRole("region", {
    name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`),
  });

test("the additional graphs draw each curve the mode offers", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);

  for (const name of [
    "Chemical potential μ(T)",
    "Conductivity σ(T)",
    "Thermal conductivity κ_e(T)",
    "Band contributions",
    "Carrier concentration by band",
  ]) {
    await expect(
      graph(page, name).locator(".scatterlayer .trace path.js-line").first(),
    ).toBeVisible();
  }
  await expect(graph(page, "Thermal conductivity")).toContainText(
    "The electronic part only",
  );
  // DPB S + ρ has no R_H data to size n.
  await expect(graph(page, "Carrier concentration")).toContainText(
    "uses m₁ = 1",
  );
  await expect(page.getByText("unreliable")).toHaveCount(0);
});

test("with acPhDis, σ, κ_e and S by band are flagged as unreliable", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /acPhDis/ }).click();
  await finishWith(page);
  await toResults(page);

  for (const name of [
    "Conductivity σ(T)",
    "Thermal conductivity",
    "Band contributions",
  ]) {
    await expect(
      graph(page, name).getByRole("heading").getByText("unreliable").first(),
    ).toBeVisible();
    await expect(graph(page, name)).toContainText(
      /Unreliable: With acPhDis, σ, κ and S by band use another scale/,
    );
  }
  await expect(
    graph(page, "Chemical potential").getByText("unreliable"),
  ).toHaveCount(0);
  // The total of S drawn with the bands has its own flag, and σ, which does not draw it, has not.
  await expect(graph(page, "Band contributions")).toContainText(
    "Unreliable: With acPhDis, the band weight of the last temperature applies to all of S.",
  );
  await expect(graph(page, "Conductivity σ(T)")).not.toContainText(
    "band weight of the last temperature",
  );
  await expect(graph(page, "Band contributions")).not.toContainText(
    "DPB R_H is half",
  );
});

test("in S mode, the graphs that need ρ say so, and nothing is asked for them", async ({
  page,
}) => {
  let kinds: string[] = [];
  await openFit(page, async (opened) => {
    kinds = await serveCurves(opened);
  });
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await finishWith(page);
  await toResults(page);

  for (const name of ["Conductivity σ(T)", "Thermal conductivity"]) {
    await expect(graph(page, name)).toContainText("Needs ρ(T)");
  }
  // A graph the mode does not offer has nothing to download.
  await expect(
    page.getByRole("button", {
      name: "Download the data of Conductivity σ(T)",
    }),
  ).toBeDisabled();
  // Once the others are drawn, their requests are all out.
  await expect(
    graph(page, "Chemical potential")
      .locator(".scatterlayer .trace path.js-line")
      .first(),
  ).toBeVisible();
  await page.waitForTimeout(400);
  expect(kinds).not.toContain("electrical_conductivity");
  expect(kinds).not.toContain("thermal_conductivity");
});

async function downloaded(page: Page, button: string): Promise<string> {
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: button }).click(),
  ]);
  const path = await file.path();
  return readFileSync(path, "utf8");
}

test("Data to file has the data, and the curves before and after the fit", async ({
  page,
}) => {
  const bodies: { parameters: Record<string, number> }[] = [];
  await openFit(page, (opened) =>
    opened.route("**/api/calc", (route) => {
      const body = route.request().postDataJSON() as {
        kind?: string;
        parameters: Record<string, number>;
      };
      if (body.kind === undefined) {
        bodies.push(body);
      }
      return route.fulfill({
        json: {
          ...CALC,
          curves: {
            seebeck_v_per_k: [1e-4, 2e-4, 3e-4],
            resistivity_ohm_m: [1e-5, 2e-5, 3e-5],
          },
          rmse: RMSE,
        },
      });
    }),
  );
  await finishWith(page);
  await toResults(page);

  bodies.length = 0;
  const file = (await inFormat(page, "Text")).toString("utf8");
  const lines = file.split("\n");
  expect(lines[0]).toMatch(/^# SeeBand Web /);
  expect(lines).toContain("# Model DPB, fit mode S + ρ");
  expect(lines).toContain("# Fit converged, 5 iterations");
  const legends = lines.find((line) => line.startsWith("Temperature"));
  expect(legends?.split("\t")).toEqual([
    "Temperature [K]",
    "Experimental Seebeck coefficient [V/K]",
    "Temperature [K]",
    "Pre-fit Seebeck coefficient [V/K]",
    "Temperature [K]",
    "Fit Seebeck coefficient [V/K]",
    "Temperature [K]",
    "Experimental electrical resistivity [Ohm*m]",
    "Temperature [K]",
    "Pre-fit electrical resistivity [Ohm*m]",
    "Temperature [K]",
    "Fit electrical resistivity [Ohm*m]",
  ]);
  // The curve before the fit is of the values it started from, E_g = 1000 K by default, and the
  // other of the fitted ones.
  // The page's own live curve may ask once more for the fitted values.
  expect(new Set(bodies.map(({ parameters }) => parameters.band_gap))).toEqual(
    new Set([1000, 900]),
  );
});

test("Parameters to file has each value, its unit and how it was found", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page, { at_bounds: ["band_gap"] });

  // From the fit screen, as from the results.
  const file = (await inFormat(page, "Text", "Parameters to file")).toString(
    "utf8",
  );
  const lines = file.split("\n");
  expect(lines).toContain("Parameter\tValue\tStatus");
  expect(lines).toContain(
    "E_g (position of band 2) [eV]\t0.077555999358\tfitted, at bound",
  );
  expect(lines).toContain("N1, N2 (band degeneracies)\t1, 1\tfixed");

  const csv = (
    await inFormat(page, "CSV, one table", "Parameters to file")
  ).toString("utf8");
  expect(csv.split("\n")).toContain(
    'band_gap,E_g,position of band 2,eV,0.077555999358,"fitted, at bound"',
  );
});

test("each additional graph downloads its own curves and flags", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /acPhDis/ }).click();
  await finishWith(page);
  await toResults(page);
  await expect(
    graph(page, "Band contributions")
      .locator(".scatterlayer .trace path.js-line")
      .first(),
  ).toBeVisible();

  const file = await downloaded(
    page,
    "Download the data of Band contributions",
  );
  const lines = file.split("\n");
  expect(lines).toContain(
    "# Unreliable: With acPhDis, the band weight of the last temperature applies to all of S. (acphdis_band_weight)",
  );
  expect(
    lines.find((line) => line.startsWith("Temperature"))?.split("\t"),
  ).toEqual([
    "Temperature [K]",
    "Total Seebeck coefficient [V/K]",
    "Seebeck coefficient of band 1 [V/K]",
    "Seebeck coefficient of band 2 [V/K]",
  ]);
});

test("μ downloads in eV, as the screen shows it", async ({ page }) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);
  await expect(
    graph(page, "Chemical potential μ(T)")
      .locator(".scatterlayer .trace path.js-line")
      .first(),
  ).toBeVisible();

  const file = await downloaded(
    page,
    "Download the data of Chemical potential μ(T)",
  );
  const rows = file
    .split("\n")
    .filter((line) => line !== "" && !line.startsWith("#"));
  // From -100, 0 and 100 K.
  expect(rows[0]).toBe("Temperature [K]\tChemical potential [eV]");
  expect(rows.slice(1).map((row) => row.split("\t")[1])).toEqual([
    "-0.008617333262",
    "0",
    "0.008617333262",
  ]);
});

test("a failed export says so, and downloads nothing", async ({ page }) => {
  await openFit(page);
  await finishWith(page);
  await toResults(page);
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", (route) =>
    route.fulfill({ status: 500, json: { code: "internal_error" } }),
  );
  let downloads = 0;
  page.on("download", () => {
    downloads += 1;
  });

  await page.getByRole("button", { name: "Data to file" }).click();
  await page.getByRole("button", { name: "Download" }).click();

  await expect(
    page.getByText(
      "The file could not be made, as the server did not answer. Try again.",
    ),
  ).toBeVisible();
  expect(downloads).toBe(0);
});

/** An export, in a format chosen in its dialog. */
async function inFormat(
  page: Page,
  format: string,
  button = "Data to file",
): Promise<Buffer> {
  await page.getByRole("button", { name: button }).click();
  await page.getByRole("radio", { name: new RegExp(`^${format}`) }).click();
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download" }).click(),
  ]);
  return readFileSync(await file.path());
}

test("Data to file also gives a CSV, and a ZIP of plain tables", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);

  const csv = (await inFormat(page, "CSV, one table")).toString("utf8");
  expect(csv).toContain("\nquantity,curve,temperature_k,value,unit\n");
  expect(csv).toMatch(/\nseebeck,fit,100,0\.0001,V\/K\n/);

  const zip = unzipSync(
    new Uint8Array(await inFormat(page, "ZIP, a file each")),
  );
  expect(Object.keys(zip)).toEqual(
    expect.arrayContaining([
      "metadata.txt",
      "parameters.txt",
      "data/seebeck.txt",
      "data/resistivity.txt",
      "curves/pre-fit.txt",
      "curves/fit.txt",
      "graphs/chemical_potential.txt",
      "graphs/carrier_concentration_by_band.txt",
    ]),
  );
  expect(strFromU8(zip["data/seebeck.txt"] ?? new Uint8Array())).toMatch(
    /\nT \[K\]\tS \[V\/K\]\n/,
  );
});

test("the dialog of Data to file starts on text, says what each format is, and closes", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Data to file" }).click();

  const dialog = page.getByRole("dialog", { name: "Data to file" });
  await expect(dialog.getByRole("radio")).toHaveCount(3);
  await expect(dialog.getByRole("radio", { name: /^Text/ })).toBeChecked();
  await expect(
    dialog.getByRole("radio", { name: /^CSV, one table/ }),
  ).toHaveAccessibleDescription(/for pandas or R/);
  await expect(dialog.getByText(/JSON/)).toHaveCount(0);

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Data to file" }),
  ).toBeFocused();
});

test("during a fit, the curve before it still comes from its start, and the file says it runs", async ({
  page,
}) => {
  // A curve that shows the E_g it was calculated with.
  await openFit(page, (opened) =>
    opened.route("**/api/calc", (route) => {
      const body = route.request().postDataJSON() as {
        parameters: Record<string, number>;
      };
      const gap = body.parameters.band_gap ?? 0;
      return route.fulfill({
        json: {
          ...CALC,
          curves: {
            seebeck_v_per_k: [gap, gap, gap],
            resistivity_ohm_m: [1, 1, 1],
          },
          rmse: RMSE,
        },
      });
    }),
  );
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await send(page, {
    type: "iteration",
    iteration: 2,
    parameters: { band_gap: 950 },
  });
  await expect(
    page.getByRole("textbox", { name: "E_g", exact: true }),
  ).toHaveValue("0,08");

  const lines = (await inFormat(page, "Text")).toString("utf8").split("\n");
  expect(lines).toContain(
    "# A fit is running, at iteration 2: no fitted curve yet",
  );
  const legends =
    lines.find((line) => line.startsWith("Temperature"))?.split("\t") ?? [];
  const preFit = legends.indexOf("Pre-fit Seebeck coefficient [V/K]");
  expect(legends).not.toContain("Fit Seebeck coefficient [V/K]");
  const first = lines[lines.indexOf(legends.join("\t")) + 1]?.split("\t") ?? [];
  expect(first[preFit]).toBe("1000");
});

test("a fit that ends while the server answers does not change the file's header", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  // The export's curves wait until the fit has ended.
  const held: (() => void)[] = [];
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", async (route) => {
    await new Promise<void>((resolve) => {
      held.push(resolve);
    });
    await route.fulfill({ json: { ...CALC, rmse: RMSE } });
  });

  await page.getByRole("button", { name: "Data to file" }).click();
  await page.getByRole("radio", { name: /^Text/ }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download" }).click();
  await expect.poll(() => held.length).toBeGreaterThan(0);
  await send(page, { type: "done", result: RESULT });
  await expect(page.getByRole("button", { name: "Run fit" })).toBeVisible();
  for (const release of held.splice(0)) {
    release();
  }
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", (route) =>
    route.fulfill({ json: { ...CALC, rmse: RMSE } }),
  );

  const lines = readFileSync(await (await download).path(), "utf8").split("\n");
  expect(lines).toContain("# A fit is running: no fitted curve yet");
  expect(lines).not.toContain("# Fit converged, 5 iterations");
});

test("Report (PDF) prints the results with each chart as a picture, and only them", async ({
  page,
}) => {
  await page.addInitScript(() => {
    (window as Window & { printed?: number }).printed = 0;
    window.print = () => {
      const counted = window as Window & { printed?: number };
      counted.printed = (counted.printed ?? 0) + 1;
    };
  });
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);

  await page.getByRole("button", { name: "Report (PDF)" }).click();
  await expect
    .poll(() =>
      page.evaluate(() => (window as Window & { printed?: number }).printed),
    )
    .toBe(1);

  // S and ρ of the mode, then the five additional graphs.
  // Hidden on screen, so by their text rather than their role.
  const pictures = page.locator('img[alt^="Chart: "]');
  await expect(pictures).toHaveCount(7);
  await expect(pictures.first()).toHaveAttribute(
    "src",
    /^data:image\/png;base64,/,
  );
  // Real pictures, at twice their printed size.
  expect(
    await pictures
      .first()
      .evaluate((picture: HTMLImageElement) => [
        picture.naturalWidth,
        picture.naturalHeight,
      ]),
  ).toEqual([720, 520]);
  const report = page.locator('section[aria-label="Charts"]');
  await expect(report).toContainText("Measurements · Model");
  await expect(report).toContainText(
    "Total S · band 1 contribution · band 2 contribution",
  );

  // On screen, the report's parts stay out of the way.
  await expect(report).toBeHidden();
  await expect(page.getByText("SeeBand Web report")).toBeHidden();

  await page.emulateMedia({ media: "print" });
  await expect(report).toBeVisible();
  await expect(page.getByText("SeeBand Web report")).toBeVisible();
  await expect(
    page.getByText(/^S: f0\.txt, 2 points, 100–200 K$/),
  ).toBeVisible();
  await expect(page.locator(".sb-header")).toBeHidden();
  await expect(page.getByRole("button", { name: "Report (PDF)" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Data to file" })).toBeHidden();
  await expect(
    page.getByRole("region", { name: "Additional graphs" }),
  ).toBeHidden();
  await expect(
    page.getByRole("table", { name: "Fit parameters" }),
  ).toBeVisible();
  await expect(page.getByRole("list", { name: "Fit log" })).toBeHidden();
  // A chart's note goes with it.
  await expect(report).toContainText("uses m₁ = 1");

  // After printing, the pictures go, as they would be of old values by the next print.
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(pictures).toHaveCount(0);
});

test("a report names each chart the mode does not draw, and why", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.print = () => undefined;
  });
  await openFit(page, serveCurves);
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await finishWith(page);
  await toResults(page);
  await page.getByRole("button", { name: "Report (PDF)" }).click();

  const report = page.locator('section[aria-label="Charts"]');
  await expect(page.locator('img[alt^="Chart: "]').first()).toBeAttached();
  await expect(report).toContainText(
    "Conductivity σ(T): not drawn. Needs ρ(T):",
  );
  await expect(report).toContainText(
    "Thermal conductivity κ_e(T): not drawn. Needs ρ(T):",
  );
});

test("a report that cannot be prepared says so, and prints nothing", async ({
  page,
}) => {
  await page.addInitScript(() => {
    (window as Window & { printed?: number }).printed = 0;
    window.print = () => {
      const counted = window as Window & { printed?: number };
      counted.printed = (counted.printed ?? 0) + 1;
    };
    // No picture can be made of a chart.
    HTMLCanvasElement.prototype.toDataURL = () => {
      throw new Error("no canvas");
    };
  });
  await openFit(page);
  await finishWith(page);
  await toResults(page);

  await page.getByRole("button", { name: "Report (PDF)" }).click();

  // Plotly never answers when a picture fails, so the report gives up after its wait.
  await expect(
    page.getByText("The report could not be prepared. Try again."),
  ).toBeVisible({ timeout: 15_000 });
  expect(
    await page.evaluate(
      () => (window as Window & { printed?: number }).printed,
    ),
  ).toBe(0);
});
