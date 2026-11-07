import { expect, test, type Page } from "@playwright/test";

import { CALC, serveModels } from "./support/models";

interface FitBody {
  fit_mode: string;
  start: Record<string, number>;
  measurements: Record<string, unknown>;
  bounds?: object;
}

declare global {
  interface Window {
    fitTest: {
      bodies: FitBody[];
      aborted: number;
      send: (event: object) => void;
      end: () => void;
      fail: () => void;
      refuse: { status: number; body: object } | null;
    };
  }
}

/** A fake `POST /api/fit`, whose stream the test feeds event by event. */
async function fakeFit(page: Page) {
  await page.addInitScript(() => {
    const encoder = new TextEncoder();
    let stream: ReadableStreamDefaultController<Uint8Array> | null = null;
    const state: Window["fitTest"] = {
      bodies: [],
      aborted: 0,
      refuse: null,
      send: (event) => {
        stream?.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      },
      end: () => {
        stream?.close();
      },
      fail: () => {
        stream?.error(new TypeError("lost"));
      },
    };
    window.fitTest = state;
    const realFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (!url.endsWith("/api/fit")) {
        return realFetch(input, init);
      }
      state.bodies.push(JSON.parse(String(init?.body)) as FitBody);
      if (state.refuse !== null) {
        return Promise.resolve(
          new Response(JSON.stringify(state.refuse.body), {
            status: state.refuse.status,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      init?.signal?.addEventListener("abort", () => {
        state.aborted += 1;
      });
      const body = new ReadableStream<Uint8Array>({
        start: (controller) => {
          stream = controller;
          init?.signal?.addEventListener("abort", () => {
            controller.error(new DOMException("Aborted", "AbortError"));
          });
        },
      });
      return Promise.resolve(
        new Response(body, {
          headers: { "Content-Type": "text/event-stream" },
        }),
      );
    };
  });
}

const PARSED = (quantity: string) => ({
  column_count: 2,
  row_count: 2,
  preview: [],
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
});

async function open(page: Page) {
  await fakeFit(page);
  await serveModels(page);
  await page.route("**/api/parse", (route) => {
    const { expected } = route.request().postDataJSON() as {
      expected: string;
    };
    return route.fulfill({ json: PARSED(expected) });
  });
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
}

/** Fills the next empty slot, as a filled one has no file input, and waits for it to count. */
async function load(page: Page, filled: number) {
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

/** DPB S + ρ, the design's first state, is iterative, and needs these two. */
async function openWithData(page: Page) {
  await open(page);
  await load(page, 0);
  await load(page, 1);
  await expect(run(page)).toBeEnabled();
}

const run = (page: Page) => page.getByRole("button", { name: "Run fit" });
const stop = (page: Page) => page.getByRole("button", { name: "Stop" });
const reset = (page: Page) => page.getByRole("button", { name: "Reset" });
const heading = (page: Page) =>
  page
    .locator("div")
    .filter({ has: page.getByRole("heading", { level: 1 }) })
    .last();
const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const slider = (page: Page, name: string) =>
  page.getByRole("slider", { name, exact: true });
const send = (page: Page, event: object) =>
  page.evaluate((value) => {
    window.fitTest.send(value);
  }, event);
const fitBodies = (page: Page) => page.evaluate(() => window.fitTest.bodies);
const aborted = (page: Page) => page.evaluate(() => window.fitTest.aborted);

const badge = (page: Page, text: string) =>
  page.locator('[data-slot="badge"]').filter({
    hasText: new RegExp(`^${text}$`),
  });

const RESULT = {
  parameters: { m_eff: 0.5, band_gap: 900, fermi_energy: -50 },
  status: "converged",
  iterations: 5,
  parameter_errors: {},
  at_bounds: [],
  known_issues: [],
};

async function startFit(page: Page) {
  await run(page).click();
  await send(page, { type: "started" });
  await expect(stop(page)).toBeVisible();
}

test("Run says what it needs, and is enabled once it has that", async ({
  page,
}) => {
  await open(page);

  await expect(run(page)).toBeDisabled();
  await expect(
    page.getByText("This fit mode needs data for S, ρ."),
  ).toBeVisible();

  await load(page, 0);
  await expect(page.getByText("This fit mode needs data for ρ.")).toBeVisible();
  await expect(run(page)).toBeDisabled();

  await load(page, 1);
  await expect(run(page)).toBeEnabled();
  await expect(page.getByText(/This fit mode needs/)).toHaveCount(0);

  await page.getByLabel("Lower bound, K").fill("300");
  await page.getByLabel("Lower bound, K").blur();
  await expect(run(page)).toBeDisabled();
  await expect(
    page.getByText("No points in the fit range for S, ρ."),
  ).toBeVisible();
});

test("a fit sends its start values and data, and no bounds", async ({
  page,
}) => {
  await openWithData(page);
  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();

  await run(page).click();

  const bodies = await fitBodies(page);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]?.fit_mode).toBe("dpb_s_rho");
  expect(bodies[0]?.start.band_gap).toBe(500);
  expect(Object.keys(bodies[0]?.measurements ?? {}).sort()).toEqual([
    "resistivity",
    "seebeck",
  ]);
  expect(bodies[0]?.bounds).toBeUndefined();
});

test("an iterative fit: status, counter, moving values and Stop", async ({
  page,
}) => {
  await openWithData(page);
  await expect(page.getByText("Manual parameters")).toBeVisible();

  await run(page).click();
  await expect(page.getByText("Fitting… waiting in the queue")).toBeVisible();
  await expect(stop(page)).toBeVisible();
  await expect(run(page)).toHaveCount(0);

  await send(page, { type: "started" });
  await expect(badge(page, "Fitting…")).toBeVisible();

  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { m_eff: 1.5, band_gap: 850 },
  });
  await expect(page.getByText("Fitting… iteration 1")).toBeVisible();
  await expect(field(page, "m₂/m₁")).toHaveValue("1,5");
  await expect(field(page, "E_g")).toHaveValue("850");
  await expect(field(page, "m₂/m₁")).toBeDisabled();
  await expect(slider(page, "E_g")).toHaveAttribute("data-disabled");

  await send(page, {
    type: "iteration",
    iteration: 2,
    parameters: { m_eff: 1.25, band_gap: 800 },
  });
  await expect(page.getByText("Fitting… iteration 2")).toBeVisible();

  await stop(page).click();

  await expect(page.getByText("Stopped at iteration 2")).toBeVisible();
  expect(await aborted(page)).toBe(1);
  // Stop keeps the last parameters, and the controls are back.
  await expect(field(page, "m₂/m₁")).toHaveValue("1,25");
  await expect(field(page, "E_g")).toHaveValue("800");
  await expect(field(page, "E_g")).toBeEnabled();
  await expect(run(page)).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("Stop before any iteration keeps the start values", async ({ page }) => {
  await openWithData(page);
  await run(page).click();

  await stop(page).click();

  await expect(badge(page, "Stopped")).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("1000");
});

test("the curves follow the fit, and end on its values", async ({ page }) => {
  const bodies: { parameters: Record<string, number> }[] = [];
  await openWithData(page);
  await page.route("**/api/calc", (route) => {
    bodies.push(
      route.request().postDataJSON() as {
        parameters: Record<string, number>;
      },
    );
    return route.fulfill({ json: CALC });
  });
  await startFit(page);

  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { m_eff: 1.5 },
  });
  await expect.poll(() => bodies.at(-1)?.parameters.m_eff).toBe(1.5);

  await send(page, { type: "done", result: RESULT });

  await expect(page.getByText("Converged in 5 iter.")).toBeVisible();
  await expect.poll(() => bodies.at(-1)?.parameters.m_eff).toBe(0.5);
  await expect(field(page, "E_F")).toHaveValue("-50");
  await expect(run(page)).toBeEnabled();
});

test("a single-pass mode shows no counter", async ({ page }) => {
  await openWithData(page);
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await startFit(page);
  await expect(badge(page, "Fitting…")).toBeVisible();

  await send(page, {
    type: "done",
    result: { ...RESULT, iterations: null },
  });

  await expect(badge(page, "Converged")).toBeVisible();
  await expect(page.getByText(/iter/)).toHaveCount(0);
});

test("reaching the limit says so, and keeps the values", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await send(page, {
    type: "done",
    result: { ...RESULT, status: "iteration_limit" },
  });

  await expect(badge(page, "Iteration limit reached")).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("900");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a value that is not finite leaves the last one", async ({ page }) => {
  await openWithData(page);
  // Not the default, which a lost value would fall back to.
  await field(page, "m₂/m₁").fill("2");
  await field(page, "m₂/m₁").blur();
  await startFit(page);

  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { m_eff: null, band_gap: 850 },
  });

  await expect(field(page, "E_g")).toHaveValue("850");
  await expect(field(page, "m₂/m₁")).toHaveValue("2");
});

test("a long value shows short, and stays exact", async ({ page }) => {
  await openWithData(page);
  const bodies: { parameters: Record<string, number> }[] = [];
  await page.route("**/api/calc", (route) => {
    bodies.push(
      route.request().postDataJSON() as { parameters: Record<string, number> },
    );
    return route.fulfill({ json: CALC });
  });
  await startFit(page);
  await send(page, {
    type: "done",
    result: { ...RESULT, parameters: { band_gap: 651.553903512 } },
  });
  await expect(field(page, "E_g")).toHaveValue("651,554");
  await expect(field(page, "E_g")).toHaveAttribute("title", "651,553903512");
  await expect
    .poll(() => bodies.at(-1)?.parameters.band_gap)
    .toBe(651.553903512);
  const count = bodies.length;

  // Typing what is shown is no change, so the exact value and the result stay. It is written
  // differently, as filling in the same text sends no input event.
  await field(page, "E_g").fill("651,5540");
  await field(page, "E_g").blur();

  await page.waitForTimeout(400);
  expect(bodies).toHaveLength(count);
  await expect(page.getByText("Converged in 5 iter.")).toBeVisible();
});

test("a value that a fit moves ends a refused number", async ({ page }) => {
  await openWithData(page);
  await field(page, "E_g").fill("9999");
  await field(page, "E_g").blur();
  await expect(page.getByRole("alert")).toBeVisible();
  await startFit(page);

  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { band_gap: 850 },
  });

  await expect(field(page, "E_g")).toHaveValue("850");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a value beyond the control's range shows, with the slider at its end", async ({
  page,
}) => {
  await openWithData(page);
  await startFit(page);

  await send(page, {
    type: "done",
    result: { ...RESULT, parameters: { band_gap: 9000 } },
  });

  await expect(field(page, "E_g")).toHaveValue("9000");
  await expect(slider(page, "E_g")).toHaveAttribute("aria-valuenow", "3000");
});

test("a fit that ends with no result says why", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await send(page, {
    type: "done",
    result: {
      ...RESULT,
      status: "failed",
      iterations: null,
      message: "The start values do not fit the bounds.",
    },
  });

  await expect(page.getByRole("alert")).toContainText(
    "The start values do not fit the bounds.",
  );
  await expect(badge(page, "Failed")).toBeVisible();
  await expect(run(page)).toBeEnabled();
});

test("a failure event says so in our words, and a new run clears it", async ({
  page,
}) => {
  await openWithData(page);
  await startFit(page);

  await send(page, {
    type: "error",
    error: { code: "fit_timeout", message: "SECRET-VALUE", details: [] },
  });

  await expect(page.getByRole("alert")).toContainText("time limit");
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);

  await run(page).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a stream that ends by itself is a failure, not a Stop", async ({
  page,
}) => {
  await openWithData(page);
  await startFit(page);

  await page.evaluate(() => {
    window.fitTest.end();
  });

  await expect(page.getByRole("alert")).toContainText("connection was lost");
  await expect(page.getByText("Stopped")).toHaveCount(0);
});

test("a lost connection is a failure too", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await page.evaluate(() => {
    window.fitTest.fail();
  });

  await expect(page.getByRole("alert")).toContainText("connection was lost");
});

test("a refusal says so, with nothing left running", async ({ page }) => {
  await openWithData(page);
  await page.evaluate(() => {
    window.fitTest.refuse = {
      status: 429,
      body: { code: "fit_queue_full", message: "SECRET-VALUE", details: [] },
    };
  });

  await run(page).click();

  await expect(page.getByRole("alert")).toContainText("Too many fits");
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);
  await expect(run(page)).toBeEnabled();
});

test("Reset goes back to the defaults, and to manual", async ({ page }) => {
  await openWithData(page);
  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();
  await field(page, "E_F").fill("9999");
  await field(page, "E_F").blur();
  await expect(page.getByRole("alert")).toBeVisible();

  await reset(page).click();

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(field(page, "E_F")).toHaveValue("-100");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("Manual parameters")).toBeVisible();
});

test("Reset touches only this fit mode", async ({ page }) => {
  await openWithData(page);
  await field(page, "E_g").fill("500");
  await field(page, "E_g").blur();
  await page.getByRole("radio", { name: "S", exact: true }).click();
  await field(page, "E_g").fill("600");
  await field(page, "E_g").blur();

  await reset(page).click();
  await expect(field(page, "E_g")).toHaveValue("1000");

  await page.getByRole("radio", { name: "S + ρ", exact: true }).click();
  await expect(field(page, "E_g")).toHaveValue("500");
});

test("Reset during a fit stops it", async ({ page }) => {
  await openWithData(page);
  await startFit(page);
  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { band_gap: 850 },
  });
  await expect(field(page, "E_g")).toHaveValue("850");

  await reset(page).click();

  expect(await aborted(page)).toBe(1);
  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(run(page)).toBeEnabled();
});

test("a change of what the fit is of stops it", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name: /dis\)/ }).click();

  await expect(run(page)).toBeEnabled();
  expect(await aborted(page)).toBe(1);

  await startFit(page);
  await page.getByLabel("Upper bound, K").fill("700");
  await page.getByLabel("Upper bound, K").blur();
  await expect(run(page)).toBeEnabled();
  expect(await aborted(page)).toBe(2);

  await startFit(page);
  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  await expect(run(page)).toBeDisabled();
  expect(await aborted(page)).toBe(3);
});

test("its own values moving do not stop a fit", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { band_gap: 850 },
  });

  await expect(field(page, "E_g")).toHaveValue("850");
  await page.waitForTimeout(300);
  expect(await aborted(page)).toBe(0);
  await expect(stop(page)).toBeVisible();
});

test("a fit goes on while another screen is open", async ({ page }) => {
  await openWithData(page);
  await startFit(page);

  await page.getByRole("link", { name: "Results" }).click();
  await send(page, {
    type: "iteration",
    iteration: 1,
    parameters: { band_gap: 850 },
  });
  await page.getByRole("link", { name: "Model fit" }).click();

  expect(await aborted(page)).toBe(0);
  await expect(page.getByText("Fitting… iteration 1")).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("850");

  await send(page, { type: "done", result: RESULT });
  await expect(page.getByText("Converged in 5 iter.")).toBeVisible();
});

test("a move of a slider after a result goes back to manual", async ({
  page,
}) => {
  await openWithData(page);
  await startFit(page);
  await send(page, { type: "done", result: RESULT });
  await expect(page.getByText("Converged in 5 iter.")).toBeVisible();

  await slider(page, "E_g").press("ArrowRight");

  await expect(page.getByText("Manual parameters")).toBeVisible();
});

test("a screen reader hears the status, and not each iteration", async ({
  page,
}) => {
  await openWithData(page);
  await startFit(page);
  const status = page.getByRole("status").filter({ hasText: /^Fitting…$/ });
  await expect(status).toHaveCount(1);

  await send(page, {
    type: "iteration",
    iteration: 7,
    parameters: {},
  });

  await expect(page.getByText("Fitting… iteration 7")).toBeVisible();
  await expect(status).toHaveCount(1);
  await expect(heading(page)).toBeVisible();
});
