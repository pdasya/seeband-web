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
  const energy = page.getByRole("textbox", { name: "E_F", exact: true });
  await expect(energy).toHaveValue("-0,01");
  await page.getByRole("radio", { name: "n: electrons" }).click();
  await expect(energy).toHaveValue("0,09");
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("cb_cb");
  await expect(energy).toHaveValue("0,01");
  await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();
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
    carrier_type: "n",
  });
  expect(response.request().postDataJSON()).not.toHaveProperty(
    "net_electron_density_per_m3",
  );
  await expect(page.getByRole("radio", { name: "p: holes" })).toBeDisabled();
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("vb_cb");
  await page.getByRole("radio", { name: "p: holes" }).click();
  // Carrier choice does not invent the sign of a physical energy.
  await expect(energy).toHaveValue("0,02");
  const changedPolarity = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/calc") &&
      response.request().postDataJSON().carrier_type === "p" &&
      response.request().postDataJSON().parameters.fermi_energy < 0,
  );
  await energy.fill("-0.01");
  await energy.press("Enter");
  expect((await changedPolarity).ok()).toBe(true);
  const about = page.getByRole("button", { name: "About carrier type" });
  await about.hover();
  await expect(page.getByRole("tooltip")).toContainText("p means excess holes");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Edit bounds" }).click();
  await expect(
    page.getByRole("textbox", { name: "E_F, lower bound", exact: true }),
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
    parameters: { dpb_s_rho: { m_eff: 2, band_gap: 600, fermi_energy: 80 } },
    guessedParameters: {},
    customBounds: { dpb_s_rho: { fermi_energy: { lower: 0, upper: 100 } } },
    held: { dpb_s_rho: ["fermi_energy"] },
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
  const density = page.getByRole("textbox", {
    name: "Carrier excess magnitude |n − p| (m⁻³)",
  });
  await expect(
    page.getByText("Explicit bands · fixed carrier excess"),
  ).toBeVisible();
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
        netElectronDensityPerM3: number;
        legacySource: string;
      };
      customBounds: object;
      held: object;
    };
  };
  expect(file.version).toBe(2);
  expect(file.content.selection.parameterization).toBe("explicit_density_v1");
  expect(file.content.customBounds).toEqual({});
  expect(file.content.held).toEqual({});
  expect(file.content.selection.legacySource).not.toContain('"data":');
  await openSession(page, saved);
  await expect(dialog).not.toBeVisible();
  await expect(density).toHaveValue(
    String(Math.abs(file.content.selection.netElectronDensityPerM3)),
  );
  await page.getByRole("radio", { name: "S + ρ + R_H", exact: true }).click();
  const massLock = page.getByRole("button", {
    name: "Hold m₁ at its value in a fit",
  });
  await expect(massLock).toHaveAttribute("aria-pressed", "true");
  await massLock.click();
  await expect(massLock).toHaveAttribute("aria-pressed", "false");
});

test("VB+VB updates at positive offset and explains the hole threshold", async ({
  page,
}) => {
  await page.goto("/fit");
  await page.getByLabel("Band configuration").selectOption("vb_vb");
  const energy = page.getByRole("textbox", { name: "E_F", exact: true });
  const offset = page.getByRole("textbox", { name: "Δ", exact: true });
  const chart = page.getByRole("region", { name: "Chart 1", exact: true });
  const dispersion = page.getByRole("region", { name: "Chart 4", exact: true });
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "positive-s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "T [K] S [V/K]\n100 0.0001\n300 0.0002\n500 0.0003\n",
      ),
    });
  await offset.fill("0.06");
  await offset.press("Enter");
  const editEnergy = async (value: string) => {
    const calc = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/calc") &&
        Math.abs(
          r.request().postDataJSON().parameters.fermi_energy * 8.617333262e-5 -
            Number(value),
        ) < 0.0002,
    );
    const diagram = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/band-diagram") &&
        Math.abs(
          r.request().postDataJSON().parameters.fermi_energy * 8.617333262e-5 -
            Number(value),
        ) < 0.0002,
    );
    await energy.fill(value);
    await energy.press("Enter");
    return Promise.all([calc, diagram]);
  };
  const [valid] = await editEnergy("0.03");
  expect(valid.status()).toBe(200);
  expect(
    (await valid.json()).curves.seebeck_v_per_k.every(
      (s: number) => Number.isFinite(s) && s > 0,
    ),
  ).toBe(true);
  const [empty, geometry] = await editEnergy("0.10");
  expect(empty.status()).toBe(422);
  expect(geometry.status()).toBe(200);
  await expect(chart.getByRole("alert")).toContainText(
    "below the higher valence-band edge",
  );
  await expect(dispersion.getByRole("alert")).toHaveCount(0);
  const [recovered] = await editEnergy("0.02");
  expect(recovered.status()).toBe(200);
  await expect(chart.getByRole("alert")).toHaveCount(0);
});
