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
  await expect(
    page.getByText("Explicit bands · fixed carrier excess"),
  ).toBeVisible();
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("cb_cb");
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
  const density = page.getByRole("textbox", {
    name: "Carrier excess magnitude |n − p| (m⁻³)",
  });
  await density.fill("2e24");
  const calculated = page.waitForResponse((response) => {
    if (!response.url().endsWith("/api/calc")) return false;
    const body = response
      .request()
      .postDataJSON() as components["schemas"]["CalcRequest"];
    return (
      body.band_configuration === "cb_cb" &&
      body.net_electron_density_per_m3 === 2e24
    );
  });
  await density.press("Enter");
  const response = await calculated;
  expect(response.ok()).toBe(true);
  const answer =
    (await response.json()) as components["schemas"]["CalcResponse"];
  expect(
    answer.curves.seebeck_v_per_k?.every(
      (value) => value !== null && value < 0,
    ),
  ).toBe(true);
  const plotted = page
    .getByRole("region", { name: "Chart 1", exact: true })
    .locator(".js-plotly-plot");
  await expect
    .poll(async () =>
      plotted.evaluate((element) => {
        const graph = element as HTMLElement & {
          data?: { mode?: string; y?: (number | null)[] }[];
        };
        const values = (graph.data ?? [])
          .filter((trace) => trace.mode === "lines")
          .flatMap((trace) => trace.y ?? [])
          .filter((value): value is number => value !== null);
        return values.length > 0 && values.every((value) => value < 0);
      }),
    )
    .toBe(true);
  expect(response.request().postDataJSON()).toMatchObject({
    parameterization: "explicit_density_v1",
    band_configuration: "cb_cb",
    net_electron_density_per_m3: 2e24,
  });
  await expect(
    page.getByRole("button", { name: "Initial guess", exact: true }),
  ).toBeDisabled();

  await expect(
    page.getByRole("radio", { name: "p: excess holes" }),
  ).toBeDisabled();
  await page
    .getByLabel("Band configuration", { exact: false })
    .selectOption("vb_cb");
  const changedPolarity = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/calc") &&
      response.request().postDataJSON().band_configuration === "vb_cb" &&
      response.request().postDataJSON().net_electron_density_per_m3 === -2e24,
  );
  await page.getByRole("radio", { name: "p: excess holes" }).click();
  expect((await changedPolarity).ok()).toBe(true);
  await expect(density).toHaveValue("2e+24");
  await expect(page.getByText("n − p = −2e+24 m⁻³ (p)")).toBeVisible();
  const about = page.getByRole("button", { name: "About carrier excess" });
  await about.hover();
  await expect(page.getByRole("tooltip")).toContainText(
    "vary with temperature",
  );
  await page.getByRole("heading", { name: "Parameters", exact: true }).hover();
  await expect(page.getByRole("tooltip")).not.toBeVisible();
  await about.focus();
  await expect(page.getByRole("tooltip")).toContainText("per cubic metre");
  await page.keyboard.press("Escape");
  await about.click();
  await expect(page.getByRole("tooltip")).toContainText("VB + VB");
  await page.getByRole("heading", { name: "Parameters", exact: true }).click();

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
  await expect(density).toHaveValue("2e+24");
  await openSession(page, Buffer.from(JSON.stringify(historical)));
  await dialog.getByLabel("Single-valley |m₁| (mₑ)").fill("1.7");
  await dialog
    .getByRole("button", { name: "Confirm scale and convert" })
    .click();
  await expect(dialog).not.toBeVisible();
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
