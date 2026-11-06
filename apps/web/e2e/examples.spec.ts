import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// Against a real API, as the mock's answers do not depend on the file. See the README.
test.skip(
  process.env.SEEBAND_API_TARGET === undefined,
  "Needs a real API, through SEEBAND_API_TARGET",
);

const EXAMPLES = fileURLToPath(
  new URL(
    "../../../packages/seeband_core/tests/fixtures/examples/",
    import.meta.url,
  ),
);

for (const example of ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]) {
  test(`all files of ${example} load`, async ({ page }) => {
    await page.goto("/app/fit");

    for (const suffix of ["see", "rho", "hall"]) {
      const name = `${example}_${suffix}.txt`;
      // A slot with a file has no input, so the first input left is the next slot.
      await page
        .locator('input[type="file"]')
        .first()
        .setInputFiles(`${EXAMPLES}${name}`);
      await expect(page.getByText(name)).toBeVisible();
    }

    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText(/\d+ points · .* K · V\/K/)).toBeVisible();
    await expect(page.getByText(/\d+ points · .* K · Ω·m/)).toBeVisible();
    await expect(page.getByText(/\d+ points · .* K · m³\/C/)).toBeVisible();
  });
}

test("a broken file shows a specific error from the real parser", async ({
  page,
}) => {
  await page.goto("/app/fit");
  const good = readFileSync(`${EXAMPLES}01_Fe2VAl09Si01_see.txt`, "utf8");
  const lines = good.split("\n");
  lines[3] = "300 not-a-number";

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "broken.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(lines.join("\n")),
    });

  await expect(page.getByRole("alert")).toContainText("broken.txt");
  await expect(page.getByRole("alert")).toContainText("Line 4");
});
