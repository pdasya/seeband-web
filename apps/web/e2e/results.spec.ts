import { readFileSync } from "node:fs";

import { strFromU8, unzipSync } from "fflate";

import { expect, test, type Page } from "@playwright/test";

import { fakeFit } from "./support/fakeFit";
import {
  CALC,
  DEMO,
  MODELS_WITH_SEEBECK_ISSUE,
  serveModels,
  SYNTHETIC_SEEBECK_ISSUE,
} from "./support/models";

const PARSED = (quantity: string) => ({
  headers: ["T", "x"],
  column_count: 2,
  row_count: 2,
  preview: [],
  preview_si: [],
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
  interpolation_failure_reasons: {},
});

const RESULT = {
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 },
  status: "converged",
  iterations: 5,
  parameter_errors: {},
  parameter_status: {
    m_eff: "estimated",
    band_gap: "estimated",
    fermi_energy: "estimated",
    A: "estimated",
    B: "estimated",
  },
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
  await expect(page.getByRole("slider", { name: "EF" })).toBeVisible();
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

// Inside the app, as a reload would start a new session. It waits for the page, as the fit
// screen has its own Data to file, which a test must not open on the way.
async function toResults(page: Page) {
  await page.getByRole("link", { name: "Results", exact: true }).click();
  await expect(page).toHaveURL(/\/results$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Results", exact: true }),
  ).toBeVisible();
}

const table = (page: Page) =>
  page.getByRole("table", { name: "Fit parameters" });
// The last cell of a row, which says how the fit found the parameter.
const statusOf = (page: Page, symbol: string) =>
  row(page, symbol).getByRole("cell").last();
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
    page
      .locator('[data-slot="badge"]')
      .filter({ hasText: /^Stopped by its rule/ }),
  ).toHaveText(
    "Stopped by its rule (each parameter changed by at most 10 % in the last iteration) in 5 iter.",
  );
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
  await expect(kpi(page, "RMSE RH")).toHaveCount(0);
  await expect(kpi(page, "Iterations")).toContainText("5");
  await expect(kpi(page, "Iterations")).toContainText("limit 1000");

  await expect(row(page, "m₂/m₁")).toContainText("band mass ratio");
  await expect(row(page, "m₂/m₁")).toContainText("0,5");
  await expect(row(page, "m₂/m₁")).toContainText("estimated");
  await expect(row(page, "Eg")).toContainText("0,08 eV");
  await expect(row(page, "N₁, N₂")).toContainText("1, 1");
  await expect(row(page, "N₁, N₂")).toContainText("fixed");
  await expect(row(page, "m₁")).toContainText("absolute mass");
  await expect(row(page, "m₁")).toContainText("needs RH");

  // The design's stand-ins are gone.
  await expect(page.getByText("[N]")).toHaveCount(0);
  await expect(page.getByText(/synthetic/i)).toHaveCount(0);
});

test("known issues and bounds reached are named", async ({ page }) => {
  await openFit(page);
  await page
    .getByRole("combobox", { name: "Fitting method" })
    .selectOption("legacy-sequential-v1");
  await finishWith(page, {
    algorithm: "legacy-sequential-v1",
    known_issues: ["dpb_loop_degeneracy"],
    at_bounds: ["band_gap"],
    parameter_status: { ...RESULT.parameter_status, band_gap: "at_bound" },
  });
  await toResults(page);

  // In the notes, and on each additional graph, as the issue is one of the fit's values.
  const caution = page.getByText(
    /^Caution: In the legacy method with N₂\/N₁ other than 1/,
  );
  await expect(caution).toHaveCount(7);
  await expect(
    page
      .getByRole("region", { name: "Additional graphs" })
      .getByText(/^Caution: In the legacy method with N₂\/N₁ other than 1/),
  ).toHaveCount(6);
  await expect(statusOf(page, "Eg")).toHaveText("at bound");
  await expect(row(page, "EF")).not.toContainText("at bound");
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

test("a failed Results curve explains the admissible Fermi energy", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page);
  await page.route("**/api/calc", (route) =>
    route.fulfill({
      status: 422,
      json: {
        code: "calculation_failed",
        message: "x",
        details: [
          {
            code: "chemical_potential_dpb_fermi_energy",
            message: "x",
            location: ["body", "parameters"],
          },
        ],
      },
    }),
  );
  await toResults(page);

  await expect(
    page
      .getByRole("region", { name: "Additional graphs" })
      .getByRole("alert")
      .filter({ hasText: "Set EF below the higher band edge, max(0, Eg)." })
      .first(),
  ).toBeVisible();
});

test("demo data say so on the results", async ({ page }) => {
  await stub(page);
  await page.route("**/api/demo", (route) => route.fulfill({ json: DEMO }));
  await page.goto("/fit?demo=1");
  await expect(page.getByText(/^Synthetic data/)).toBeVisible();
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
  // Every request waits until the answer is set, as the fit screen may still have one on its way,
  // and any later one gets the same answer.
  const pending: ((ok: boolean) => void)[] = [];
  const set: { ok?: boolean } = {};
  await page.unroute("**/api/calc");
  await page.route("**/api/calc", async (route) => {
    const ok =
      set.ok ??
      (await new Promise<boolean>((resolve) => {
        pending.push(resolve);
      }));
    await (ok
      ? route.fulfill({ json: { ...CALC, rmse: RMSE } })
      : route.fulfill({ status: 500, json: { code: "internal_error" } }));
  });
  await toResults(page);

  await expect(kpi(page, "RMSE S")).toContainText("calculating…");
  await expect(kpi(page, "RMSE S")).not.toContainText("needs measurements");
  await expect.poll(() => pending.length).toBeGreaterThan(0);
  set.ok = false;
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
  await page.getByRole("slider", { name: "Eg" }).press("ArrowRight");
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
  await page.route(/\/api\/models(?:\?.*)?$/, (route) =>
    route.fulfill({ status: 500, json: { code: "internal_error" } }),
  );
  await page.goto("/results");

  await expect(page.getByText(/^The models could not be loaded/)).toBeVisible();
  await expect(page.getByText(/gave no values/)).toHaveCount(0);
});

test("each parameter shows how the fit found it, and none in green", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page, {
    at_bounds: ["B"],
    parameter_status: {
      m_eff: "did_not_move",
      band_gap: "estimated",
      fermi_energy: "not_determined",
      A: "not_assessed",
      B: "at_bound",
    },
  });
  await toResults(page);

  await expect(statusOf(page, "m₂/m₁")).toHaveText(
    "did not move from its start",
  );
  await expect(statusOf(page, "Eg")).toHaveText("estimated");
  await expect(statusOf(page, "EF")).toHaveText("not determined by the data");
  await expect(statusOf(page, "A")).toHaveText("not assessed");
  await expect(statusOf(page, "B")).toHaveText("at bound");
  await expect(statusOf(page, "N₁, N₂")).toHaveText("fixed");
  const badges = table(page).locator('[data-slot="badge"]');
  for (const badge of await badges.all()) {
    await expect(badge).not.toHaveAttribute("data-variant", "success");
  }
  await expect(
    page.getByText(/The uncertainty of the values is not assessed\./),
  ).toBeVisible();
  // The stop rule, not "Converged", and not in green.
  const status = page
    .locator('[data-slot="badge"]')
    .filter({ hasText: /^Stopped by its rule/ });
  await expect(status).toHaveText(
    "Stopped by its rule (each parameter changed by at most 10 % in the last iteration) in 5 iter.",
  );
  await expect(status).not.toHaveAttribute("data-variant", "success");
});

test("the fit screen shows the warnings beside the values, as the results do", async ({
  page,
}) => {
  await openFit(page);
  await finishWith(page, {
    parameter_status: {
      ...RESULT.parameter_status,
      fermi_energy: "not_determined",
    },
  });

  const panel = page.getByRole("table", { name: "Parameters in use" });
  await expect(
    panel
      .getByRole("row", { name: /EF/ })
      .getByText("not determined by the data"),
  ).toBeVisible();
  // An estimated value gets no badge there, as the panel is narrow.
  await expect(panel.getByText("estimated")).toHaveCount(0);
  await expect(
    page.getByText(/The uncertainty of the values is not assessed\./),
  ).toBeVisible();
});

test("a fit stopped here assesses nothing, and a held value says so", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: RESULT.parameters,
  });
  await page.getByRole("button", { name: "Stop" }).click();
  await toResults(page);

  await expect(statusOf(page, "m₂/m₁")).toHaveText("not assessed");
  await expect(statusOf(page, "Eg")).toHaveText("not assessed");
});

test("two fits with other scattering compare side by side after a value changed", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page, {
    core_version: "0.3.0",
    parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50, A: 4e4, B: 1 },
  });
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: "Alloy disorder (dis)" }).click();
  await finishWith(page, {
    core_version: "0.3.1",
    parameters: { m_eff: 0.7, band_gap: 800, fermi_energy: -40, F: 3e4, G: 1 },
  });
  // A value changed: the current result ends, and the runs stay.
  await page.getByRole("textbox", { name: "EF", exact: true }).fill("-0,001");
  await page.getByRole("textbox", { name: "EF", exact: true }).press("Enter");
  await toResults(page);

  // The page names no result for the values now in use, and the runs apart from it.
  await expect(
    page.getByText(
      "No fit for the current values. Run one on the model fit page.",
    ),
  ).toBeVisible();
  const runs = page.getByRole("table", { name: "Runs compared" });
  await expect(runs).toBeVisible();
  await expect(
    page.getByText(
      /Only a run marked as the current result is the result of the values now on the fit screen/,
    ),
  ).toBeVisible();
  const cells = (label: string) =>
    runs.getByRole("row").filter({
      has: page.getByRole("cell", { name: label, exact: true }),
    });
  await expect(cells("Scattering")).toContainText("Acoustic phonons (acPh)");
  await expect(cells("Scattering")).toContainText("Alloy disorder (dis)");
  await expect(cells("Core version").getByRole("cell")).toHaveText([
    "Core version",
    "0.3.0",
    "0.3.1",
  ]);
  await expect(cells("m₂/m₁")).toContainText("0,5");
  await expect(cells("m₂/m₁")).toContainText("0,7");
  await expect(cells("RMSE S")).toContainText("111 µV/K");
  // A parameter of one scattering only is shown for that run alone.
  await expect(cells("F")).toContainText("–");
});

test("the run on screen is marked as the current result, and runs read in words", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: "Alloy disorder (dis)" }).click();
  await finishWith(page);
  await toResults(page);

  const runs = page.getByRole("table", { name: "Runs compared" });
  // Run B, the last, is the result now on screen; run A is not.
  await expect(runs.getByRole("columnheader").nth(2)).toContainText(
    "current result",
  );
  await expect(runs.getByRole("columnheader").nth(1)).not.toContainText(
    "current result",
  );
  await expect(runs.getByRole("columnheader").first()).toHaveText("Property");
  const status = runs.getByRole("row").filter({
    has: page.getByRole("cell", { name: "Status", exact: true }),
  });
  await expect(status).toContainText("Stopped by its rule");
  await expect(status).not.toContainText("converged");
  // Not on paper: the report is of the current result.
  await page.emulateMedia({ media: "print" });
  await expect(runs).toBeHidden();
});

test("runs fit to another range say that their points differ", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  // The data have points at 100 and 200 K, so a range from 150 K leaves one out.
  await page.getByLabel("Lower bound, K").fill("150");
  await page.getByLabel("Lower bound, K").blur();
  await finishWith(page);
  await toResults(page);

  await expect(
    page.getByText(/^These runs were fit to different points/),
  ).toBeVisible();
  const range = page
    .getByRole("table", { name: "Runs compared" })
    .getByRole("row")
    .filter({
      has: page.getByRole("cell", { name: "Fit range", exact: true }),
    });
  await expect(range).toContainText("50–800 K");
  await expect(range).toContainText("150–800 K");
});

const logSteps = (page: Page) =>
  page.getByRole("list", { name: "Fit log" }).getByRole("listitem");

test("the fit log follows the stages of the mode and how the fit ended", async ({
  page,
}) => {
  await openFit(page);
  await page
    .getByRole("combobox", { name: "Fitting method" })
    .selectOption("legacy-sequential-v1");
  await finishWith(page, { iterations: 3, algorithm: "legacy-sequential-v1" });
  await toResults(page);

  await expect(logSteps(page)).toHaveText([
    /^\dStart values\s*The values on the fit screen$/,
    /^\dFit to S\s*Finds m₂\/m₁, Eg, EF, in each of 3 iterations$/,
    /^\dFit to ρ\s*Finds A, B, in each of 3 iterations$/,
    /^\dStopped by its rule\s*The legacy fit met its stop rule: each parameter of its loop changed by at most 10 % in iteration 3\.$/,
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

// Synthetic curves; the measured response can carry an active warning for export tests.
const DERIVED: Record<string, Record<string, number[]>> = {
  chemical_potential: { chemical_potential_k: [-100, 0, 100] },
  electrical_conductivity: { electrical_conductivity_s_per_m: [1e5, 8e4, 6e4] },
  thermal_conductivity: { thermal_conductivity_w_per_m_k: [0.5, 1, 1.5] },
  lorenz_number: {
    lorenz_number_w_ohm_per_k2: [3e-8, 5e-8, 4e-8],
    lorenz_number_band_1_w_ohm_per_k2: [2e-8, 2.2e-8, 2.3e-8],
    lorenz_number_band_2_w_ohm_per_k2: [1.8e-8, 2e-8, 2.1e-8],
  },
  seebeck_by_band: {
    seebeck_band_1_v_per_k: [2e-4, 3e-4, 2e-4],
    seebeck_band_2_v_per_k: [-1e-4, -1e-4, -5e-5],
  },
  carrier_concentration_by_band: {
    carrier_concentration_band_1_per_cm3: [1e19, 2e19, 3e19],
    carrier_concentration_band_2_per_cm3: [1e18, 2e18, 3e18],
  },
};

async function serveCurves(page: Page) {
  await page.route(/\/api\/models(?:\?.*)?$/, (route) =>
    route.fulfill({ json: MODELS_WITH_SEEBECK_ISSUE }),
  );
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
          body.scattering !== "ionized"
            ? []
            : kind === "measured"
              ? [SYNTHETIC_SEEBECK_ISSUE.id]
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
    "Thermal conductivity κe(T)",
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
  await expect(graph(page, "Lorenz number")).toContainText("Total L");
  await expect(graph(page, "Lorenz number")).toContainText("L, 10⁻⁸ W·Ω·K⁻²");
  await expect(graph(page, "Lorenz number")).not.toContainText("L / L₀");
  // DPB S + ρ has no R_H data to size n.
  await expect(graph(page, "Carrier concentration")).toContainText(
    "uses m₁ = 1",
  );
  await expect(page.getByText("unreliable")).toHaveCount(0);
});

test("a measured S warning follows its total into the band graph", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /Ionized impurities/ }).click();
  await finishWith(page);
  await toResults(page);

  for (const name of [
    "Conductivity σ(T)",
    "Thermal conductivity",
    "Lorenz number",
  ]) {
    await expect(
      graph(page, name).getByText("unreliable", { exact: true }),
    ).toHaveCount(0);
  }
  await expect(
    graph(page, "Chemical potential").getByText("unreliable"),
  ).toHaveCount(0);
  // The total of S drawn with the bands has its own flag, and σ, which does not draw it, has not.
  await expect(graph(page, "Band contributions")).toContainText(
    "Unreliable: A known error applies to this result.",
  );
  await expect(graph(page, "Conductivity σ(T)")).not.toContainText(
    "A known error applies to this result.",
  );
  await expect(graph(page, "Band contributions")).not.toContainText(
    "DPB RH is half",
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

  for (const name of [
    "Conductivity σ(T)",
    "Thermal conductivity",
    "Lorenz number",
  ]) {
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
  expect(kinds).not.toContain("lorenz_number");
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
          core_version: "0.1.0",
          curves: {
            seebeck_v_per_k: [1e-4, 2e-4, 3e-4],
            resistivity_ohm_m: [1e-5, 2e-5, 3e-5],
          },
          rmse: RMSE,
        },
      });
    }),
  );
  await finishWith(page, { core_version: "0.0.0" });
  await toResults(page);

  bodies.length = 0;
  const file = (await inFormat(page, "Text")).toString("utf8");
  const lines = file.split("\n");
  expect(lines[0]).toMatch(/^# SeeBand Web /);
  expect(lines).toContain("# Model DPB, fit mode S + ρ");
  expect(lines).toContain("# Fit core 0.0.0");
  expect(lines).toContain("# Curve core 0.1.0");
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
  await finishWith(page, {
    at_bounds: ["band_gap"],
    parameter_status: { ...RESULT.parameter_status, band_gap: "at_bound" },
  });

  // From the fit screen, as from the results.
  const file = (await inFormat(page, "Text", "Parameters to file")).toString(
    "utf8",
  );
  const lines = file.split("\n");
  expect(lines).toContain("Parameter\tValue\tStatus");
  expect(lines).toContain(
    "E_g (position of band 2) [eV]\t0.077555999358\tat bound",
  );
  expect(lines).toContain("N1, N2 (band degeneracies)\t1, 1\tfixed");

  const csv = (
    await inFormat(page, "CSV, one table", "Parameters to file")
  ).toString("utf8");
  expect(csv.split("\n")).toContain(
    "band_gap,E_g,position of band 2,eV,0.077555999358,at bound",
  );
});

test("each additional graph downloads its own curves and flags", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /Ionized impurities/ }).click();
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
    "# Unreliable: A known error applies to this result. (synthetic_seebeck_issue)",
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
  await page
    .getByRole("dialog", { name: "Data to file", exact: true })
    .getByRole("button", { name: "Download", exact: true })
    .click();

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
    page
      .getByRole("dialog", { name: button, exact: true })
      .getByRole("button", { name: "Download", exact: true })
      .click(),
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

test("a ZIP of a fit with bounds of the user's holds them, the start values and the RMSE", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await page.getByRole("button", { name: "Edit bounds" }).click();
  await page
    .getByRole("textbox", { name: "Eg, lower bound", exact: true })
    .fill("0,05");
  await page
    .getByRole("textbox", { name: "Eg, upper bound", exact: true })
    .fill("0,12");
  await page.getByRole("button", { name: "Done" }).click();
  await finishWith(page);
  await toResults(page);

  const zip = unzipSync(
    new Uint8Array(await inFormat(page, "ZIP, a file each")),
  );
  const metadata = strFromU8(zip["metadata.txt"] ?? new Uint8Array());
  expect(metadata).toMatch(
    /\nBounds: [^\n]*E_g 0\.05 eV to 0\.12 eV \(set by the user\)/,
  );
  expect(metadata).toMatch(
    /\nStart values, from the values on the fit screen: m₂\/m₁ = /,
  );
  expect(metadata).toContain("\nRMSE S of the fitted curve: 111 µV/K\n");
  expect(metadata).toMatch(/^SeeBand Web \S+ \(commit [0-9a-f]{12}(-dirty)?\)/);
});

/** Opens a session file through the chooser of Open session, which leaves no input in the page. */
async function openSession(
  page: Page,
  file: { name: string; mimeType: string; buffer: Buffer },
) {
  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Open session" }).click(),
  ]);
  await chooser.setFiles(file);
}

test("a session saved to file opens in a new tab as it was, and fits again with the same inputs", async ({
  page,
}) => {
  await openFit(page);
  await page.getByRole("button", { name: "Edit bounds" }).click();
  await page
    .getByRole("textbox", { name: "Eg, lower bound", exact: true })
    .fill("0,05");
  await page
    .getByRole("textbox", { name: "Eg, upper bound", exact: true })
    .fill("0,12");
  await page.getByRole("button", { name: "Done" }).click();
  await finishWith(page);

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Session to file" }).first().click(),
  ]);
  expect(download.suggestedFilename()).toBe("seeband-session.json");
  const saved = readFileSync(await download.path());
  const file = JSON.parse(saved.toString("utf8")) as {
    format: string;
    fit: { request: Record<string, unknown> | null } | null;
  };
  expect(file.format).toBe("seeband-session");
  expect(file.fit?.request).not.toBeNull();

  const other = await page.context().newPage();
  await stub(other);
  await other.goto("/fit");
  await expect(other.getByRole("slider", { name: "EF" })).toBeVisible();
  await openSession(other, {
    name: "seeband-session.json",
    mimeType: "application/json",
    buffer: saved,
  });

  await expect(
    other.getByText(/^Opened from a session file saved /),
  ).toBeVisible();
  // The fit shows as it was, not run again.
  await expect(
    other
      .locator('[data-slot="badge"]')
      .filter({ hasText: /^Stopped by its rule/ }),
  ).toBeVisible();
  for (const name of ["m₂/m₁", "Eg", "EF"]) {
    await expect(other.getByRole("textbox", { name, exact: true })).toHaveValue(
      await page.getByRole("textbox", { name, exact: true }).inputValue(),
    );
  }

  await other.getByRole("button", { name: "Run fit" }).click();
  const bodies = await other.evaluate(() => window.fitTest.bodies);
  const again = bodies.at(-1) as unknown as Record<string, unknown>;
  const first = file.fit?.request ?? {};
  // The same inputs: everything but the start, which is now the fit's own values.
  for (const key of Object.keys(first).filter((key) => key !== "start")) {
    expect(again[key], key).toEqual(first[key]);
  }
  // The bounds the user set, in core units: 0,05 to 0,12 eV.
  const bounds = again.bounds as { band_gap: { lower: number; upper: number } };
  expect(bounds.band_gap.lower * 8.617333262e-5).toBeCloseTo(0.05, 10);
  expect(bounds.band_gap.upper * 8.617333262e-5).toBeCloseTo(0.12, 10);
});

test("a session cannot be opened while a fit runs", async ({ page }) => {
  await openFit(page);
  const open = page.getByRole("button", { name: "Open session" });
  await expect(open).toBeEnabled();
  await page.getByRole("button", { name: "Run fit" }).click();
  await send(page, { type: "started" });
  await expect(open).toBeDisabled();
  await send(page, { type: "done", result: RESULT });
  await expect(open).toBeEnabled();
});

test("a file that is not a session says so, and changes nothing", async ({
  page,
}) => {
  await openFit(page);
  await openSession(page, {
    name: "other.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"format":"other"}'),
  });
  await expect(
    page.getByText("This file is not a SeeBand session file."),
  ).toBeVisible();
  await expect(page.getByText(/^2 points/)).toHaveCount(2);
});

test("the ZIP holds the session too", async ({ page }) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);

  const zip = unzipSync(
    new Uint8Array(await inFormat(page, "ZIP, a file each")),
  );
  const session = JSON.parse(
    strFromU8(zip["seeband-session.json"] ?? new Uint8Array()),
  ) as { format: string };
  expect(session.format).toBe("seeband-session");
});

test("ZIP export respects occupied calculation slots and retries temporary admission limits", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page, { core_version: "fit-core" });
  await toResults(page);
  await expect(
    graph(page, "Chemical potential μ(T)")
      .locator(".scatterlayer .trace path.js-line")
      .first(),
  ).toBeVisible();

  let active = 0;
  let peak = 0;
  let rejected = 0;
  let first = true;
  const accepted: string[] = [];
  await page.route("**/api/calc", async (route) => {
    // The real per-client limit is four; three slots may belong to live Results curves.
    if (first || active + 3 >= 4) {
      first = false;
      rejected += 1;
      await route.fulfill({
        status: 429,
        headers: { "Retry-After": "1" },
        json: { code: "client_calc_limit", message: "Busy", details: [] },
      });
      return;
    }
    active += 1;
    peak = Math.max(peak, active);
    const { kind = "measured" } = route.request().postDataJSON() as {
      kind?: string;
    };
    accepted.push(kind);
    await new Promise((resolve) => setTimeout(resolve, 100));
    await route.fulfill({
      json: {
        ...CALC,
        core_version: "export-core",
        curves: kind === "measured" ? CALC.curves : DERIVED[kind],
        rmse: kind === "measured" ? RMSE : {},
      },
    });
    active -= 1;
  });

  const zip = unzipSync(
    new Uint8Array(await inFormat(page, "ZIP, a file each")),
  );
  expect(peak).toBe(1);
  expect(rejected).toBe(1);
  expect(accepted.filter((kind) => kind === "measured")).toHaveLength(2);
  for (const kind of Object.keys(DERIVED)) {
    expect(zip[`graphs/${kind}.txt`], kind).toBeDefined();
  }
  expect(zip["curves/pre-fit.txt"]).toBeDefined();
  expect(zip["curves/fit.txt"]).toBeDefined();
  const metadata = strFromU8(zip["metadata.txt"] ?? new Uint8Array());
  expect(metadata).toContain("Fit core fit-core");
  expect(metadata).toContain("Curve core export-core");
  expect(metadata).not.toContain("Not in this ZIP");
});

for (const status of [429, 503]) {
  test(`ZIP export stops after bounded retries of HTTP ${String(status)}`, async ({
    page,
  }) => {
    await openFit(page, serveCurves);
    await finishWith(page);
    await toResults(page);
    let attempts = 0;
    await page.route("**/api/calc", async (route) => {
      const { parameters } = route.request().postDataJSON() as {
        parameters: { band_gap: number };
      };
      // Only the export asks for the pre-fit values; live Results uses the fitted gap, 900 K.
      if (parameters.band_gap !== 1000) {
        await route.fallback();
        return;
      }
      attempts += 1;
      await route.fulfill({
        status,
        headers: { "Retry-After": "0" },
        json: { code: "server_busy", message: "Busy", details: [] },
      });
    });
    let downloads = 0;
    page.on("download", () => {
      downloads += 1;
    });
    await page.getByRole("button", { name: "Data to file" }).click();
    await page.getByRole("radio", { name: /^ZIP, a file each/ }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Download", exact: true })
      .click();
    await expect(
      page.getByText(
        "The file could not be made, as the server did not answer. Try again.",
      ),
    ).toBeVisible();
    expect(attempts).toBe(3);
    expect(downloads).toBe(0);
  });
}

test("ZIP export downloads nothing when an additional calculation fails", async ({
  page,
}) => {
  await openFit(page, serveCurves);
  await finishWith(page);
  await toResults(page);
  await page.route("**/api/calc", async (route) => {
    const { kind } = route.request().postDataJSON() as { kind?: string };
    if (kind !== "thermal_conductivity") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 500,
      json: { code: "internal_error", message: "Failed", details: [] },
    });
  });
  let downloads = 0;
  page.on("download", () => {
    downloads += 1;
  });
  await page.getByRole("button", { name: "Data to file" }).click();
  await page.getByRole("radio", { name: /^ZIP, a file each/ }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Download", exact: true })
    .click();
  await expect(
    page.getByText(
      "The file could not be made, as the server did not answer. Try again.",
    ),
  ).toBeVisible();
  expect(downloads).toBe(0);
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
    page.getByRole("textbox", { name: "Eg", exact: true }),
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
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Download", exact: true })
    .click();
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
  await finishWith(page, { core_version: "0.0.0" });
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
  await expect(page.getByText("Fit core 0.0.0", { exact: true })).toBeVisible();
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
    "Thermal conductivity κe(T): not drawn. Needs ρ(T):",
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
