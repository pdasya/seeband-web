import { expect, test, type Page } from "@playwright/test";

import { serveModels } from "./support/models";

async function open(page: Page) {
  await serveModels(page);
  await page.goto("/fit");
  await expect(page.getByRole("slider", { name: "E_F" })).toBeVisible();
}

const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name, exact: true });
const slider = (page: Page, name: string) =>
  page.getByRole("slider", { name, exact: true });
const choose = (page: Page, name: string) =>
  page.getByRole("radio", { name, exact: true }).click();

async function chooseScattering(page: Page, name: RegExp) {
  await page.getByRole("combobox", { name: "Scattering" }).click();
  await page.getByRole("option", { name }).click();
}

async function moveAway(page: Page) {
  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();
}

/** What the session holds for a mode, in core units. */
function stored(page: Page, fitMode: string) {
  return page.evaluate(async (id) => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => { parameters: Record<string, object | undefined> };
      };
    };
    return useSessionStore.getState().parameters[id];
  }, fitMode);
}

test("starts with the mode's parameters, defaults and ranges", async ({
  page,
}) => {
  await open(page);

  await expect(field(page, "m₂/m₁")).toHaveValue("1,01");
  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(field(page, "E_F")).toHaveValue("-100");
  await expect(field(page, "A")).toHaveValue("40000");
  await expect(field(page, "B")).toHaveValue("1");
  await expect(slider(page, "E_F")).toHaveAttribute("aria-valuemin", "-3000");
  await expect(slider(page, "E_F")).toHaveAttribute("aria-valuemax", "3000");
  await expect(field(page, "E_F")).toHaveAccessibleDescription(
    "Fermi energy at T = 0, in K",
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a parameter's meaning shows on its (i), not under it", async ({
  page,
}) => {
  await open(page);
  const about = page.getByRole("button", { name: "About m₂/m₁" });
  const tip = page.getByRole("tooltip");
  await expect(tip).toHaveCount(0);

  await about.hover();
  await expect(tip).toContainText(/^band mass ratio m2\/m1/);
  await page.getByRole("heading", { name: "Parameters" }).hover();
  await expect(tip).toHaveCount(0);

  // A keyboard reaches it too.
  await page.getByRole("button", { name: "About E_g" }).focus();
  await expect(tip).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(tip).toHaveCount(0);
});

test("parameters follow the scattering type and fit mode", async ({ page }) => {
  await open(page);

  await chooseScattering(page, /dis\)/);
  await expect(field(page, "F")).toBeVisible();
  await expect(field(page, "G")).toBeVisible();
  await expect(field(page, "A")).toHaveCount(0);

  await chooseScattering(page, /acPhDis/);
  for (const name of ["A", "B", "C", "D"]) {
    await expect(field(page, name)).toBeVisible();
  }
  await expect(field(page, "F")).toHaveCount(0);
  await expect(field(page, "m₁")).toHaveCount(0);

  await choose(page, "S + ρ + R_H");
  await expect(field(page, "m₁")).toBeVisible();

  await choose(page, "S");
  await expect(slider(page, "E_F")).toBeVisible();
  await expect(field(page, "A")).toHaveCount(0);
});

test("the SPB mass spans both signs, and is marked as not fitted", async ({
  page,
}) => {
  await open(page);
  await choose(page, "SPB");

  await expect(field(page, "m")).toHaveValue("1,01");
  await expect(slider(page, "m")).toHaveAttribute("aria-valuemin", "-3");
  await expect(slider(page, "m")).toHaveAttribute("aria-valuemax", "3");
  await expect(
    page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Parameters" }) })
      .getByText("not fitted"),
  ).toHaveCount(1);

  await field(page, "m").fill("-2.5");
  await field(page, "m").press("Enter");

  await expect(slider(page, "m")).toHaveAttribute("aria-valuenow", "-2.5");
  expect(await stored(page, "spb_s")).toEqual({ band_mass: -2.5 });
});

test("a typed value counts on leaving the field, and moves the slider", async ({
  page,
}) => {
  await open(page);

  await field(page, "E_g").fill("1234.5");
  await expect(slider(page, "E_g")).toHaveAttribute("aria-valuenow", "1000");

  await field(page, "E_g").blur();

  await expect(slider(page, "E_g")).toHaveAttribute("aria-valuenow", "1234.5");
  await moveAway(page);
  await expect(field(page, "E_g")).toHaveValue("1234,5");
});

for (const typed of ["3001", "-3001", "", "abc", "1,2,3"]) {
  test(`"${typed}" is refused, says why, and keeps the last value`, async ({
    page,
  }) => {
    await open(page);
    await field(page, "E_g").fill("500");
    await field(page, "E_g").press("Enter");

    await field(page, "E_g").fill(typed);
    await field(page, "E_g").blur();

    await expect(field(page, "E_g")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("alert")).toContainText(
      "E_g: enter a number from -3000 to 3000",
    );
    expect(await stored(page, "dpb_s_rho")).toEqual({ band_gap: 500 });

    await moveAway(page);
    await expect(field(page, "E_g")).toHaveValue("500");
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("moving the slider replaces a refused number", async ({ page }) => {
  await open(page);
  await field(page, "E_g").fill("9999");
  await field(page, "E_g").blur();
  await expect(page.getByRole("alert")).toBeVisible();

  await slider(page, "E_g").press("ArrowRight");

  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(field(page, "E_g")).toHaveValue("1010");
});

test("numbers show a decimal comma, and take a comma or a point", async ({
  page,
}) => {
  await open(page);

  await expect(field(page, "m₂/m₁")).toHaveValue("1,01");
  await expect(page.getByText("0,9", { exact: true })).toBeVisible();
  await expect(page.getByText("1,1", { exact: true })).toBeVisible();

  await field(page, "E_g").fill("12,5");
  await field(page, "E_g").blur();
  await expect(slider(page, "E_g")).toHaveAttribute("aria-valuenow", "12.5");
  await expect(field(page, "E_g")).toHaveValue("12,5");

  await field(page, "E_g").fill("13.5");
  await field(page, "E_g").blur();
  await expect(slider(page, "E_g")).toHaveAttribute("aria-valuenow", "13.5");
  await expect(field(page, "E_g")).toHaveValue("13,5");
});

test("a message about a number is tied to its field", async ({ page }) => {
  await open(page);

  await field(page, "E_F").fill("9999");
  await field(page, "E_F").blur();

  await expect(field(page, "E_F")).toHaveAccessibleDescription(
    /Fermi energy.*enter a number from -3000 to 3000/,
  );
});

test("a slider's whole position reaches the session exactly", async ({
  page,
}) => {
  await open(page);
  await choose(page, "SPB");
  await choose(page, "S + ρ");
  await chooseScattering(page, /acPhDis/);
  await field(page, "C").fill("2,54");
  await field(page, "C").press("Enter");

  await slider(page, "C").press("ArrowRight");

  expect(await stored(page, "spb_s_rho")).toEqual({ C: 255 });
  await expect(field(page, "C")).toHaveValue("2,55");
});

test("the keyboard moves by the description's step", async ({ page }) => {
  await open(page);

  await slider(page, "A").press("ArrowRight");
  await expect(field(page, "A")).toHaveValue("41000");
  await slider(page, "A").press("ArrowLeft");
  await slider(page, "A").press("ArrowDown");
  await expect(field(page, "A")).toHaveValue("39000");
  await slider(page, "A").press("PageUp");
  await expect(field(page, "A")).toHaveValue("49000");
  await slider(page, "A").press("Shift+ArrowLeft");
  await expect(field(page, "A")).toHaveValue("39000");
  await slider(page, "A").press("Shift+PageUp");
  await expect(field(page, "A")).toHaveValue("49000");
  await slider(page, "A").press("PageDown");
  await slider(page, "A").press("Home");
  await expect(field(page, "A")).toHaveValue("0");
  await slider(page, "A").press("End");
  await expect(field(page, "A")).toHaveValue("1000000");
});

test("a value between steps stays, and a step moves on from it", async ({
  page,
}) => {
  await open(page);
  await field(page, "m₂/m₁").fill("1.234");
  await field(page, "m₂/m₁").blur();

  await expect(slider(page, "m₂/m₁")).toHaveAttribute("aria-valuenow", "1.234");
  await slider(page, "m₂/m₁").press("ArrowRight");

  await expect(field(page, "m₂/m₁")).toHaveValue("1,244");
});

test("G with R_H keeps its default off the large step", async ({ page }) => {
  await open(page);
  await choose(page, "S + ρ + R_H");
  await chooseScattering(page, /dis\)/);

  await expect(field(page, "G")).toHaveValue("1");
  await expect(slider(page, "G")).toHaveAttribute("aria-valuenow", "1");
  await slider(page, "G").press("ArrowRight");
  await expect(field(page, "G")).toHaveValue("2");
});

test("dragging moves by whole control units, not by the step", async ({
  page,
}) => {
  await open(page);
  await choose(page, "S + ρ + R_H");
  await chooseScattering(page, /dis\)/);
  await slider(page, "G").scrollIntoViewIfNeeded();
  const box = await slider(page, "G").locator("..").locator("..").boundingBox();
  if (box === null) {
    throw new Error("No slider");
  }

  await page.mouse.click(box.x + box.width * 0.4, box.y + box.height / 2);

  // With its step of 1 as a grid, only 0.5, 1.5 and so on could be reached.
  const value = Number((await field(page, "G").inputValue()).replace(",", "."));
  expect(value).not.toBe(1);
  expect(value).toBeGreaterThan(1);
  expect(value).toBeLessThan(1.2);
  expect(value * 100).toBeCloseTo(Math.round(value * 100), 6);
});

test("where the two scales differ, the session holds core units", async ({
  page,
}) => {
  await open(page);
  await choose(page, "SPB");
  await choose(page, "S + ρ");
  await chooseScattering(page, /acPhDis/);

  await expect(field(page, "C")).toHaveValue("1");

  await field(page, "C").fill("1.5");
  await field(page, "C").press("Enter");

  expect(await stored(page, "spb_s_rho")).toEqual({ C: 150 });
  await expect(field(page, "C")).toHaveValue("1,5");
});

test("each fit mode keeps its own values and defaults", async ({ page }) => {
  await open(page);
  await choose(page, "SPB");
  await field(page, "E_F").fill("700");
  await field(page, "E_F").blur();

  await choose(page, "S + ρ");
  await expect(field(page, "E_F")).toHaveValue("-100");
  await expect(field(page, "m")).toHaveValue("-1");

  await choose(page, "S");
  await expect(field(page, "E_F")).toHaveValue("700");

  await choose(page, "DPB");
  await expect(field(page, "E_F")).toHaveValue("-100");
  await choose(page, "SPB");
  await expect(field(page, "E_F")).toHaveValue("700");
});

test("a refused number does not follow to another fit mode", async ({
  page,
}) => {
  await open(page);
  await field(page, "E_g").fill("9999");
  await field(page, "E_g").blur();
  await expect(page.getByRole("alert")).toBeVisible();

  await choose(page, "S");

  await expect(field(page, "E_g")).toHaveValue("1000");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("leaving a field unchanged keeps a result and the exact value", async ({
  page,
}) => {
  await open(page);
  const fitStatus = () =>
    page.evaluate(async () => {
      const path = "/src/session/store.ts";
      const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
        useSessionStore: { getState: () => { fit: { status: string } } };
      };
      return useSessionStore.getState().fit.status;
    });
  await page.evaluate(async () => {
    const path = "/src/session/store.ts";
    const { useSessionStore } = (await import(/* @vite-ignore */ path)) as {
      useSessionStore: {
        getState: () => {
          fitRequested: () => number;
          fitEvent: (run: number, event: object) => void;
          setParameter: (mode: string, name: string, value: number) => void;
        };
      };
    };
    const state = useSessionStore.getState();
    state.setParameter("dpb_s_rho", "band_gap", 1000.0000000000001);
    state.fitEvent(state.fitRequested(), {
      type: "done",
      result: {
        parameters: {},
        status: "converged",
        parameter_errors: {},
        at_bounds: [],
        known_issues: [],
      },
    });
  });

  await field(page, "E_g").focus();
  await field(page, "E_g").press("Enter");
  await field(page, "E_g").blur();
  // Typing the number that is shown, written differently, is no change either.
  await field(page, "E_g").fill("1000,0");
  await field(page, "E_g").blur();

  expect(await fitStatus()).not.toBe("idle");
  expect(await stored(page, "dpb_s_rho")).toEqual({
    band_gap: 1000.0000000000001,
  });

  await slider(page, "E_g").press("ArrowRight");
  await expect.poll(fitStatus).toBe("idle");
});

test.describe("on a touch screen", () => {
  test.use({ hasTouch: true });

  test("a tap on (i) shows the meaning, and a tap beside it hides it", async ({
    page,
  }) => {
    // Safari on iOS does not focus a button that is tapped, so focus cannot open it there.
    await page.addInitScript(() => {
      document.addEventListener(
        "mousedown",
        (event) => {
          event.preventDefault();
        },
        true,
      );
    });
    await open(page);
    const tip = page.getByRole("tooltip");

    await page.getByRole("button", { name: "About E_g" }).tap();
    await expect(
      page.getByRole("button", { name: "About E_g" }),
    ).not.toBeFocused();
    await expect(tip).toContainText("in K");

    await page.getByRole("heading", { name: "Parameters" }).tap();
    await expect(tip).toHaveCount(0);
  });
});
