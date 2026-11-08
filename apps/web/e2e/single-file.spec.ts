import { expect, test, type Page } from "@playwright/test";

import { fitBadges } from "./support/fitScreen";
import { serveModels } from "./support/models";

const TABLE =
  "T,S,rho,R_H\n100,1e-4,1e-5,1e-7\n200,2e-4,2e-5,2e-7\n300,3e-4,3e-5,3e-7\n";
const measurement = {
  temperature_k: [100, 200, 300],
  values: [1, 2, 3],
  points: 3,
  min_temperature_k: 100,
  max_temperature_k: 300,
};
const ALL_MAPPING = [
  { column: 0, role: "temperature" },
  { column: 1, role: "seebeck" },
  { column: 2, role: "resistivity" },
  { column: 3, role: "hall" },
];

function parsed(overrides: object = {}) {
  return {
    headers: ["T", "S", "rho", "R_H"],
    column_count: 4,
    row_count: 3,
    preview: [
      [100, 1e-4, 1e-5, 1e-7],
      [200, 2e-4, 2e-5, 2e-7],
      [300, 3e-4, 3e-5, 3e-7],
    ],
    mapping: ALL_MAPPING,
    measurements: {
      seebeck: measurement,
      resistivity: measurement,
      hall: measurement,
    },
    errors: [],
    warnings: [],
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    ...overrides,
  };
}

async function openSingleFile(page: Page) {
  await serveModels(page);
  await page.goto("/fit");
  await page.getByRole("tab", { name: "Single file" }).click();
}

async function choose(page: Page, name = "all.csv", text = TABLE) {
  await page.locator('input[type="file"]').setInputFiles({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(text),
  });
}

async function pickRole(page: Page, column: string, role: string) {
  await page
    .getByRole("combobox", { name: `Quantity for column ${column}` })
    .click();
  await page.getByRole("option", { name: role, exact: true }).click();
}

const slot = (page: Page) => page.locator('[data-file-slot="table"]');

test("detected columns show, with chips and a preview", async ({ page }) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({ json: parsed() }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(slot(page).getByText("all.csv")).toBeVisible();
  await expect(slot(page).getByText("3 rows · 4 columns")).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Quantity for column S" }),
  ).toHaveText("S");
  await expect(
    page.getByRole("combobox", { name: "Quantity for column rho" }),
  ).toHaveText("ρ");
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await expect(page.getByText("R_H · 3 points")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "T ← T" })).toBeVisible();
  await expect(
    page
      .locator('table:not([aria-label="Parameters in use"])')
      .getByRole("row"),
  ).toHaveCount(4);
  await expect(page.getByRole("cell", { name: "1,000e-4" })).toBeVisible();
});

test("the panel says what each source expects, with its units", async ({
  page,
}) => {
  await page.goto("/fit");
  await expect(
    page.getByText("Each file: T in K and the value."),
  ).toBeVisible();

  await page.getByRole("tab", { name: "Single file" }).click();

  await expect(page.getByText("One table: a column for T in K")).toBeVisible();
  await expect(
    page.getByText("S in V/K, ρ in Ω·m, R_H in m³/C."),
  ).toBeVisible();
  await expect(page.getByText("Each file: T in K")).toHaveCount(0);
});

test("the first read sends no mapping, so that the server suggests one", async ({
  page,
}) => {
  const bodies: unknown[] = [];
  await page.route("**/api/parse", (route) => {
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ json: parsed() });
  });
  await openSingleFile(page);

  await choose(page);

  await expect(page.getByText("S · 3 points")).toBeVisible();
  expect(bodies).toEqual([{ text: TABLE }]);
});

test("a change sends the text again with the new mapping, and ignoring drops a column", async ({
  page,
}) => {
  const bodies: { text: string; mapping?: unknown[] }[] = [];
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as {
      text: string;
      mapping?: { column: number; role: string }[];
    };
    bodies.push(body);
    return route.fulfill({
      json: parsed({
        mapping: body.mapping ?? ALL_MAPPING,
        measurements:
          body.mapping === undefined
            ? {
                seebeck: measurement,
                resistivity: measurement,
                hall: measurement,
              }
            : { seebeck: measurement, resistivity: measurement },
      }),
    });
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("R_H · 3 points")).toBeVisible();

  await pickRole(page, "R_H", "Ignore");

  await expect(page.getByText("R_H · not found")).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Quantity for column R_H" }),
  ).toHaveText("Ignore");
  expect(bodies).toHaveLength(2);
  expect(bodies[1]?.text).toBe(TABLE);
  expect(bodies[1]?.mapping).toEqual(ALL_MAPPING.slice(0, 3));
});

test("a mapping with no temperature shows its error, and keeps the choice", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { mapping?: object[] };
    return route.fulfill({
      json:
        body.mapping === undefined
          ? parsed()
          : parsed({
              mapping: body.mapping,
              measurements: {},
              errors: [{ code: "missing_temperature" }],
            }),
    });
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await pickRole(page, "T", "Ignore");

  await expect(page.getByRole("alert")).toContainText("Check the mapping.");
  await expect(page.getByRole("alert")).toContainText(
    "No column holds the temperature",
  );
  await expect(page.getByText("S · not found")).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Quantity for column T" }),
  ).toHaveText("Ignore");
});

test("a quantity used twice shows its error", async ({ page }) => {
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { mapping?: object[] };
    return route.fulfill({
      json:
        body.mapping === undefined
          ? parsed()
          : parsed({
              mapping: body.mapping,
              measurements: {},
              errors: [{ code: "repeated_role" }],
            }),
    });
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await pickRole(page, "rho", "S");

  await expect(page.getByRole("alert")).toContainText(
    "A quantity is assigned twice",
  );
});

test("a repeated temperature is a warning, and the data load", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        warnings: [{ code: "duplicate_temperature", column: 0 }],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(page.getByText("A temperature is repeated.")).toBeVisible();
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a file with no header names its columns by number", async ({ page }) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        headers: undefined,
        mapping: [{ column: 0, role: "temperature" }],
        measurements: {},
        warnings: [{ code: "columns_need_assigning" }],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(
    page.getByRole("combobox", { name: "Quantity for column Column 2" }),
  ).toHaveText("Ignore");
  await expect(
    page.getByText("More than two columns with no header"),
  ).toBeVisible();
});

test("a broken file shows its error, with no columns to map", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        headers: undefined,
        column_count: 0,
        row_count: 0,
        preview: [],
        mapping: [],
        measurements: {},
        errors: [{ code: "no_data" }],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(page.getByRole("alert")).toContainText("No rows of numbers");
  await expect(
    page.getByRole("combobox", { name: /^Quantity for column/ }),
  ).toHaveCount(0);
  await expect(
    page.locator('table:not([aria-label="Parameters in use"])'),
  ).toHaveCount(0);
});

test("a server that is down says so, and a wrong type sends nothing", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return route.fulfill({ status: 502, contentType: "text/plain", body: "" });
  });
  await openSingleFile(page);

  await choose(page, "sheet.xlsx");
  await expect(page.getByRole("alert")).toContainText(".txt, .csv or .dat");
  expect(requests).toBe(0);

  await choose(page);
  await expect(page.getByRole("alert")).toContainText(
    "server is not responding",
  );
});

test("a failed change of mapping shows no data as loaded", async ({ page }) => {
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { mapping?: object[] };
    return body.mapping === undefined
      ? route.fulfill({ json: parsed() })
      : route.fulfill({ status: 502, contentType: "text/plain", body: "" });
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await pickRole(page, "R_H", "Ignore");

  await expect(page.getByRole("alert")).toContainText(
    "server is not responding",
  );
  await expect(page.getByText("S · not found")).toBeVisible();
  await expect(page.getByText("S · 3 points")).toHaveCount(0);
});

test("a table with no quantity assigned asks for one, in an alert", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        headers: undefined,
        mapping: [{ column: 0, role: "temperature" }],
        measurements: {},
        warnings: [
          { code: "columns_need_assigning" },
          { code: "few_rows" },
          { code: "no_quantity" },
        ],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Check the mapping.");
  await expect(alert).toContainText("No column holds a quantity yet");
  await expect(alert).toContainText("More than two columns with no header");
  await expect(page.getByText("neural net")).toHaveCount(0);
});

test("an error in the file is not called a problem of the mapping", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        measurements: {},
        errors: [{ code: "not_numeric", line: 3, column: 0 }],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(page.getByRole("alert")).toContainText("Check the file.");
  await expect(page.getByRole("alert")).toContainText("Line 3");
});

test("each column used twice is named", async ({ page }) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({
      json: parsed({
        measurements: {},
        errors: [
          { code: "repeated_role", column: 1 },
          { code: "repeated_role", column: 2 },
        ],
      }),
    }),
  );
  await openSingleFile(page);

  await choose(page);

  await expect(page.getByRole("alert")).toContainText("Check the mapping.");
  await expect(page.getByRole("alert")).toContainText("Column 2: A quantity");
  await expect(page.getByRole("alert")).toContainText("Column 3: A quantity");
});

test("a file still being read does not come back after a change of source", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return route.fulfill({ json: parsed() });
  });
  await openSingleFile(page);
  // A read of a file that takes time, which the page can leave during.
  await page.evaluate(() => {
    const real = Blob.prototype.arrayBuffer;
    Blob.prototype.arrayBuffer = async function slow(this: Blob) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      return real.call(this);
    };
  });

  await choose(page);
  await expect(page.getByText("Reading…").first()).toBeVisible();
  await page.getByRole("tab", { name: "Separate files" }).click();
  await page.waitForTimeout(700);

  expect(requests).toBe(0);
  await expect(page.locator('input[type="file"]')).toHaveCount(3);
  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(page.getByText("A table with several columns")).toBeVisible();
});

test("of two files, the last chosen counts, even if the first takes longer", async ({
  page,
}) => {
  const texts: string[] = [];
  await page.route("**/api/parse", (route) => {
    texts.push((route.request().postDataJSON() as { text: string }).text);
    return route.fulfill({ json: parsed() });
  });
  await openSingleFile(page);
  await page.evaluate(() => {
    const real = Blob.prototype.arrayBuffer;
    Blob.prototype.arrayBuffer = async function slow(this: Blob) {
      if (this instanceof File && this.name === "slow.csv") {
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      return real.call(this);
    };
    const drop = (name: string) => {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(new File([name], name));
      document.querySelector('[data-file-slot="table"]')?.dispatchEvent(
        new DragEvent("drop", {
          bubbles: true,
          cancelable: true,
          dataTransfer,
        }),
      );
    };
    drop("slow.csv");
    setTimeout(() => {
      drop("fast.csv");
    }, 50);
  });

  await expect(slot(page).getByText("fast.csv")).toBeVisible();
  await page.waitForTimeout(800);

  expect(texts).toEqual(["fast.csv"]);
  await expect(slot(page).getByText("fast.csv")).toBeVisible();
  await expect(slot(page).getByText("slow.csv")).toHaveCount(0);
});

test("a read can be cancelled, which stops its request", async ({ page }) => {
  let answer: (() => Promise<void>) | undefined;
  await page.route("**/api/parse", (route) => {
    answer = () => route.fulfill({ json: parsed() });
  });
  await openSingleFile(page);
  const failed = page.waitForEvent("requestfailed");

  await choose(page, "slow.csv");
  await expect.poll(() => answer !== undefined).toBe(true);
  await page.getByRole("button", { name: "Cancel reading" }).click();

  expect((await failed).failure()?.errorText).toContain("ABORTED");
  await expect(page.getByText("A table with several columns")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await answer?.().catch(() => undefined);
  await expect(
    page.getByRole("combobox", { name: /^Quantity for column/ }),
  ).toHaveCount(0);
});

test("an older mapping's request is stopped by a newer one", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { mapping?: object[] };
    return body.mapping === undefined
      ? route.fulfill({ json: parsed() })
      : undefined;
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();
  const failed = page.waitForEvent("requestfailed");

  await pickRole(page, "rho", "Ignore");
  await pickRole(page, "R_H", "Ignore");

  expect((await failed).failure()?.errorText).toContain("ABORTED");
});

test("a late answer to an older mapping does not overwrite a newer one", async ({
  page,
}) => {
  const waiting: {
    mapping?: { role: string }[];
    fulfill: () => Promise<void>;
  }[] = [];
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as {
      mapping?: { column: number; role: string }[];
    };
    if (body.mapping === undefined) {
      return route.fulfill({ json: parsed() });
    }
    waiting.push({
      mapping: body.mapping,
      fulfill: () =>
        route.fulfill({
          json: parsed({
            mapping: body.mapping,
            measurements: body.mapping?.some((m) => m.role === "hall")
              ? { hall: measurement }
              : { seebeck: measurement },
          }),
        }),
    });
    return undefined;
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await pickRole(page, "rho", "Ignore");
  await pickRole(page, "R_H", "Ignore");
  await expect.poll(() => waiting.length).toBe(2);

  await waiting[1]?.fulfill();
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await waiting[0]?.fulfill();

  await expect(page.getByText("R_H · not found")).toBeVisible();
  await expect(page.getByText("S · 3 points")).toBeVisible();
});

test("removing the file clears everything, and changing source keeps it", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({ json: parsed() }),
  );
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await page.getByRole("button", { name: "Remove file" }).click();
  await expect(
    page.getByRole("combobox", { name: /^Quantity for column/ }),
  ).toHaveCount(0);
  await expect(page.getByText("A table with several columns")).toBeVisible();

  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await page.getByRole("tab", { name: "Separate files" }).click();

  await expect(page.locator('input[type="file"]')).toHaveCount(3);
  await expect(fitBadges(page)).toHaveText("Missing data: S, ρ");
  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await expect(slot(page).getByText("all.csv")).toBeVisible();
});

test("each way keeps its own files, and only the open one counts", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { expected?: string };
    return route.fulfill({
      json:
        body.expected === "seebeck"
          ? parsed({
              measurements: {
                seebeck: {
                  temperature_k: [100],
                  values: [1e-4],
                  points: 1,
                  min_temperature_k: 100,
                  max_temperature_k: 100,
                },
              },
            })
          : parsed(),
    });
  });
  await serveModels(page);
  await page.goto("/fit");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "s.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("T S\n100 1\n"),
    });
  await expect(page.getByText("s.txt", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(page.getByText("s.txt", { exact: true })).toHaveCount(0);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await page.getByRole("tab", { name: "Separate files" }).click();
  await expect(page.getByText("s.txt", { exact: true })).toBeVisible();
  await expect(page.getByText("all.csv")).toHaveCount(0);

  await page.getByRole("tab", { name: "Single file" }).click();
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await expect(page.getByText("s.txt", { exact: true })).toHaveCount(0);
});

test("the chosen mapping stays when coming back", async ({ page }) => {
  const bodies: { mapping?: string[] }[] = [];
  await page.route("**/api/parse", (route) => {
    const body = route.request().postDataJSON() as { mapping?: string[] };
    bodies.push(body);
    return route.fulfill({
      json: parsed(body.mapping === undefined ? {} : { mapping: body.mapping }),
    });
  });
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();
  await page.getByRole("combobox", { name: "Quantity for column R_H" }).click();
  await page.getByRole("option", { name: "Ignore", exact: true }).click();
  await expect.poll(() => bodies.length).toBe(2);
  const requests = bodies.length;

  await page.getByRole("tab", { name: "Separate files" }).click();
  await page.getByRole("tab", { name: "Single file" }).click();

  await expect(
    page.getByRole("combobox", { name: "Quantity for column R_H" }),
  ).toHaveText("Ignore");
  // The file is not read again.
  expect(bodies).toHaveLength(requests);
});

test("the table stays when moving to another screen and back", async ({
  page,
}) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({ json: parsed() }),
  );
  await openSingleFile(page);
  await choose(page);
  await expect(page.getByText("S · 3 points")).toBeVisible();

  await page.getByRole("link", { name: "Results", exact: true }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(page.getByRole("tab", { name: "Single file" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("S · 3 points")).toBeVisible();
});
