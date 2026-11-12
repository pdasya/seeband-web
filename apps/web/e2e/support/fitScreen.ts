import { expect, type Page } from "@playwright/test";

/** One of the four charts, counted from 1. */
export const chart = (page: Page, index = 1) =>
  page.getByRole("region", { name: `Chart ${String(index)}` });

/** Sets what a chart shows, by the name in its select. */
export async function show(page: Page, label: string, index = 1) {
  await page
    .getByRole("combobox", {
      name: `Quantity shown in chart ${String(index)}`,
    })
    .click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

/** Opens the data, which a user may have folded with Hide. */
export async function openData(page: Page) {
  const details = page.getByRole("button", { name: "Details" });
  if (await details.isVisible()) {
    await details.click();
  }
  await expect(page.getByRole("heading", { name: "Data" })).toBeVisible();
}

/** The badges of the fit panel: its status, or the data it still needs. None before a fit. */
export const fitBadges = (page: Page) =>
  page
    .getByRole("region", { name: "Fit", exact: true })
    .locator('[data-slot="badge"]');
