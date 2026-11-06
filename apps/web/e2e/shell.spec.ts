import { expect, test } from "@playwright/test";

test("the shared header has its styles, in the design's sizes", async ({
  page,
}) => {
  await page.goto("/app/fit");

  const look = await page.locator("header.sb-header").evaluate((header) => {
    const style = (selector: string) => {
      const element = header.querySelector(selector);
      if (element === null) {
        throw new Error(`No ${selector}`);
      }
      return getComputedStyle(element);
    };
    return {
      border: getComputedStyle(header).borderBottomColor,
      innerDisplay: style(".sb-header__inner").display,
      innerPadding: style(".sb-header__inner").padding,
      logo: style(".sb-header__logo").width,
      name: style(".sb-header__name").fontSize,
      stage: style(".sb-header__stage").fontSize,
      link: style(".sb-header__link").padding,
      current: style('[aria-current="page"]').backgroundColor,
    };
  });

  expect(look).toEqual({
    border: "rgb(228, 228, 231)",
    innerDisplay: "flex",
    innerPadding: "12px 24px",
    logo: "32px",
    name: "16px",
    stage: "12px",
    link: "6px 12px",
    current: "rgb(244, 244, 245)",
  });
});

test("links inside the app stay in the page, and the current one moves", async ({
  page,
}) => {
  await page.goto("/app/fit");
  await page.evaluate(() => {
    (window as unknown as { sameDocument: boolean }).sameDocument = true;
  });

  await page.getByRole("link", { name: "Results" }).click();

  await expect(page).toHaveURL(/\/app\/results$/);
  await expect(page.getByRole("link", { name: "Results" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    await page.evaluate(
      () => (window as unknown as { sameDocument?: boolean }).sameDocument,
    ),
  ).toBe(true);
});

test("links to the public site leave the app", async ({ page }) => {
  await page.goto("/app/fit");

  await expect(page.getByRole("link", { name: "Overview" })).toHaveAttribute(
    "href",
    "/",
  );
  await expect(page.getByRole("link", { name: "Conventions" })).toHaveAttribute(
    "href",
    "/conventions/",
  );
});

test("there is no language switch while the app has one language", async ({
  page,
}) => {
  await page.goto("/app/fit");

  await expect(page.getByRole("radiogroup")).toHaveCount(0);
});
