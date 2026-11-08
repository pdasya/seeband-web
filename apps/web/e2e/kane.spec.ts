import { spawn, type ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:8293";
let server: ChildProcess | undefined;
const fixture = JSON.parse(
  readFileSync(new URL("./support/kane-data.json", import.meta.url), "utf8"),
) as {
  tables: Record<string, string>;
};

test.beforeAll(async () => {
  const python = fileURLToPath(
    new URL("../../../.venv/bin/python", import.meta.url),
  );
  server = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "seeband_api.main:create_app",
      "--factory",
      "--host",
      "127.0.0.1",
      "--port",
      "8293",
      "--no-access-log",
    ],
    { stdio: "ignore" },
  );
  for (let attempt = 0; attempt < 100; attempt++) {
    const ready = await fetch(`${ORIGIN}/api/health`)
      .then((r) => r.ok)
      .catch(() => false);
    if (ready) return;
    if (server.exitCode !== null)
      throw new Error("The SKB integration API did not start");
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The SKB integration API did not become ready");
});

test.afterAll(async () => {
  if (server === undefined || server.exitCode !== null) return;
  const closed = new Promise<void>((resolve) =>
    server?.once("exit", () => resolve()),
  );
  server.kill("SIGTERM");
  const timeout = setTimeout(() => server?.kill("SIGKILL"), 5000);
  await closed;
  clearTimeout(timeout);
});

test("fits synthetic SKB series through the real API and draws L(T), mu(T), mobility and E(k)", async ({
  page,
}) => {
  test.setTimeout(60000);
  let fitResponseText = "";
  await page.route(
    /\/api\/(?:models|parse|fit|calc|guess|band-diagram)$/,
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      const response = await route.fetch({ url: `${ORIGIN}${path}` });
      if (path === "/api/fit") fitResponseText = await response.text();
      await route.fulfill({ response });
    },
  );
  await page.goto("/fit");
  await page.getByRole("radio", { name: "SKB", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "m", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("N₁", { exact: true })).toBeVisible();
  await expect(page.getByLabel("N₂", { exact: true })).toHaveCount(0);
  await page.getByRole("textbox", { name: "m", exact: true }).fill("0,2");
  await page.getByRole("textbox", { name: "m", exact: true }).blur();
  await page.getByRole("textbox", { name: "E_F", exact: true }).fill("250");
  await page.getByRole("textbox", { name: "E_F", exact: true }).blur();
  for (const [quantity, text] of Object.entries(fixture.tables)) {
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles({
        name: `synthetic-${quantity}.txt`,
        mimeType: "text/plain",
        buffer: Buffer.from(text),
      });
    await expect(
      page.getByText("synthetic-" + quantity + ".txt", { exact: true }),
    ).toBeVisible();
  }
  const run = page.getByRole("button", { name: "Run fit", exact: true });
  await expect(run).toBeEnabled();
  await run.click();
  await expect
    .poll(async () =>
      Number(
        (
          await page
            .getByRole("textbox", {
              name: "m",
              exact: true,
            })
            .inputValue()
        ).replace(",", "."),
      ),
    )
    .toBeCloseTo(0.16, 4);
  expect(fitResponseText).toContain('"converged"');

  const panel = page.getByRole("region", { name: "Chart 1", exact: true });
  const choose = async (name: string) => {
    await page
      .getByRole("combobox", { name: "Quantity shown in chart 1", exact: true })
      .click();
    await page.getByRole("option", { name, exact: true }).click();
  };
  await choose("L(T)");
  await expect(panel.locator(".ytitle")).toHaveText("L, 10⁻⁸ W Ω/K²");
  await expect(
    panel.locator(".scatterlayer path.js-line").first(),
  ).toBeVisible();
  await choose("Chemical potential μ(T)");
  await expect(panel.locator(".ytitle")).toHaveText("μ, K");
  await choose("Mobility");
  await expect(panel.locator(".scatterlayer .trace")).toHaveCount(2);
  await choose("E(k)");
  await expect(panel.locator(".xtitle")).toHaveText("k, Å⁻¹");
  await expect(panel.locator(".ytitle")).toHaveText("E − E_edge, eV");
  await expect(panel.locator(".scatterlayer .trace path.js-line")).toHaveCount(
    1,
  );
  await expect(
    panel.locator(".scatterlayer path.js-line").first(),
  ).toBeVisible();
  await expect(panel.locator(".xtick text").first()).toHaveText(/[−-]/);
});
