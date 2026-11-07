import { expect, test, type Page, type Route } from "@playwright/test";

import { CALC, NO_GUESS, serveModels } from "./support/models";

interface GuessBody {
  model: string;
  temperature_k: number[];
  seebeck_v_per_k: number[];
}

const PARSED = {
  column_count: 2,
  row_count: 2,
  preview: [],
  mapping: [],
  measurements: {
    seebeck: {
      temperature_k: [40, 100, 900],
      values: [1e-5, 2e-5, 3e-5],
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

const GUESS = {
  status: "guess",
  net_range: { min_temperature_k: 25, max_temperature_k: 750 },
  prediction: { m_eff: 1.57, band_gap_k: 554, fermi_energy_k: 1170 },
  start_values: { m_eff: 1.57, band_gap: 554, fermi_energy: 1170 },
  warnings: [],
};

async function open(
  page: Page,
  answer: (route: Route, index: number) => Promise<void> = (route) =>
    route.fulfill({ json: GUESS }),
) {
  await serveModels(page);
  const bodies: GuessBody[] = [];
  await page.route("**/api/guess", (route) => {
    bodies.push(route.request().postDataJSON() as GuessBody);
    return answer(route, bodies.length - 1);
  });
  await page.route("**/api/parse", (route) => route.fulfill({ json: PARSED }));
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
  return bodies;
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
  await expect(page.getByText(/^3 points/)).toBeVisible();
}

const button = (page: Page) =>
  page.getByRole("button", { name: "Initial guess" });
const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const badge = (page: Page, text: string) =>
  page.locator('[data-slot="badge"]').filter({ hasText: text });
const choose = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true }).click();

function hold() {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release: () => release() };
}

test("a new file of S applies the net's values, and shows its real range", async ({
  page,
}) => {
  const bodies = await open(page);

  await load(page);

  await expect(field(page, "m₂/m₁")).toHaveValue("1,57");
  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(field(page, "E_F")).toHaveValue("1170");
  await expect(badge(page, "Initial guess · net 25–750 K")).toBeVisible();
  // Every row of S, also outside the fit range, in V/K.
  expect(bodies).toEqual([
    {
      model: "dpb",
      temperature_k: [40, 100, 900],
      seebeck_v_per_k: [1e-5, 2e-5, 3e-5],
    },
  ]);
});

test("the values go to every mode of the model, and stay out of others", async ({
  page,
}) => {
  await open(page);
  await load(page);
  await expect(field(page, "E_g")).toHaveValue("554");

  await choose(page, "S");
  await expect(field(page, "E_g")).toHaveValue("554");
  await choose(page, "S + ρ + R_H");
  await expect(field(page, "E_g")).toHaveValue("554");

  await choose(page, "SPB");
  await expect(field(page, "E_F")).toHaveValue("100");
  await expect(badge(page, "Initial guess")).toHaveCount(0);
});

test("the other parameters keep their values", async ({ page }) => {
  await open(page);
  await field(page, "A").fill("50000");
  await field(page, "A").blur();

  await load(page);

  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(field(page, "A")).toHaveValue("50000");
});

test("loading while SPB is open still sets the DPB values", async ({
  page,
}) => {
  await open(page);
  await choose(page, "SPB");

  await load(page);
  await expect(button(page)).toBeDisabled();
  await expect(field(page, "E_F")).toHaveValue("100");

  await choose(page, "DPB");
  await expect(field(page, "E_g")).toHaveValue("554");
});

test("the button is for a model with nets and S data, and says so", async ({
  page,
}) => {
  await open(page);

  await expect(button(page)).toBeDisabled();
  await expect(button(page)).toHaveAttribute("title", /Load S data/);

  await choose(page, "SPB");
  await expect(button(page)).toHaveAttribute("title", /DPB only/);
  await choose(page, "DPB");

  await load(page);
  await expect(button(page)).toBeEnabled();
  await expect(button(page)).toHaveAttribute("title", /proposes/);
});

test("the button applies the net again after edits", async ({ page }) => {
  const bodies = await open(page);
  await load(page);
  await field(page, "E_g").fill("700");
  await field(page, "E_g").blur();
  await expect(badge(page, "Initial guess")).toHaveCount(0);

  await button(page).click();

  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(badge(page, "Initial guess · net 25–750 K")).toBeVisible();
  expect(bodies).toHaveLength(2);
});

test("an edit ends the badge, and the values count as manual", async ({
  page,
}) => {
  await open(page);
  await load(page);
  await expect(badge(page, "Initial guess")).toBeVisible();

  await page.getByRole("slider", { name: "E_g" }).press("ArrowRight");

  await expect(badge(page, "Initial guess")).toHaveCount(0);
  await expect(page.getByText("Manual parameters")).toBeVisible();
});

test("edits after the file are kept, if the answer comes later", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS });
  });
  await load(page);

  await field(page, "E_g").fill("700");
  await field(page, "E_g").blur();
  gate.release();

  await expect(button(page)).toBeEnabled();
  await expect(field(page, "E_g")).toHaveValue("700");
  await expect(field(page, "E_F")).toHaveValue("-100");
  await expect(badge(page, "Initial guess")).toHaveCount(0);
});

test("edits before the file are overwritten, as on the desktop", async ({
  page,
}) => {
  await open(page);
  await field(page, "E_g").fill("700");
  await field(page, "E_g").blur();

  await load(page);

  await expect(field(page, "E_g")).toHaveValue("554");
});

test("coming back to a tab does not guess again, or undo edits", async ({
  page,
}) => {
  const bodies = await open(page);
  await load(page);
  await expect(field(page, "E_g")).toHaveValue("554");
  await field(page, "E_g").fill("700");
  await field(page, "E_g").blur();

  await page.getByRole("tab", { name: "Single file" }).click();
  await page.getByRole("tab", { name: "Separate files" }).click();
  await expect(page.getByText(/^3 points/)).toBeVisible();
  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();
  await page.waitForTimeout(300);

  expect(bodies).toHaveLength(1);
  await expect(field(page, "E_g")).toHaveValue("700");
});

test("a removed file loaded again guesses again", async ({ page }) => {
  const bodies = await open(page);
  await load(page);
  await expect(field(page, "E_g")).toHaveValue("554");
  await field(page, "E_g").fill("700");
  await field(page, "E_g").blur();

  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  await expect(page.getByText(/^3 points/)).toHaveCount(0);
  await load(page);

  await expect(field(page, "E_g")).toHaveValue("554");
  expect(bodies).toHaveLength(2);
});

test("a late answer about a file that was replaced does not count", async ({
  page,
}) => {
  const gate = hold();
  const bodies = await open(page, async (route, index) => {
    if (index === 0) {
      await gate.held;
      await route.fulfill({ json: GUESS }).catch(() => undefined);
    } else {
      await route.fulfill({ json: NO_GUESS });
    }
  });
  await load(page);
  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  await expect(page.getByText(/^3 points/)).toHaveCount(0);
  await load(page);
  await expect(page.getByText(/No neural net covers/)).toBeVisible();
  expect(bodies).toHaveLength(2);

  gate.release();
  await page.waitForTimeout(300);

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(page.getByText(/No neural net covers/)).toBeVisible();
});

test("a late answer about a removed file changes nothing", async ({ page }) => {
  const gate = hold();
  const bodies = await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS });
  });
  await load(page);
  await page
    .getByRole("button", { name: /Remove/ })
    .first()
    .click();
  await expect(page.getByText(/^3 points/)).toHaveCount(0);

  const answered = page.waitForResponse("**/api/guess");
  gate.release();
  await answered;
  await page.waitForTimeout(300);

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(field(page, "E_F")).toHaveValue("-100");

  // The file can still be loaded and guessed from.
  await load(page);
  await expect(field(page, "E_g")).toHaveValue("554");
  expect(bodies).toHaveLength(2);
});

test("an answer that comes while another model is open waits for it", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS });
  });
  await load(page);
  await choose(page, "SPB");

  const answered = page.waitForResponse("**/api/guess");
  gate.release();
  await answered;
  await expect(button(page)).toHaveAttribute("title", /DPB only/);
  await expect(field(page, "E_F")).toHaveValue("100");
  await expect(badge(page, "Initial guess")).toHaveCount(0);

  await choose(page, "DPB");
  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(badge(page, "Initial guess · net 25–750 K")).toBeVisible();
});

test("an answer that comes while another screen is open still counts", async ({
  page,
}) => {
  const gate = hold();
  const bodies = await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS });
  });
  await load(page);
  await page.getByRole("link", { name: "Results", exact: true }).click();

  const answered = page.waitForResponse("**/api/guess");
  gate.release();
  await answered;
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(badge(page, "Initial guess · net 25–750 K")).toBeVisible();
  expect(bodies).toHaveLength(1);
});

test("no net keeps the values, and names the real ranges", async ({ page }) => {
  await open(page, (route) => route.fulfill({ json: NO_GUESS }));

  await load(page);

  await expect(
    page.getByText(
      "No neural net covers 100–200 K, so the values stay as they are. The nets cover 300–800 K.",
    ),
  ).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(badge(page, "Initial guess")).toHaveCount(0);
  await expect(page.getByText("Manual parameters")).toBeVisible();
});

test("a prediction that is not finite keeps the values", async ({ page }) => {
  await open(page, (route) =>
    route.fulfill({
      json: { status: "not_finite", net_range: GUESS.net_range, warnings: [] },
    }),
  );

  await load(page);

  await expect(page.getByText("no usable values")).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("1000");
});

test("a mass of about 0 is not applied, and asks for one", async ({ page }) => {
  await open(page, (route) =>
    route.fulfill({
      json: {
        ...GUESS,
        start_values: { m_eff: 0, band_gap: 554, fermi_energy: 1170 },
        warnings: ["m_eff_rounds_to_zero"],
      },
    }),
  );

  await load(page);

  await expect(page.getByText("Set a mass by hand.")).toBeVisible();
  await expect(field(page, "m₂/m₁")).toHaveValue("1,01");
  await expect(field(page, "E_g")).toHaveValue("1000");
});

test("a weak guess is applied, and says so", async ({ page }) => {
  await open(page, (route) =>
    route.fulfill({
      json: { ...GUESS, warnings: ["underdetermined_fit"] },
    }),
  );

  await load(page);

  await expect(field(page, "E_g")).toHaveValue("554");
  await expect(page.getByText("too few temperatures")).toBeVisible();
});

test("a failure keeps the values and says so, without the server's text", async ({
  page,
}) => {
  await open(page, (route) =>
    route.fulfill({
      status: 422,
      json: {
        code: "calculation_failed",
        message: "SECRET-VALUE",
        details: [],
      },
    }),
  );

  await load(page);

  await expect(page.getByText("could not be calculated")).toBeVisible();
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);
  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(button(page)).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a limit keeps the values and says so", async ({ page }) => {
  await open(page, (route) =>
    route.fulfill({
      status: 429,
      json: { code: "rate_limited", message: "SECRET-VALUE", details: [] },
    }),
  );

  await load(page);

  await expect(page.getByText("Too many initial guesses")).toBeVisible();
  await expect(page.getByText("SECRET-VALUE")).toHaveCount(0);
  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(button(page)).toBeEnabled();
});

test("a fit started while the answer is on its way keeps its values", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS }).catch(() => undefined);
  });
  // Never answers, so that the fit stays at its start.
  await page.route("**/api/fit", () => new Promise<void>(() => undefined));
  await load(page);
  await choose(page, "S");
  await page.getByRole("button", { name: "Run fit" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();

  gate.release();
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: "Stop" }).click();

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(badge(page, "Initial guess")).toHaveCount(0);
  await expect(button(page)).toBeEnabled();
});

test("a fit that fails before the answer keeps its message", async ({
  page,
}) => {
  const gate = hold();
  await open(page, async (route) => {
    await gate.held;
    await route.fulfill({ json: GUESS }).catch(() => undefined);
  });
  await page.route("**/api/fit", (route) =>
    route.fulfill({
      status: 422,
      json: { code: "calculation_failed", message: "x", details: [] },
    }),
  );
  await load(page);
  await choose(page, "S");
  await page.getByRole("button", { name: "Run fit" }).click();
  await expect(page.getByRole("alert")).toBeVisible();

  gate.release();
  await page.waitForTimeout(300);

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(field(page, "E_g")).toHaveValue("1000");
});

test("the button cannot be pressed during a fit", async ({ page }) => {
  await open(page);
  await load(page);
  await page.getByRole("radio", { name: "S", exact: true }).click();
  const gate = hold();
  await page.route("**/api/fit", async (route) => {
    await gate.held;
    await route.abort().catch(() => undefined);
  });
  await page.getByRole("button", { name: "Run fit" }).click();

  await expect(button(page)).toBeDisabled();
  gate.release();
});

test("the curve follows the values it applies", async ({ page }) => {
  const calcs: { parameters: Record<string, number> }[] = [];
  await open(page);
  await page.route("**/api/calc", (route) => {
    calcs.push(
      route.request().postDataJSON() as { parameters: Record<string, number> },
    );
    return route.fulfill({ json: CALC });
  });

  await load(page);

  await expect.poll(() => calcs.at(-1)?.parameters.band_gap).toBe(554);
});

test("Reset goes back to the defaults, not to the guess", async ({ page }) => {
  await open(page);
  await load(page);
  await expect(field(page, "E_g")).toHaveValue("554");

  await page.getByRole("button", { name: "Reset" }).click();

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(badge(page, "Initial guess")).toHaveCount(0);
});
