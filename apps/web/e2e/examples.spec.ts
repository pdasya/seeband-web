import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { components } from "@seeband/api-client";
import { strFromU8, unzipSync } from "fflate";

import { expect, test, type Page } from "@playwright/test";

import type { FitEvent } from "../src/api/fitStream";
import { chart, show, fitBadges } from "./support/fitScreen";

// Against a real API, as the mock's answers do not depend on the file. See the README.
test.skip(
  process.env.SEEBAND_API_TARGET === undefined,
  "Needs a real API, through SEEBAND_API_TARGET",
);

const slots = (page: Page) => page.locator("[data-file-slot]");

const EXAMPLES = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/",
    import.meta.url,
  ),
);

type Schemas = components["schemas"];

const SYMBOL_OF_SUFFIX = { see: "S", rho: "ρ", hall: "R_H" } as const;

/**
 * Chooses a file for the next empty slot, then names the quantity of its second column, which
 * loads it, as the examples have no header.
 */
async function loadExample(page: Page, name: string) {
  const suffix = /_(see|rho|hall)\.txt$/.exec(name)?.[1] as
    keyof typeof SYMBOL_OF_SUFFIX | undefined;
  if (suffix === undefined) {
    throw new Error(`No quantity in the name ${name}`);
  }
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles(`${EXAMPLES}${name}`);
  await page
    .getByRole("combobox", { name: "Quantity for column Column 2" })
    .click();
  await page
    .getByRole("option", { name: SYMBOL_OF_SUFFIX[suffix], exact: true })
    .click();
}

for (const example of ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]) {
  test(`all files of ${example} load`, async ({ page }) => {
    await page.goto("/fit");
    await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();

    const names = ["see", "rho", "hall"].map(
      (suffix) => `${example}_${suffix}.txt`,
    );
    for (const name of names) {
      // A slot with a file has no input, so the first input left is the next slot.
      await loadExample(page, name);
      await expect(slots(page).getByText(name)).toBeVisible();
    }

    await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
    for (const name of names) {
      await expect(slots(page).getByText(name)).toBeVisible();
    }
    await expect(
      slots(page).getByText(/\d+ points · .* K · V\/K/),
    ).toBeVisible();
    await expect(
      slots(page).getByText(/\d+ points · .* K · Ω·m/),
    ).toBeVisible();
    await expect(
      slots(page).getByText(/\d+ points · .* K · m³\/C/),
    ).toBeVisible();
  });
}

test("a desktop example, with no header and in SI, is marked as assumed and needs no unit check", async ({
  page,
}) => {
  const name = "01_Fe2VAl09Si01_see.txt";
  const firstLine = readFileSync(`${EXAMPLES}${name}`, "utf8").split("\n")[0];
  const [temperature, seebeck] = (firstLine ?? "").trim().split(/\s+/);
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await loadExample(page, name);

  const unitOfS = page.getByRole("combobox", {
    name: /^Unit of Seebeck coefficient/,
  });
  await expect(unitOfS).toHaveAccessibleName(
    "Unit of Seebeck coefficient: V/K, assumed",
  );
  await expect(page.getByText("Check the unit", { exact: true })).toHaveCount(
    0,
  );
  // The first row as the file writes it, which the real parser returns.
  await expect(
    page.getByText(`First row: T ${temperature} K · S ${seebeck} V/K`, {
      exact: true,
    }),
  ).toBeVisible();

  await unitOfS.click();
  await page.getByRole("option", { name: "V/K", exact: true }).click();
  await expect(unitOfS).toHaveAccessibleName("Unit of Seebeck coefficient");

  await page.getByRole("button", { name: "Hide" }).click();
  await expect(
    page.getByRole("region", { name: "Data" }).getByRole("listitem").first(),
  ).toHaveText(/^S · \d+ pts$/);
});

test("a broken file shows a specific error from the real parser", async ({
  page,
}) => {
  await page.goto("/fit");
  const good = readFileSync(`${EXAMPLES}01_Fe2VAl09Si01_see.txt`, "utf8");
  const lines = good.split("\n");
  lines[3] = "300 not-a-number";

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "broken.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(lines.join("\n")),
    });

  await expect(page.locator('[data-feedback="error"]')).toContainText(
    "broken.txt",
  );
  await expect(page.locator('[data-feedback="error"]')).toContainText("Line 4");
});

test("a ρ file in the S slot asks first, and says what its name names", async ({
  page,
}) => {
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles(`${EXAMPLES}03_AWI32_SI_rho.txt`);

  await expect(
    page.getByText(
      "This file has no column names. Choose what its columns hold.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByText("Its name suggests Resistivity.")).toBeVisible();
  await expect(fitBadges(page)).toHaveText("Missing data: S, ρ");
});

test("the real parser refuses a negative resistivity", async ({ page }) => {
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name: "rho.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T rho\n100 1e-5\n200 -2e-5\n300 3e-5\n"),
    });

  await expect(page.locator('[data-feedback="error"]')).toContainText(
    "Line 3: A resistivity below 0",
  );
});

test("a single file maps its columns through the real parser", async ({
  page,
}) => {
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
  const table =
    "T,S,rho\n100,1e-4,1e-5\n200,2e-4,2e-5\n300,3e-4,3e-5\n400,4e-4,4e-5\n500,5e-4,5e-5\n600,6e-4,6e-5\n";

  await page.locator('input[type="file"]').setInputFiles({
    name: "all.csv",
    mimeType: "text/plain",
    buffer: Buffer.from(table),
  });

  await expect(page.getByText("S · 6 points")).toBeVisible();
  await expect(page.getByText("ρ · 6 points")).toBeVisible();
  await expect(page.getByText("R_H · not found")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column rho" }).click();
  await page.getByRole("option", { name: "R_H", exact: true }).click();
  await expect(page.getByText("R_H · 6 points")).toBeVisible();
  await expect(page.getByText("ρ · not found")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "Ignore", exact: true }).click();
  await expect(page.locator('[data-feedback="error"]')).toContainText(
    "No column holds the temperature",
  );

  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "T", exact: true }).click();
  await expect(page.getByText("S · 6 points")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column rho" }).click();
  await page.getByRole("option", { name: "S", exact: true }).click();
  await expect(page.locator('[data-feedback="error"]')).toContainText(
    "assigned twice",
  );
});

test("interpolation of an example through the real API has its flags", async ({
  page,
}) => {
  await page.goto("/fit");
  // Its data run from 25 to 750 K, and the default range ends at 800 K.
  await loadExample(page, "01_Fe2VAl09Si01_see.txt");
  await expect(slots(page).getByText(/\d+ points/)).toBeVisible();

  const parsed = page.waitForResponse("**/api/parse");
  await page.getByRole("switch", { name: /Interpolation/ }).click();
  const response = await parsed;
  expect(response.ok()).toBe(true);
  const result = (await response.json()) as Schemas["ParseResponse"];
  const grid = result.interpolated.seebeck;
  if (!grid) throw new Error("Missing interpolated Seebeck data");
  expect(grid).toMatchObject({ range_limited: true, extrapolated: false });
  expect(Math.min(...grid.temperature_k)).toBe(50);
  expect(Math.max(...grid.temperature_k)).toBe(750);

  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
  await expect(page.locator('[data-feedback="error"]')).toContainText(
    "S: the measured range limits interpolation to 50–750 K",
  );

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
  await expect(
    slots(page).getByText("30 points · 25–750 K · V/K"),
  ).toBeVisible();
});

test("the SPB Hall mode is selectable and draws its calculated coefficient", async ({
  page,
}) => {
  await page.goto("/fit");

  await expect(page.getByRole("radio", { name: "DPB" })).toBeChecked();
  await expect(
    page.getByRole("radio", { name: "S + ρ", exact: true }),
  ).toBeChecked();

  await page.getByRole("radio", { name: "SPB" }).click();

  const hallMode = page.getByRole("radio", {
    name: "S + ρ + R_H",
    exact: true,
  });
  await hallMode.click();
  await expect(hallMode).toBeChecked();
  // Put the Fermi energy inside the default electron band.
  const fermi = page.getByRole("textbox", { name: "E_F", exact: true });
  await fermi.fill("0,02");
  await fermi.blur();
  const calculated = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/calc") &&
      response.request().postDataJSON().fit_mode === "spb_s_rho_rh",
  );
  await loadExample(page, "01_Fe2VAl09Si01_hall.txt");
  const response = await calculated;
  expect(response.ok()).toBe(true);
  const result = (await response.json()) as Schemas["CalcResponse"];
  const hall = result.curves.hall_m3_per_c ?? [];
  expect(result.temperature_k.length).toBeGreaterThan(1);
  expect(hall).toHaveLength(result.temperature_k.length);
  expect(
    hall.every(
      (value) => value !== null && Number.isFinite(value) && value < 0,
    ),
  ).toBe(true);
  await show(page, "Hall coefficient R_H(T)");
  await expect(
    chart(page).locator(".scatterlayer .trace path.js-line"),
  ).toBeVisible();
});

test("the real descriptions fill the parameters", async ({ page }) => {
  await page.goto("/fit");

  await expect(
    page.getByRole("textbox", { name: "E_F", exact: true }),
  ).toHaveValue("-0,01");
  await page.getByRole("radio", { name: "SPB" }).click();
  await expect(
    page.getByRole("slider", { name: "m", exact: true }),
  ).toHaveAttribute("aria-valuemin", "-3");
});

test("an example through the real API draws the curve, with its RMSE", async ({
  page,
}) => {
  await page.goto("/fit");
  await loadExample(page, "01_Fe2VAl09Si01_see.txt");

  await expect(page.getByText("RMSE, S")).toBeVisible();
  await expect(page.getByText(/^[\d,]+ µV\/K$/)).toBeVisible();
  await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
  const before = await page.getByText(/^[\d,]+ µV\/K$/).textContent();

  await page.getByRole("slider", { name: "E_F" }).press("PageUp");

  await expect(page.getByText(/^[\d,]+ µV\/K$/)).not.toHaveText(before ?? "");
});

test("a zero in resistivity does not stop the real API from answering", async ({
  page,
}) => {
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name: "rho.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "T rho\n100 1e-5\n150 0\n200 2e-5\n250 2e-5\n300 3e-5\n350 3e-5\n",
      ),
    });

  await expect(page.getByText("RMSE, ρ")).toBeVisible();
  await expect(page.getByText("ρ: points with a value of 0")).toBeVisible();
  await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
});

test("the charts draw real curves through the real API", async ({ page }) => {
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  const lines = chart(page).locator(".scatterlayer .trace path.js-line");

  await show(page, "Chemical potential μ(T)");
  await expect(lines).toHaveCount(1);
  await expect(chart(page).getByText("band 2 bottom (E_g)")).toBeVisible();

  await show(page, "Band contributions");
  await expect(lines).toHaveCount(3);

  await show(page, "Conductivity σ(T)");
  await expect(lines).toHaveCount(1);
  await expect(chart(page).locator(".ytitle")).toHaveText("σ, S/m");

  await page.getByRole("radio", { name: "SPB" }).click();
  await show(page, "Band contributions");
  await expect(chart(page).getByText("DPB only")).toBeVisible();
  await show(page, "Chemical potential μ(T)");
  await expect(lines).toHaveCount(1);
  await expect(chart(page).getByText("band edge")).toBeVisible();
  await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
});

// From `packages/seeband_core/tests/fixtures/neural_net_references.json`, recorded on the desktop:
// E_g 554 K and 1947 K, E_F 1170 K and -350 K, as eV shows them.
for (const [example, mass, gap, fermi] of [
  ["01_Fe2VAl09Si01", "1,57", "0,05", "0,1"],
  ["03_AWI32_SI", "1,22", "0,17", "-0,03"],
] as const) {
  test(`the net's start values for ${example} match the desktop`, async ({
    page,
  }) => {
    await page.goto("/fit");
    await loadExample(page, `${example}_see.txt`);
    const field = (name: string) =>
      page.getByRole("textbox", { name, exact: true });

    await expect(field("m₂/m₁")).toHaveValue(mass);
    await expect(field("E_g")).toHaveValue(gap);
    await expect(field("E_F")).toHaveValue(fermi);
    await expect(
      page
        .locator('[data-slot="badge"]')
        .filter({ hasText: /^Initial guess · net \d+–\d+ K$/ }),
    ).toBeVisible();
  });
}

test("02_SiP has no net for its span, and keeps the desktop's values", async ({
  page,
}) => {
  await page.goto("/fit");
  await loadExample(page, "02_SiP_see.txt");

  await expect(page.getByText(/No neural net covers/)).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "E_g", exact: true }),
  ).toHaveValue("0,09");
});

test("the real API draws the sketch of the bands, and it follows the values", async ({
  page,
}) => {
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  // The last chart shows it from the start.
  await expect(chart(page, 4).getByText("E_g = 0,09 eV")).toBeVisible();
  await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
  await expect(
    chart(page, 4).locator(".js-plotly-plot .scatterlayer .trace"),
  ).toHaveCount(3);

  const answered = page.waitForResponse("**/api/band-diagram");
  const field = page.getByRole("textbox", { name: "E_g", exact: true });
  // 0.04 eV, about 464 K.
  await field.fill("0,04");
  await field.blur();
  const response = await answered;
  const body = (await response.json()) as {
    curves: Record<string, number[]>;
  };
  expect(response.status()).toBe(200);
  expect(Math.min(...(body.curves.band_2_energy_k ?? []))).toBeGreaterThan(464);
  await expect(chart(page, 4).getByText("E_g = 0,04 eV")).toBeVisible();
});

/** Compare the visible result with the terminal event of the same real fit. */
async function runVerifiedFit(page: Page) {
  // Chromium does not retain fetch-event-stream bodies for response.text(). Read a
  // clone in the page so the application still consumes its original stream live.
  const capture = await page.evaluateHandle(() => {
    const body = new Promise<string>((resolve, reject) => {
      const originalFetch = window.fetch;
      window.fetch = (input, init) => {
        const response = originalFetch.call(window, input, init);
        const url = input instanceof Request ? input.url : String(input);
        if (new URL(url, location.href).pathname === "/api/fit") {
          window.fetch = originalFetch;
          void response.then((res) => res.clone().text()).then(resolve, reject);
        }
        return response;
      };
    });
    return { body };
  });
  await page.getByRole("button", { name: "Run fit" }).click();
  const raw = await capture.evaluate(({ body }) => body);
  await capture.dispose();
  const last = raw
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .at(-1);
  const event = JSON.parse(last?.slice(5) ?? "null") as FitEvent | null;
  if (event?.type !== "done")
    throw new Error(`Expected a completed fit, received ${last}`);
  const { result } = event;
  expect(result.algorithm).toBe("verified-sequential-v2");
  const labels = {
    converged: "Numerically settled",
    stalled: "Numerical fit stalled",
    iteration_limit: "Iteration limit reached",
  };
  if (result.status === "failed" || result.status === "stopped") {
    throw new Error(`Fit ended with ${result.status}: ${result.message ?? ""}`);
  }
  await expect(fitBadges(page)).toHaveText(labels[result.status]);
  return result;
}

// One after another, as the API limits the fits of a client, and all tests here are one client.
test.describe("real fits", () => {
  test.describe.configure({ mode: "serial" });

  test("a real fit can be stopped, shows the verified outcome and resets", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/fit");
    await loadExample(page, "01_Fe2VAl09Si01_see.txt");
    await expect(page.getByText(/^\d+ points/)).toBeVisible();
    await loadExample(page, "01_Fe2VAl09Si01_rho.txt");
    await expect(page.getByText(/^\d+ points/)).toHaveCount(2);
    const run = page.getByRole("button", { name: "Run fit" });
    const gap = page.getByRole("textbox", { name: "E_g", exact: true });

    const badge = (text: RegExp) =>
      page.locator('[data-slot="badge"]').filter({ hasText: text });

    // The net has set its start values from S, as on the desktop.
    await expect(gap).toHaveValue("0,05");

    // Stop before the first iteration updates the initial values.
    await run.click();
    await page.getByRole("button", { name: "Stop" }).click();
    await expect(badge(/^Stopped/)).toBeVisible();
    await expect(gap).toHaveValue("0,05");

    async function expectFittedGap(gapK: number | null | undefined) {
      if (gapK == null) throw new Error("Fit result is missing E_g");
      const displayedEv = Number((await gap.inputValue()).replace(",", "."));
      expect(displayedEv).toBeCloseTo(gapK * 8.617333262e-5, 2);
    }
    const joint = await runVerifiedFit(page);
    await expectFittedGap(joint.parameters.band_gap);
    await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
    // The result panel counts them, and shows the values the fit reached.
    const iterations = page
      .locator("dl > div")
      .filter({ hasText: "Iterations" });
    const parameters = page.getByRole("table", { name: "Parameters in use" });
    expect(joint.iterations).toBeGreaterThan(0);
    await expect(iterations).toHaveText(
      `Iterations${String(joint.iterations)}limit 1000`,
    );
    await expect(
      parameters.getByRole("row").filter({ hasText: /^E_g/ }),
    ).toContainText("-0,26 … 0,26");

    await page.getByRole("button", { name: "Reset" }).click();
    await expect(gap).toHaveValue("0,09");

    // The S-only mode has no outer iteration counter.
    await page.getByRole("radio", { name: "S", exact: true }).click();
    await expect(gap).toHaveValue("0,05");
    const single = await runVerifiedFit(page);
    await expectFittedGap(single.parameters.band_gap);
    await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
    await expect(iterations).toHaveCount(0);
  });

  test("the demo goes through the real API like a file: curve, interpolation and fit", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/fit?demo=1");
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
    await expect(
      page.locator("[data-file-slot]").getByText("Demo data"),
    ).toHaveCount(3);
    await expect(page.getByText(/^31 points/)).toHaveCount(3);
    await expect(chart(page).getByText("Measurements (demo)")).toBeVisible();

    // Its rows are sent again as text, and the real parser reads them.
    await page.getByRole("switch", { name: /Interpolation/ }).click();
    await expect(chart(page).getByText("Measurements (demo)")).toBeVisible();
    await expect(
      chart(page).getByText("Interpolated", { exact: true }),
    ).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
    await page.getByRole("switch", { name: /Interpolation/ }).click();

    await runVerifiedFit(page);
    await expect(page.locator('[data-feedback="error"]')).toHaveCount(0);
    await expect(page.getByText(/^Unreliable:/)).toHaveCount(0);
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
  });

  test("a ZIP of a real fit holds data and curves the real parser reads again", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/fit?demo=1");
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
    await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
    await runVerifiedFit(page);
    await page.getByRole("link", { name: "Results", exact: true }).click();
    // The fit screen has its own Data to file, so the results page must be open first.
    await expect(
      page.getByRole("heading", { level: 1, name: "Results", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Data to file" }).click();
    await page.getByRole("radio", { name: /^ZIP, a file each/ }).click();
    const [file] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download", exact: true }).click(),
    ]);
    const zip = unzipSync(new Uint8Array(readFileSync(await file.path())));

    for (const [name, expected, quantities] of [
      ["data/seebeck.txt", "seebeck", ["seebeck"]],
      ["data/resistivity.txt", "resistivity", ["resistivity"]],
      ["curves/fit.txt", "seebeck", ["seebeck", "resistivity"]],
    ] as const) {
      const answer = await page.request.post("/api/parse", {
        data: { text: strFromU8(zip[name] ?? new Uint8Array()), expected },
      });
      expect(answer.status(), name).toBe(200);
      const parsed = (await answer.json()) as {
        measurements: Record<string, { points: number }>;
        errors: unknown[];
      };
      expect(parsed.errors, name).toEqual([]);
      expect(Object.keys(parsed.measurements).sort(), name).toEqual(
        [...quantities].sort(),
      );
    }
    // The demo has 31 points of each.
    const again = await page.request.post("/api/parse", {
      data: {
        text: strFromU8(zip["data/seebeck.txt"] ?? new Uint8Array()),
        expected: "seebeck",
      },
    });
    expect(
      (
        (await again.json()) as {
          measurements: { seebeck: { points: number } };
        }
      ).measurements.seebeck.points,
    ).toBe(31);
  });

  test("a real fit stays inside bounds set by the user, and says so at the bound", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/fit?demo=1");
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
    await page.getByRole("radio", { name: "S", exact: true }).click();
    const gap = page.getByRole("textbox", { name: "E_g", exact: true });
    await gap.fill("0,09");
    await gap.blur();
    await page.getByRole("button", { name: "Edit bounds" }).click();

    // The data were made with a gap of 800 K, so a fit is held off from there: 0.08 eV is about 928 K.
    await page.getByRole("textbox", { name: "E_g, lower bound" }).fill("0,08");
    await page.getByRole("textbox", { name: "E_g, upper bound" }).fill("0,1");
    await page.getByRole("button", { name: "Done" }).click();
    await runVerifiedFit(page);

    await expect(gap).toHaveValue("0,08");
    const row = page
      .getByRole("table", { name: "Parameters in use" })
      .getByRole("row")
      .filter({ hasText: /^E_g/ });
    await expect(row).toContainText("0,08 … 0,1");
    await expect(row.getByText("at bound")).toBeVisible();
  });
});
