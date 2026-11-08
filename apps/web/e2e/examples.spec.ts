import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { chart, show } from "./support/fitScreen";

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

/** Chooses a file for the next empty slot, and loads it as chosen already, as the examples have no header. */
async function loadExample(page: Page, name: string) {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles(`${EXAMPLES}${name}`);
  await page.getByRole("button", { name: /^Load as / }).click();
}

for (const example of ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]) {
  test(`all files of ${example} load`, async ({ page }) => {
    await page.goto("/fit");

    for (const suffix of ["see", "rho", "hall"]) {
      const name = `${example}_${suffix}.txt`;
      // A slot with a file has no input, so the first input left is the next slot.
      await loadExample(page, name);
      await expect(slots(page).getByText(name)).toBeVisible();
    }

    await expect(page.getByRole("alert")).toHaveCount(0);
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

  await expect(page.getByRole("alert")).toContainText("broken.txt");
  await expect(page.getByRole("alert")).toContainText("Line 4");
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
  await expect(
    page.getByText("This fit mode needs data for S, ρ."),
  ).toBeVisible();
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

  await expect(page.getByRole("alert")).toContainText(
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
  await expect(page.getByRole("alert")).toContainText(
    "No column holds the temperature",
  );

  await page.getByRole("combobox", { name: "Quantity for column T" }).click();
  await page.getByRole("option", { name: "T", exact: true }).click();
  await expect(page.getByText("S · 6 points")).toBeVisible();

  await page.getByRole("combobox", { name: "Quantity for column rho" }).click();
  await page.getByRole("option", { name: "S", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("assigned twice");
});

test("interpolation of an example through the real API has its flags", async ({
  page,
}) => {
  await page.goto("/fit");
  // Its data run from 25 to 750 K, and the default range ends at 800 K.
  await loadExample(page, "01_Fe2VAl09Si01_see.txt");
  await expect(slots(page).getByText(/\d+ points/)).toBeVisible();

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.getByText("Fit range 50–800 K")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "S: the grid goes beyond the data",
  );

  await page.getByRole("switch", { name: /Interpolation/ }).click();

  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(
    slots(page).getByText("30 points · 25–750 K · V/K"),
  ).toBeVisible();
});

test("the real model descriptions fill the model panel", async ({ page }) => {
  await page.goto("/fit");

  await expect(page.getByRole("radio", { name: "DPB" })).toBeChecked();
  await expect(
    page.getByRole("radio", { name: "S + ρ", exact: true }),
  ).toBeChecked();

  await page.getByRole("radio", { name: "SPB" }).click();

  await expect(
    page.getByRole("radio", { name: "S + ρ + R_H", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText(/fails on the desktop/)).toBeVisible();
});

test("the real descriptions fill the parameters", async ({ page }) => {
  await page.goto("/fit");

  await expect(
    page.getByRole("textbox", { name: "E_F", exact: true }),
  ).toHaveValue("-100");
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
  await expect(page.getByRole("alert")).toHaveCount(0);
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
  await expect(page.getByRole("alert")).toHaveCount(0);
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
  await expect(page.getByRole("alert")).toHaveCount(0);
});

// From `packages/seeband_core/tests/fixtures/neural_net_references.json`, recorded on the desktop.
for (const [example, mass, gap, fermi] of [
  ["01_Fe2VAl09Si01", "1,57", "554", "1170"],
  ["03_AWI32_SI", "1,22", "1947", "-350"],
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
  ).toHaveValue("1000");
});

test("the real API draws the sketch of the bands, and it follows the values", async ({
  page,
}) => {
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  // The last chart shows it from the start.
  await expect(page.getByText(/^Caution: This is a sketch/)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(
    chart(page, 4).locator(".js-plotly-plot .scatterlayer .trace"),
  ).toHaveCount(3);

  const answered = page.waitForResponse("**/api/band-diagram");
  const field = page.getByRole("textbox", { name: "E_g", exact: true });
  await field.fill("500");
  await field.blur();
  const response = await answered;
  const body = (await response.json()) as {
    curves: Record<string, number[]>;
  };
  expect(response.status()).toBe(200);
  expect(Math.min(...(body.curves.band_2_energy_k ?? []))).toBeGreaterThan(500);
});

// One after another, as the API limits the fits of a client, and all tests here are one client.
test.describe("real fits", () => {
  test.describe.configure({ mode: "serial" });

  test("a real fit stops, converges and resets through the real API", async ({
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
    await expect(gap).toHaveValue("554");

    // A real fit takes about a second here, so a Stop can only come right at its start.
    await run.click();
    await page.getByRole("button", { name: "Stop" }).click();
    await expect(badge(/^Stopped/)).toBeVisible();
    await expect(gap).toHaveValue("554");

    // S + ρ is iterative, so its result counts them.
    await run.click();
    await expect(badge(/^Converged in \d+ iter\.$/)).toBeVisible({
      timeout: 30_000,
    });
    await expect(gap).not.toHaveValue("1000");
    await expect(page.getByRole("alert")).toHaveCount(0);
    // The result panel counts them, and shows the values the fit reached.
    const iterations = page
      .locator("dl > div")
      .filter({ hasText: "Iterations" });
    const parameters = page.getByRole("table", { name: "Parameters in use" });
    await expect(iterations).toContainText(/^Iterations\d+limit 1000$/);
    await expect(
      parameters.getByRole("row").filter({ hasText: /^E_g/ }),
    ).toContainText("-3000 … 3000");

    await page.getByRole("button", { name: "Reset" }).click();
    await expect(gap).toHaveValue("1000");

    // S is single-pass, so it ends with no counter, on values other than its start.
    await page.getByRole("radio", { name: "S", exact: true }).click();
    await expect(gap).toHaveValue("554");
    await run.click();
    await expect(badge(/^Converged$/)).toBeVisible({
      timeout: 30_000,
    });
    await expect(gap).not.toHaveValue("554");
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(iterations).toHaveCount(0);

    // acPhDis has known errors of both kinds, each beside what it is about.
    await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
    await page.getByRole("combobox", { name: "Scattering" }).click();
    await page.getByRole("option", { name: /acPhDis/ }).click();
    await run.click();
    await expect(badge(/^Converged in \d+ iter\.$/)).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByText(/^Unreliable: With acPhDis, this fit stops/),
    ).toBeVisible();
    await expect(
      page.getByText(/^Unreliable: With acPhDis, the band weight/),
    ).toBeVisible();
    await expect(
      page
        .locator("dl > div")
        .filter({ hasText: "RMSE, S" })
        .getByText("unreliable"),
    ).toBeVisible();
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
    await expect(page.getByText("Measurements (demo)")).toBeVisible();

    // Its rows are sent again as text, and the real parser reads them.
    await page.getByRole("switch", { name: /Interpolation/ }).click();
    await expect(page.getByText("Measurements (demo)")).toBeVisible();
    await expect(page.getByText("Interpolated", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("alert")).toHaveCount(0);
    await page.getByRole("switch", { name: /Interpolation/ }).click();

    await page.getByRole("button", { name: "Run fit" }).click();
    await expect(
      page.locator('[data-slot="badge"]').filter({ hasText: /^Converged/ }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText(/^Unreliable: DPB R_H is half/)).toBeVisible();
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
  });

  test("a real fit stays inside bounds set by the user, and says so at the bound", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/fit?demo=1");
    await expect(page.getByText(/^Synthetic data/)).toBeVisible();
    await page.getByRole("radio", { name: "S", exact: true }).click();
    const gap = page.getByRole("textbox", { name: "E_g", exact: true });
    await gap.fill("1000");
    await gap.blur();
    await page.getByRole("button", { name: "Edit bounds" }).click();

    // The data were made with a gap of 800 K, so a fit is held off from there.
    await page.getByRole("textbox", { name: "E_g, lower bound" }).fill("900");
    await page.getByRole("textbox", { name: "E_g, upper bound" }).fill("1100");
    await page.getByRole("button", { name: "Done" }).click();
    await page.getByRole("button", { name: "Run fit" }).click();
    await expect(
      page.locator('[data-slot="badge"]').filter({ hasText: /^Converged/ }),
    ).toBeVisible({ timeout: 30_000 });

    await expect(gap).toHaveValue("900");
    const row = page
      .getByRole("table", { name: "Parameters in use" })
      .getByRole("row")
      .filter({ hasText: /^E_g/ });
    await expect(row).toContainText("900 … 1100");
    await expect(row.getByText("at bound")).toBeVisible();
  });
});
