import { expect, test, type Page } from "@playwright/test";

const FIXTURE = "/app/e2e/chart-fixture.html";
const POINTS = 9;

async function openChart(page: Page) {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    // A page with no icon gets a 404 for it from the browser.
    if (
      message.type() === "error" &&
      !message.location().url.endsWith("/favicon.ico")
    ) {
      problems.push(message.text());
    }
  });
  await page.goto(FIXTURE);
  await expect(page.locator(".main-svg").first()).toBeVisible();
  return problems;
}

const modelPath = (page: Page) =>
  page.locator(".scatterlayer .trace").nth(0).locator("path.js-line").first();

test("draws curves, hollow markers, shading, a reference line and axes", async ({
  page,
}) => {
  const problems = await openChart(page);

  await expect(page.locator(".scatterlayer .trace")).toHaveCount(3);
  await expect(page.locator(".scatterlayer .points path")).toHaveCount(POINTS);

  const points = page.locator(".scatterlayer .points path");
  const look = await points.evaluateAll((elements) =>
    elements.map((element) => {
      const style = getComputedStyle(element);
      return { fill: style.fill, stroke: style.stroke };
    }),
  );
  expect(new Set(look.map((point) => point.fill))).toEqual(
    new Set(["rgb(255, 255, 255)"]),
  );
  // 50 K and 800 K lie outside the fit range of 100 to 700 K.
  expect(look.at(0)?.stroke).toBe("rgb(161, 161, 170)");
  expect(look.at(1)?.stroke).toBe("rgb(9, 9, 11)");
  expect(look.at(-1)?.stroke).toBe("rgb(161, 161, 170)");

  const shapes = await page
    .locator(".layer-below .shapelayer path")
    .evaluateAll((elements) =>
      elements.map((element) => getComputedStyle(element).fill),
    );
  expect(shapes).toEqual(["rgb(244, 244, 245)", "rgb(244, 244, 245)"]);
  await expect(page.locator(".annotation-text")).toHaveText("Band edge");
  await expect(page.locator(".xtitle")).toHaveText("T, K");
  await expect(page.locator(".ytitle")).toHaveText("S, µV/K");
  await expect(page.locator(".xtick text").first()).toHaveText("0");

  const font = await page
    .locator(".xtitle")
    .evaluate((element) => getComputedStyle(element).fontFamily);
  expect(font).toContain("Geist");
  expect(problems).toEqual([]);
});

test("a value that is not finite leaves a gap in its curve", async ({
  page,
}) => {
  await openChart(page);

  // The curve has 9 points, with null as the fourth, so it is drawn in two pieces.
  await expect(
    page.locator(".scatterlayer .trace").nth(0).locator("path.js-line"),
  ).toHaveCount(2);
  await expect(
    page.locator(".scatterlayer .trace").nth(1).locator("path.js-line"),
  ).toHaveCount(1);
});

test("the second curve is dashed, with its own colour", async ({ page }) => {
  await openChart(page);

  const look = await page
    .locator(".scatterlayer .trace")
    .nth(1)
    .locator("path.js-line")
    .first()
    .evaluate((element) => {
      const style = getComputedStyle(element);
      return { dash: style.strokeDasharray, stroke: style.stroke };
    });

  expect(look.dash).not.toBe("none");
  expect(look.stroke).toBe("rgb(234, 88, 12)");
});

test("the legend names each series, and the toggle hides measurements", async ({
  page,
}) => {
  await openChart(page);
  const legend = page.locator("figure ul");
  await expect(legend).toContainText("Measurements");
  await expect(legend).toContainText("Band 2");

  await page.getByRole("switch", { name: "Show measurements" }).click();

  await expect(page.locator(".scatterlayer .points path")).toHaveCount(0);
  await expect(legend).not.toContainText("Measurements");
  await expect(page.locator(".scatterlayer .trace")).toHaveCount(2);

  await page.getByRole("switch", { name: "Show measurements" }).click();

  await expect(page.locator(".scatterlayer .points path")).toHaveCount(POINTS);
});

test("new values update the same drawing rather than a new one", async ({
  page,
}) => {
  await openChart(page);
  const before = await modelPath(page).getAttribute("d");
  await page
    .locator(".main-svg")
    .first()
    .evaluate((element) => {
      element.setAttribute("data-same-drawing", "yes");
    });

  await page.getByRole("button", { name: "Move" }).click();

  await expect.poll(() => modelPath(page).getAttribute("d")).not.toBe(before);
  await expect(page.locator('.main-svg[data-same-drawing="yes"]')).toHaveCount(
    1,
  );
});

test("the chart and its empty state have the same height", async ({ page }) => {
  await openChart(page);
  const chart = await page
    .locator(".main-svg")
    .first()
    .evaluate((element) => element.getBoundingClientRect().height);
  expect(chart).toBe(480);

  await page.goto(`${FIXTURE}?empty`);

  const empty = await page
    .getByText("No data yet")
    .locator("..")
    .evaluate((element) => element.getBoundingClientRect().height);
  expect(empty).toBe(480);
});

test("a screen reader gets the description, as the drawing is one image", async ({
  page,
}) => {
  await openChart(page);

  await expect(
    page.getByRole("img", { name: "Chart of S against temperature" }),
  ).toBeVisible();
});

test("the chart follows the width of its container", async ({ page }) => {
  await openChart(page);
  const widthAt = () =>
    page
      .locator(".main-svg")
      .first()
      .evaluate((element) => element.getBoundingClientRect().width);
  const wide = await widthAt();

  await page.locator("main").evaluate((element) => {
    (element as HTMLElement).style.width = "500px";
  });
  await page.evaluate(() => window.dispatchEvent(new Event("resize")));

  await expect.poll(widthAt).toBeLessThan(wide);
  await expect
    .poll(async () =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
});

test("an empty state downloads no Plotly", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));

  await page.goto(`${FIXTURE}?empty`);

  await expect(page.getByText("No data yet")).toBeVisible();
  await expect(page.locator(".main-svg")).toHaveCount(0);
  expect(requests.filter((url) => url.includes("plotly"))).toEqual([]);
});

test("a failed download says so, and draws nothing", async ({ page }) => {
  await page.route(/plotly/, (route) => route.abort());

  await page.goto(FIXTURE);

  await expect(page.getByText("The chart could not load")).toBeVisible();
  await expect(page.locator(".main-svg")).toHaveCount(0);
});

test("a picture of the chart, to compare with the design", async ({ page }) => {
  await openChart(page);
  await page
    .locator("figure")
    .screenshot({ path: "test-results/chart.png", animations: "disabled" });
});
