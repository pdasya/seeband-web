import type { components } from "@seeband/api-client";
import { expect, test } from "@playwright/test";
import { chart, show } from "./support/fitScreen";

test.skip(!process.env.SEEBAND_API_TARGET, "Requires the real calculation API");

test("an intrinsic DPB keeps current S, resistivity and Hall points when its low-temperature Hall comparison fails", async ({
  page,
}) => {
  await page.goto("/fit");
  await page.getByRole("radio", { name: "S + ρ + RH" }).click();
  const edit = async (name: string, value: string) => {
    const field = page.getByRole("textbox", { name, exact: true });
    await field.fill(value);
    await field.blur();
  };
  await edit("Lower bound, K", "2");
  await edit("Upper bound, K", "300");
  await edit("m₂/m₁", "1,2");
  await edit("Eg", "0,25");
  const measuredResponse = () =>
    page.waitForResponse((response) => {
      if (!response.url().endsWith("/api/calc")) return false;
      const request = response
        .request()
        .postDataJSON() as components["schemas"]["CalcRequest"];
      return !request.kind && !!request.measurements?.hall;
    });
  const healthyResponse = measuredResponse();
  await page
    .locator('[data-file-slot="hall"] input[type="file"]')
    .setInputFiles({
      name: "hall.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T [K]\tRH [m³/C]\n2\t1e-8\n100\t2e-8\n300\t3e-8\n"),
    });
  const healthy = (await (
    await healthyResponse
  ).json()) as components["schemas"]["CalcResponse"];
  expect(healthy.curves.hall_m3_per_c?.every((value) => value !== null)).toBe(
    true,
  );
  const nextResponse = measuredResponse();
  await edit("EF", "0,12");
  const response = await nextResponse;
  expect(response.ok()).toBe(true);
  const next = (await response.json()) as components["schemas"]["CalcResponse"];
  expect(next.issues).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        scope: "curve",
        quantity: "hall_m3_per_c",
        temperature_k: expect.arrayContaining([2]),
      }),
      expect.objectContaining({ scope: "rmse", quantity: "hall" }),
    ]),
  );
  expect(next.rmse.hall?.value).toBeNull();
  expect(next.curves.hall_m3_per_c?.[0]).toBeNull();
  expect(Number.isFinite(next.curves.hall_m3_per_c?.at(-1))).toBe(true);
  expect(next.curves.seebeck_v_per_k).not.toEqual(
    healthy.curves.seebeck_v_per_k,
  );
  for (const [tab, name, factor] of [
    ["Seebeck S(T)", "seebeck_v_per_k", 1e6],
    ["Resistivity ρ(T)", "resistivity_ohm_m", 1e6],
    ["Hall coefficient RH(T)", "hall_m3_per_c", 1],
  ] as const) {
    await show(page, tab);
    const values = next.curves[name];
    if (!values) throw new Error("Missing API curve: " + name);
    const graph = chart(page).locator(".js-plotly-plot");
    await expect
      .poll(() =>
        graph.evaluate((element) => {
          const plot = element as HTMLElement & {
            data?: { name?: string; y?: (number | null)[] }[];
          };
          return plot.data?.find((trace) => trace.name === "Model")?.y;
        }),
      )
      .toEqual(values.map((value) => (value === null ? null : value * factor)));
  }
  await expect(
    chart(page)
      .getByText(/unavailable.*2.*K/i)
      .first(),
  ).toBeVisible();
});
