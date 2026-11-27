import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import type { components } from "@seeband/api-client";

test.skip(
  !process.env.SEEBAND_API_TARGET,
  "Requires the real API via SEEBAND_API_TARGET",
);

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (typeof value === "object" && value !== null)
    return `{${Object.entries(value)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`)
      .join(",")}}`;
  return JSON.stringify(value);
}

async function openSession(page: Page, buffer: Buffer) {
  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Open session" }).click(),
  ]);
  await chooser.setFiles({
    name: "historical.json",
    mimeType: "application/json",
    buffer,
  });
}

test("explicit CB+CB curves and confirmed historical conversion round-trip", async ({
  page,
}) => {
  await page.goto("/fit");
  await expect(page.getByText("Explicit bands · Fermi energy")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: /Carrier excess magnitude/ }),
  ).toHaveCount(0);
  const energy = page.getByRole("textbox", { name: "EF", exact: true });
  await expect(energy).toHaveValue("-0,01");
  await expect(
    page.getByRole("radiogroup", { name: "Carrier type" }),
  ).toHaveCount(0);
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("cb_cb");
  await expect(energy).toHaveValue("0,01");
  await page.getByRole("radio", { name: "S + ρ + RH", exact: true }).click();
  await expect(energy).toHaveValue("0,01");
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("vb_vb");
  await expect(energy).toHaveValue("0,08");
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("cb_cb");
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await energy.fill("0.02");
  await energy.press("Enter");
  const calculated = page.waitForResponse((response) => {
    if (!response.url().endsWith("/api/calc")) return false;
    const body = response
      .request()
      .postDataJSON() as components["schemas"]["CalcRequest"];
    return (
      body.band_configuration === "cb_cb" &&
      (body.parameters.fermi_energy ?? 0) > 0
    );
  });
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "synthetic-s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "T [K] S [V/K]\n100 -0.0001\n300 -0.0002\n800 -0.0003\n",
      ),
    });
  const response = await calculated;
  expect(response.ok()).toBe(true);
  const answer =
    (await response.json()) as components["schemas"]["CalcResponse"];
  expect(
    answer.curves.seebeck_v_per_k?.every(
      (value) => value !== null && value < 0,
    ),
  ).toBe(true);
  expect(response.request().postDataJSON()).toMatchObject({
    parameterization: "explicit_fermi_v1",
    band_configuration: "cb_cb",
  });
  expect(response.request().postDataJSON()).not.toHaveProperty(
    "net_electron_density_per_m3",
  );
  expect(response.request().postDataJSON()).not.toHaveProperty("carrier_type");
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("vb_cb");
  // Carrier choice does not invent the sign of a physical energy.
  await expect(energy).toHaveValue("0,02");
  const changedPolarity = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/calc") &&
      response.request().postDataJSON().parameters.fermi_energy < 0,
  );
  await energy.fill("-0.01");
  await energy.press("Enter");
  expect((await changedPolarity).ok()).toBe(true);
  await page.getByRole("button", { name: "Edit bounds" }).click();
  await expect(
    page.getByRole("textbox", { name: "EF, lower bound", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Done", exact: true }).click();

  const content = {
    dataMode: "separate",
    data: {},
    otherSource: null,
    singleFile: null,
    selection: {
      model: "dpb",
      fitMode: "dpb_s_rho",
      scattering: "acPh",
      band1Degeneracy: 2,
      band2Degeneracy: 6,
      minTemperatureK: 100,
      maxTemperatureK: 800,
    },
    parameters: {
      dpb_s_rho: { m_eff: 2, band_gap: 600, fermi_energy: 80 },
      dpb_s_rho_rh: { B: 1.07 },
    },
    guessedParameters: {},
    customBounds: {
      dpb_s_rho: { fermi_energy: { lower: 0, upper: 100 } },
      dpb_s_rho_rh: { B: { lower: 0.98, upper: 1.09 } },
    },
    held: { dpb_s_rho: ["fermi_energy"], dpb_s_rho_rh: ["B"] },
    interpolation: { enabled: false },
    chartPanels: ["seebeck", "resistivity", "hall", "band_diagram"],
    savedModelSettings: {},
    fitStart: { values: null, net: null, numerical: false },
    fit: null,
  };
  const historical = {
    format: "seeband-session",
    version: 1,
    saved: "2026-11-20T00:00:00Z",
    appVersion: "historical",
    apiVersion: null,
    checksum: createHash("sha256").update(canonical(content)).digest("hex"),
    content,
  };
  await openSession(page, Buffer.from(JSON.stringify(historical)));
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Convert historical DPB session" }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Confirm scale and convert" }),
  ).toBeDisabled();
  await dialog.getByLabel("Single-valley |m₁| (mₑ)").fill("1.7");
  await expect(dialog.getByRole("textbox").nth(1)).toHaveValue("2");
  await expect(dialog.getByRole("textbox").nth(2)).toHaveValue("6");
  await dialog
    .getByRole("button", { name: "Cancel", exact: true })
    .last()
    .click();
  await expect(energy).toHaveValue("-0,01");
  await openSession(page, Buffer.from(JSON.stringify(historical)));
  await dialog.getByLabel("Single-valley |m₁| (mₑ)").fill("1.7");
  await dialog
    .getByRole("button", { name: "Confirm scale and convert" })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Explicit bands · Fermi energy")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: /Carrier excess magnitude/ }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("radiogroup", { name: "Carrier excess polarity" }),
  ).toHaveCount(0);
  await expect(energy).toHaveValue("0,01");
  await expect(
    page.getByText(
      "Original historical session and fit (legacy parameterization)",
    ),
  ).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Session to file" }).first().click(),
  ]);
  const saved = readFileSync(await download.path());
  const file = JSON.parse(saved.toString()) as {
    version: number;
    content: {
      selection: {
        parameterization: string;
        netElectronDensityPerM3?: number;
        carrierType?: string;
        legacySource: string;
      };
      parameters: Record<string, Record<string, number>>;
      customBounds: object;
      held: object;
    };
  };
  expect(file.version).toBe(4);
  expect(file.content.selection.parameterization).toBe("explicit_fermi_v1");
  expect(file.content.selection.netElectronDensityPerM3).toBeUndefined();
  expect(file.content.selection.carrierType).toBeUndefined();
  expect(file.content.parameters.dpb_s_rho?.fermi_energy).toBe(80);
  expect(file.content.customBounds).toEqual({
    dpb_s_rho: { B: { lower: 0.9, upper: 1.1 } },
    dpb_s_rho_rh: { B: { lower: 0.98, upper: 1.09 } },
  });
  expect(file.content.held).toEqual({ dpb_s_rho_rh: ["B"] });
  expect(file.content.selection.legacySource).not.toContain('"data":');
  await openSession(page, saved);
  await expect(dialog).not.toBeVisible();
  await expect(energy).toHaveValue("0,01");
  await page.getByRole("radio", { name: "S + ρ + RH", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "B", exact: true }),
  ).toHaveValue("1,07");
  await expect(
    page.getByRole("button", { name: "Hold B at its value in a fit" }),
  ).toHaveAttribute("aria-pressed", "true");
  const massLock = page.getByRole("button", {
    name: "Hold m₁ at its value in a fit",
  });
  await expect(massLock).toHaveAttribute("aria-pressed", "true");
  await massLock.click();
  await expect(massLock).toHaveAttribute("aria-pressed", "false");
});

for (const sample of [
  { configuration: "vb_vb", offset: 0.06, energies: [0.03, 0.02] },
  { configuration: "cb_cb", offset: -0.06, energies: [-0.03, -0.02] },
  { configuration: "vb_cb", offset: 0.06, energies: [-0.02, 0.03, 0.08] },
  { configuration: "vb_cb", offset: -0.06, energies: [-0.05, -0.03, -0.01] },
]) {
  test(`manual EF explores both carrier signs and gap for ${sample.configuration}, offset ${sample.offset} eV`, async ({
    page,
  }) => {
    await page.goto("/fit");
    await page
      .getByLabel("Band configuration")
      .selectOption(sample.configuration);
    const energy = page.getByRole("textbox", { name: "EF", exact: true });
    const offset = page.getByRole("textbox", { name: "Δ", exact: true });
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles({
        name: "s.txt",
        mimeType: "text/plain",
        buffer: Buffer.from(
          "T [K] S [V/K]\n100 0.0001\n300 0.0002\n500 0.0003\n",
        ),
      });
    await expect(page.getByText(/^3 points/)).toBeVisible();
    await offset.fill(String(sample.offset));
    await offset.press("Enter");
    for (const value of sample.energies) {
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/calc") &&
          Math.abs(
            r.request().postDataJSON().parameters.fermi_energy *
              8.617333262e-5 -
              value,
          ) < 0.00001,
      );
      await energy.fill(String(value));
      await energy.press("Enter");
      const result = await response;
      expect(result.status()).toBe(200);
      expect(result.request().postDataJSON()).not.toHaveProperty(
        "carrier_type",
      );
      expect(
        (await result.json()).curves.seebeck_v_per_k.every(Number.isFinite),
      ).toBe(true);
      await expect(energy).toHaveAttribute("aria-invalid", "false");
    }
  });
}

test("old ionized S-only sessions replay unit B and a newly entered B survives export", async ({
  page,
}) => {
  await page.goto("/fit");
  const content = {
    dataMode: "separate",
    data: {},
    otherSource: null,
    singleFile: null,
    selection: {
      model: "dpb",
      fitMode: "dpb_s",
      scattering: "ionized",
      parameterization: "explicit_fermi_v1",
      bandConfiguration: "vb_cb",
      band1Degeneracy: 1,
      band2Degeneracy: 3,
      minTemperatureK: 100,
      maxTemperatureK: 800,
    },
    parameters: {
      dpb_s: {
        m1: 1,
        mass_ratio: 2,
        band_offset_k: 450,
        fermi_energy: 150,
        B: 9,
      },
    },
    guessedParameters: {},
    customBounds: {},
    held: {},
    interpolation: { enabled: false },
    chartPanels: ["seebeck", "band_diagram"],
    savedModelSettings: {},
    fitStart: { values: null, net: null, numerical: false },
    fit: null,
  };
  await openSession(
    page,
    Buffer.from(
      JSON.stringify({
        format: "seeband-session",
        version: 2,
        saved: "2026-11-20T00:00:00Z",
        appVersion: "old",
        apiVersion: null,
        content,
        checksum: createHash("sha256").update(canonical(content)).digest("hex"),
      }),
    ),
  );
  const field = page.getByRole("textbox", { name: "B", exact: true });
  await expect(field).toHaveValue("1");
  const prediction = (b: number) =>
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/calc") &&
        r.request().postDataJSON().fit_mode === "dpb_s" &&
        r.request().postDataJSON().parameters.B === b,
    );
  const unit = prediction(1);
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "seebeck.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "T [K] S [V/K]\n100 0.0001\n450 0.0002\n800 0.0003\n",
      ),
    });
  const baseline = await unit;
  expect(baseline.ok()).toBe(true);
  const edited = prediction(4);
  await field.fill("4");
  await field.press("Enter");
  const calculated = await edited;
  expect(calculated.ok()).toBe(true);
  expect((await calculated.json()).curves.seebeck_v_per_k).not.toEqual(
    (await baseline.json()).curves.seebeck_v_per_k,
  );
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Session to file" }).first().click(),
  ]);
  const saved = readFileSync(await download.path());
  expect(JSON.parse(saved.toString())).toMatchObject({
    version: 4,
    content: { parameters: { dpb_s: { B: 4 } } },
  });
  await openSession(page, saved);
  await expect(field).toHaveValue("4");
});

test("mixed transport drafts and locks survive S-only and session export", async ({
  page,
}) => {
  await page.goto("/fit");
  await expect(page.getByText("Explicit bands · Fermi energy")).toBeVisible();
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /acPhDis/ }).click();
  const c = page.getByRole("textbox", { name: "C", exact: true });
  const d = page.getByRole("textbox", { name: "D", exact: true });
  await c.fill("1.2");
  await c.press("Enter");
  await d.fill("1.4");
  await d.press("Enter");
  const lockC = page.getByRole("button", {
    name: "Hold C at its value in a fit",
  });
  const lockD = page.getByRole("button", {
    name: "Hold D at its value in a fit",
  });
  await lockC.click();
  await lockD.click();
  const prediction = page.waitForResponse((response) => {
    if (!response.url().endsWith("/api/calc")) return false;
    const body = response.request().postDataJSON();
    return (
      body.scattering === "acPhDis" &&
      body.parameters.C === 1.2 &&
      body.parameters.D === 1.4
    );
  });
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "synthetic-mixed-s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "T [K] S [V/K]\n100 0.0001\n300 0.0002\n800 0.0003\n",
      ),
    });
  expect((await prediction).ok()).toBe(true);
  await page.getByRole("radio", { name: "S", exact: true }).click();
  for (const name of ["A", "B", "C", "D"])
    await expect(page.getByRole("textbox", { name, exact: true })).toHaveCount(
      0,
    );
  await expect(
    page.getByRole("combobox", { name: "Scattering" }),
  ).toContainText("acPhDis");
  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await expect(c).toHaveValue("1,2");
  await expect(d).toHaveValue("1,4");
  await expect(lockC).toHaveAttribute("aria-pressed", "true");
  await expect(lockD).toHaveAttribute("aria-pressed", "true");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Session to file" }).first().click(),
  ]);
  const saved = readFileSync(await download.path());
  expect(JSON.parse(saved.toString())).toMatchObject({
    content: {
      selection: {
        scattering: "acPhDis",
        parameterization: "explicit_fermi_v1",
      },
      parameters: { dpb_s_rho: { C: 1.2, D: 1.4 } },
      held: { dpb_s_rho: ["C", "D"] },
    },
  });
  await openSession(page, saved);
  await expect(c).toHaveValue("1,2");
  await expect(d).toHaveValue("1,4");
  await expect(lockC).toHaveAttribute("aria-pressed", "true");
  await expect(lockD).toHaveAttribute("aria-pressed", "true");
});
