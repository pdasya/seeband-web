import { expect, test, type Page } from "@playwright/test";
import type { PlotlyHTMLElement } from "plotly.js";

import { chart, show } from "./support/fitScreen";

// Like examples.spec.ts, this exercises the real parser and calculation server.
test.skip(
  process.env.SEEBAND_API_TARGET === undefined,
  "Needs a real API, through SEEBAND_API_TARGET",
);

test.setTimeout(90_000);

/** Read the data owned by the rendered Plotly graph, rather than React state or API answers. */
async function traces(page: Page, index: number, mode: "lines" | "markers") {
  return chart(page, index)
    .locator(".js-plotly-plot")
    .evaluate((element, wanted) => {
      const graph = element as PlotlyHTMLElement;
      return graph.data
        .filter((trace) => "mode" in trace && trace.mode === wanted)
        .map((trace) => ({
          x: "x" in trace ? Array.from(trace.x as number[]) : [],
          y: "y" in trace ? Array.from(trace.y as (number | null)[]) : [],
        }));
    }, mode);
}

async function curves(page: Page) {
  return Promise.all([1, 2, 3].map((index) => traces(page, index, "lines")));
}

async function expectCurves(page: Page) {
  for (const index of [1, 2, 3]) {
    await expect
      .poll(async () => (await traces(page, index, "lines")).length)
      .toBe(1);
    const [line] = await traces(page, index, "lines");
    expect(line?.x.length).toBeGreaterThan(2);
    expect(line?.y).toHaveLength(line?.x.length ?? 0);
    expect(
      line?.y.every((value) => value !== null && Number.isFinite(value)),
    ).toBe(true);
    await expect(chart(page, index).locator("path.js-line")).toBeVisible();
  }
}

async function selectTransportCharts(page: Page) {
  await show(page, "Seebeck S(T)", 1);
  await show(page, "Resistivity ρ(T)", 2);
  await show(page, "Hall coefficient RH(T)", 3);
}

async function setParameter(page: Page, name: string, value: string) {
  const field = page.getByRole("textbox", { name, exact: true });
  await field.fill(value);
  await field.press("Enter");
}

test("fresh DPB transport curves respond to mass ratio and survive measurements pointwise", async ({
  page,
}) => {
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S + ρ + RH", exact: true }).click();
  await selectTransportCharts(page);
  await expectCurves(page);
  await expect(
    page.getByText("The RMSE appears here once measurements are loaded."),
  ).toBeVisible();
  const before = await curves(page);

  await setParameter(page, "m₂/m₁", "2");
  for (const index of [1, 2, 3]) {
    await expect
      .poll(() => traces(page, index, "lines"))
      .not.toEqual(before[index - 1]);
  }
  await expectCurves(page);
  const preview = await curves(page);

  // Synthetic measurements deliberately differ from the model; loading them only adds points/RMSE.
  const measurements = [
    {
      quantity: "seebeck",
      symbol: "S",
      header: "T S",
      values: [0.0001, 0.0002, 0.0003],
    },
    {
      quantity: "resistivity",
      symbol: "ρ",
      header: "T rho",
      values: [0.00001, 0.00002, 0.00003],
    },
    {
      quantity: "hall",
      symbol: "RH",
      header: "T RH",
      values: [-0.000001, -0.000002, -0.000003],
    },
  ];
  for (const [offset, measurement] of measurements.entries()) {
    const parsed = page.waitForResponse(
      (response) => response.url().endsWith("/api/parse") && response.ok(),
    );
    await page
      .locator(`[data-file-slot="${measurement.quantity}"] input[type="file"]`)
      .setInputFiles({
        name: `synthetic-${measurement.quantity}.txt`,
        mimeType: "text/plain",
        buffer: Buffer.from(
          `${measurement.header}\n${measurement.values.map((value, index) => `${String(100 + index * 100)} ${String(value)}`).join("\n")}\n`,
        ),
      });
    await parsed;
    await expect
      .poll(async () => (await traces(page, offset + 1, "markers"))[0]?.x)
      .toEqual([100, 200, 300]);
    await expect(chart(page, offset + 1)).toContainText("RMSE");
    expect(await curves(page)).toEqual(preview);
  }

  for (const measurement of measurements) {
    await page
      .getByRole("button", {
        name: `Remove file ${measurement.symbol}`,
        exact: true,
      })
      .click();
  }
  for (const index of [1, 2, 3]) {
    await expect.poll(() => traces(page, index, "markers")).toEqual([]);
    await expect(chart(page, index)).not.toContainText("RMSE");
  }
  await expectCurves(page);
  expect(await curves(page)).toEqual(preview);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

for (const branch of [
  { mass: "1", fermi: "0.01", sign: -1 },
  { mass: "-1", fermi: "-0.01", sign: 1 },
]) {
  test(`fresh SPB transport curves use the valid mass ${branch.mass} branch`, async ({
    page,
  }) => {
    await page.goto("/fit");
    await page.getByRole("radio", { name: "SPB", exact: true }).click();
    await page.getByRole("radio", { name: "S + ρ + RH", exact: true }).click();
    await setParameter(page, "m", branch.mass);
    await setParameter(page, "EF", branch.fermi);
    await selectTransportCharts(page);
    await expectCurves(page);
    await expect
      .poll(async () => {
        const [hall] = await traces(page, 3, "lines");
        return hall?.y.every(
          (value) => value !== null && Math.sign(value) === branch.sign,
        );
      })
      .toBe(true);
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}
