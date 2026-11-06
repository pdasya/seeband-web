import { expect, test, type Page, type Route } from "@playwright/test";

import { CALC, serveModels } from "./support/models";

interface CalcBody {
  model: string;
  fit_mode: string;
  scattering: string | null;
  parameters: Record<string, number>;
  min_temperature_k: number;
  max_temperature_k: number;
  extrapolated: boolean;
  measurements: Record<string, { temperature_k: number[]; values: number[] }>;
}

const PARSED = {
  column_count: 2,
  row_count: 3,
  preview: [],
  mapping: [],
  measurements: {
    seebeck: {
      temperature_k: [40, 100, 900],
      values: [1e-4, 2e-4, 3e-4],
      points: 3,
      min_temperature_k: 40,
      max_temperature_k: 900,
    },
  },
  errors: [],
  warnings: [],
  warnings_omitted: 0,
  interpolated: {},
  interpolation_failed: [],
};

const withRmse = (value: number | null) => ({
  ...CALC,
  rmse: { seebeck: { value, unit: "uV/K" } },
});

async function open(page: Page) {
  await serveModels(page);
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
}

async function load(page: Page) {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
}

/** Every calc request, answered by `answer`, in order. */
async function collect(
  page: Page,
  answer: (route: Route, index: number) => Promise<void> = (route) =>
    route.fulfill({ json: CALC }),
) {
  const bodies: CalcBody[] = [];
  await page.route("**/api/calc", (route) => {
    bodies.push(route.request().postDataJSON() as CalcBody);
    return answer(route, bodies.length - 1);
  });
  return bodies;
}

const eg = (page: Page) =>
  page.getByRole("slider", { name: "E_g", exact: true });
const modelLine = (page: Page) =>
  page.locator(".scatterlayer .trace path.js-line").first();

test("nothing is asked without data, and the empty state stays", async ({
  page,
}) => {
  await open(page);
  const bodies = await collect(page);

  await eg(page).press("ArrowRight");
  await page.waitForTimeout(500);

  expect(bodies).toHaveLength(0);
  await expect(page.getByText("No data yet")).toBeVisible();
  await expect(
    page.getByText("The RMSE appears here once measurements are loaded."),
  ).toBeVisible();
});

test("loaded data ask for a whole request, and draw the curve", async ({
  page,
}) => {
  await open(page);
  const bodies = await collect(page, (route) =>
    route.fulfill({ json: withRmse(108.43545) }),
  );

  await load(page);

  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0]).toMatchObject({
    model: "dpb",
    fit_mode: "dpb_s_rho",
    scattering: "acPh",
    min_temperature_k: 50,
    max_temperature_k: 800,
    band_1_degeneracy: 1,
    band_2_degeneracy: 1,
    extrapolated: false,
  });
  // Every parameter of the mode, also those of other scattering types.
  expect(Object.keys(bodies[0]?.parameters ?? {}).sort()).toEqual(
    ["A", "B", "C", "D", "F", "G", "band_gap", "fermi_energy", "m_eff"].sort(),
  );
  // Only points in the fit range, in V/K.
  expect(bodies[0]?.measurements).toEqual({
    seebeck: { temperature_k: [100], values: [2e-4] },
  });

  await expect(
    page.getByRole("listitem").filter({ hasText: /^Model$/ }),
  ).toBeVisible();
  await expect(modelLine(page)).toBeVisible();
  await expect(page.getByText("RMSE, S")).toBeVisible();
  await expect(page.getByText("108,4 µV/K")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a mode with no scattering sends none", async ({ page }) => {
  await open(page);
  const bodies = await collect(page);
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);

  await page.getByRole("radio", { name: "S", exact: true }).click();

  await expect.poll(() => bodies.at(-1)?.fit_mode).toBe("dpb_s");
  expect(bodies.at(-1)?.scattering).toBeNull();
});

test("rapid slider moves do not queue up, and the last one counts", async ({
  page,
}) => {
  await open(page);
  const bodies = await collect(page);
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);
  const before = bodies.length;

  const startedAt = Date.now();
  for (let move = 0; move < 30; move += 1) {
    await eg(page).press("ArrowRight");
  }
  const elapsedMs = Date.now() - startedAt;

  await expect.poll(() => bodies.at(-1)?.parameters.band_gap).toBe(1300);
  await page.waitForTimeout(400);
  // At most one per debounce, and one to finish, against 30 without it.
  expect(bodies.length - before).toBeLessThanOrEqual(
    Math.ceil(elapsedMs / 120) + 1,
  );
  expect(bodies.length - before).toBeLessThan(30);
});

test("a long drag still updates the curve on its way", async ({ page }) => {
  await open(page);
  const bodies = await collect(page);
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);
  const before = bodies.length;

  // Never resting for the debounce, for about a second.
  for (let move = 0; move < 20; move += 1) {
    await eg(page).press("ArrowRight");
    await page.waitForTimeout(50);
  }

  expect(bodies.length - before).toBeGreaterThanOrEqual(2);
});

test("an old answer never replaces a newer one, and a request is aborted", async ({
  page,
}) => {
  await open(page);
  let releaseFirst: () => void = () => undefined;
  const firstHeld = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  const aborted: string[] = [];
  page.on("requestfailed", (request) => {
    if (request.url().endsWith("/api/calc")) {
      aborted.push(request.failure()?.errorText ?? "");
    }
  });
  const bodies = await collect(page, async (route, index) => {
    if (index === 0) {
      await firstHeld;
      await route.fulfill({ json: withRmse(111) }).catch(() => undefined);
    } else {
      await route.fulfill({ json: withRmse(222) });
    }
  });
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);

  await eg(page).press("ArrowRight");

  await expect(page.getByText("222 µV/K")).toBeVisible();
  releaseFirst();
  await page.waitForTimeout(300);
  await expect(page.getByText("222 µV/K")).toBeVisible();
  await expect(page.getByText("111 µV/K")).toHaveCount(0);
  expect(aborted).toEqual(["net::ERR_ABORTED"]);
});

test("the last curve stays while waiting, with an indicator only after a delay", async ({
  page,
}) => {
  await open(page);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const bodies = await collect(page, async (route, index) => {
    if (index > 0) {
      await held;
    }
    await route.fulfill({ json: withRmse(index === 0 ? 111 : 222) });
  });
  await load(page);
  await expect(page.getByText("111 µV/K")).toBeVisible();
  await expect(page.getByText("Updating…")).toHaveCount(0);

  await eg(page).press("ArrowRight");
  await expect.poll(() => bodies.length).toBe(2);

  await expect(page.getByText("Updating…")).toBeVisible();
  await expect(modelLine(page)).toBeVisible();
  await expect(page.getByText("111 µV/K")).toBeVisible();

  release();
  await expect(page.getByText("222 µV/K")).toBeVisible();
  await expect(page.getByText("Updating…")).toHaveCount(0);
});

test("a quick answer shows no indicator at all", async ({ page }) => {
  await open(page);
  const bodies = await collect(page, async (route, index) => {
    await new Promise((resolve) => setTimeout(resolve, index === 0 ? 0 : 50));
    await route.fulfill({ json: withRmse(111 + index) });
  });
  await load(page);
  await expect(page.getByText("111 µV/K")).toBeVisible();
  await page.evaluate(() => {
    const seen: string[] = [];
    Object.assign(window, { seenStatuses: seen });
    new MutationObserver(() => {
      seen.push(document.body.innerText);
    }).observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
  });

  await eg(page).press("ArrowRight");

  await expect(page.getByText("112 µV/K")).toBeVisible();
  expect(bodies).toHaveLength(2);
  const seen = await page.evaluate(
    () => (window as unknown as { seenStatuses: string[] }).seenStatuses,
  );
  expect(seen.some((text) => text.includes("Updating…"))).toBe(false);
});

test("an error keeps the chart, says so without the server's text, and passes", async ({
  page,
}) => {
  await open(page);
  await collect(page, (route, index) =>
    index === 1
      ? route.fulfill({
          status: 422,
          json: {
            code: "calculation_failed",
            message: "SECRET-VALUE",
            details: [],
          },
        })
      : route.fulfill({ json: withRmse(111 + index) }),
  );
  await load(page);
  await expect(page.getByText("111 µV/K")).toBeVisible();

  await eg(page).press("ArrowRight");

  await expect(page.getByRole("alert")).toContainText(
    "no result for these parameters",
  );
  await expect(page.getByRole("alert")).toContainText("last curve stays");
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);
  await expect(modelLine(page)).toBeVisible();
  await expect(page.getByText("111 µV/K")).toBeVisible();

  await eg(page).press("ArrowRight");

  await expect(page.getByText("113 µV/K")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a server failure and no network say so", async ({ page }) => {
  await open(page);
  await collect(page, (route, index) => {
    if (index === 0) {
      return route.fulfill({
        status: 503,
        json: { code: "calculation_unavailable", message: "x", details: [] },
      });
    }
    return route.abort("connectionrefused");
  });
  await load(page);

  await expect(page.getByRole("alert")).toContainText("not responding");
  // With no curve yet, nothing is said about the last one.
  await expect(page.getByRole("alert")).not.toContainText("last curve");

  await eg(page).press("ArrowRight");
  await expect(page.getByRole("alert")).toContainText("could not be reached");
});

test("a limit with Retry-After tries again by itself", async ({ page }) => {
  await open(page);
  const bodies = await collect(page, (route, index) =>
    index === 0
      ? route.fulfill({
          status: 429,
          headers: { "Retry-After": "1" },
          json: { code: "rate_limited", message: "x", details: [] },
        })
      : route.fulfill({ json: withRmse(111) }),
  );
  await load(page);

  await expect(page.getByRole("alert")).toContainText("Too many updates");
  await expect(page.getByText("111 µV/K")).toBeVisible({ timeout: 3000 });
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(bodies).toHaveLength(2);
});

test("no second try runs after the values change", async ({ page }) => {
  await open(page);
  const bodies = await collect(page, (route, index) =>
    index === 0
      ? route.fulfill({
          status: 429,
          headers: { "Retry-After": "1" },
          json: { code: "rate_limited", message: "x", details: [] },
        })
      : route.fulfill({ json: CALC }),
  );
  await load(page);
  await expect(page.getByRole("alert")).toBeVisible();

  await eg(page).press("ArrowRight");
  await expect.poll(() => bodies.length).toBe(2);
  await page.waitForTimeout(1200);

  expect(bodies).toHaveLength(2);
  expect(bodies[1]?.parameters.band_gap).toBe(1010);
});

test("removing the data clears the curve and the RMSE, and ends what runs", async ({
  page,
}) => {
  await open(page);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const bodies = await collect(page, async (route, index) => {
    if (index > 0) {
      await held;
      await route.fulfill({ json: withRmse(222) }).catch(() => undefined);
    } else {
      await route.fulfill({ json: withRmse(111) });
    }
  });
  await load(page);
  await expect(page.getByText("111 µV/K")).toBeVisible();
  await eg(page).press("ArrowRight");
  await expect.poll(() => bodies.length).toBe(2);

  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();

  await expect(page.getByText("No data yet")).toBeVisible();
  await expect(page.getByText("111 µV/K")).toHaveCount(0);
  release();
  await page.waitForTimeout(200);
  await expect(page.getByText("222 µV/K")).toHaveCount(0);
});

test("leaving the page ends a request, and coming back asks again", async ({
  page,
}) => {
  await open(page);
  const bodies = await collect(page);
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);

  await page.getByRole("link", { name: "Results" }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect.poll(() => bodies.length).toBe(2);
  await expect(modelLine(page)).toBeVisible();
});

test("the range holds the request back while interpolated values are on their way", async ({
  page,
}) => {
  await open(page);
  const bodies = await collect(page);
  let hold = false;
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/parse", async (route) => {
    const body = route.request().postDataJSON() as { interpolate?: object };
    if (hold) {
      await held;
    }
    await route.fulfill({
      json:
        body.interpolate === undefined
          ? PARSED
          : {
              ...PARSED,
              interpolated: {
                seebeck: {
                  temperature_k: [100, 120],
                  values: [1e-4, 2e-4],
                  extrapolated: true,
                  measured_points_in_range: 1,
                  underdetermined: false,
                },
              },
            },
    });
  });
  await load(page);
  await expect.poll(() => bodies.length).toBe(1);
  hold = true;

  await page.getByRole("switch", { name: /Interpolation/ }).click();
  await page.waitForTimeout(500);
  expect(bodies).toHaveLength(1);

  release();

  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[1]?.measurements).toEqual({
    seebeck: { temperature_k: [100, 120], values: [1e-4, 2e-4] },
  });
  expect(bodies[1]?.extrapolated).toBe(true);
});

test("known errors of a result are named", async ({ page }) => {
  await open(page);
  await collect(page, (route) =>
    route.fulfill({
      json: { ...withRmse(111), known_issues: ["dpb_hall_prefactor"] },
    }),
  );

  await load(page);

  await expect(
    page.getByText("Known errors apply to this result: dpb_hall_prefactor."),
  ).toBeVisible();
});

test("an RMSE that is not finite says so", async ({ page }) => {
  await open(page);
  await collect(page, (route) => route.fulfill({ json: withRmse(null) }));

  await load(page);

  await expect(page.getByText("not finite")).toBeVisible();
});
