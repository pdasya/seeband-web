import { expect, test, type Page, type Route } from "@playwright/test";

import { serveModels } from "./support/models";

const SEEBECK = {
  temperature_k: [100, 200, 300],
  values: [1e-4, 2e-4, 3e-4],
  points: 3,
  min_temperature_k: 100,
  max_temperature_k: 300,
};

function parsed(overrides: object = {}) {
  return {
    headers: ["T", "S"],
    column_count: 2,
    row_count: 3,
    preview: [],
    mapping: [],
    measurements: { seebeck: SEEBECK },
    errors: [],
    warnings: [],
    warnings_omitted: 0,
    interpolated: {},
    interpolation_failed: [],
    ...overrides,
  };
}

const answerWith =
  (body: object, status = 200) =>
  (route: Route) =>
    route.fulfill({ status, json: body });

// The name also appears in a hidden status for a screen reader, so this looks only at the cards.
const slots = (page: Page) => page.locator("[data-file-slot]");

const seebeckInput = (page: Page) => page.locator('input[type="file"]').nth(0);

async function choose(page: Page, name: string, text = "T S\n100 1e-4\n") {
  await seebeckInput(page).setInputFiles({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(text),
  });
}

test.beforeEach(async ({ page }) => {
  await serveModels(page);
  await page.goto("/fit");
});

test("shows three slots, as the design does", async ({ page }) => {
  await expect(page.locator('input[type="file"]')).toHaveCount(3);
  for (const title of [
    "Seebeck coefficient",
    "Resistivity",
    "Hall coefficient",
  ]) {
    await expect(page.getByText(title)).toBeVisible();
  }
});

test("a file becomes a card with its name, points and range, and can go", async ({
  page,
}) => {
  await page.route("**/api/parse", answerWith(parsed()));

  await choose(page, "my_S.txt");

  await expect(slots(page).getByText("my_S.txt")).toBeVisible();
  await expect(
    slots(page).getByText("3 points · 100–300 K · V/K"),
  ).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(2);

  await page.getByRole("button", { name: "Remove file S" }).click();

  await expect(slots(page).getByText("my_S.txt")).toHaveCount(0);
  await expect(page.locator('input[type="file"]')).toHaveCount(3);
});

test("the request says which quantity the slot wants, and holds the text", async ({
  page,
}) => {
  const bodies: unknown[] = [];
  await page.route("**/api/parse", (route) => {
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ json: parsed() });
  });

  await choose(page, "a.txt", "T S\n100 1e-4\n");

  await expect(slots(page).getByText("3 points")).toBeVisible();
  expect(bodies).toEqual([{ text: "T S\n100 1e-4\n", expected: "seebeck" }]);
});

test("a dropped file loads, and the page does not open it", async ({
  page,
}) => {
  await page.route("**/api/parse", answerWith(parsed()));
  const url = page.url();

  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["T S\n"], "dropped.csv"));
    const target = document.querySelector("label");
    target?.dispatchEvent(
      new DragEvent("dragover", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
    target?.dispatchEvent(
      new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
  });

  await expect(slots(page).getByText("dropped.csv")).toBeVisible();
  expect(page.url()).toBe(url);
});

test("several files dropped at once are refused, with no request", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return route.fulfill({ json: parsed() });
  });

  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["a"], "a.txt"));
    transfer.items.add(new File(["b"], "b.txt"));
    document.querySelector("label")?.dispatchEvent(
      new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
  });

  await expect(page.getByRole("alert")).toContainText(
    "Drop one file at a time",
  );
  expect(requests).toBe(0);
});

test("a file dropped beside the slots does not leave the page, and text can go into a field", async ({
  page,
}) => {
  const defaultPrevented = await page.evaluate(() => {
    const drop = (build: (transfer: DataTransfer) => void) => {
      const dataTransfer = new DataTransfer();
      build(dataTransfer);
      const event = new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer,
      });
      document.body.dispatchEvent(event);
      return event.defaultPrevented;
    };
    return {
      file: drop((transfer) => {
        transfer.items.add(new File(["x"], "a.txt"));
      }),
      text: drop((transfer) => {
        transfer.setData("text/plain", "words");
      }),
    };
  });

  expect(defaultPrevented).toEqual({ file: true, text: false });
});

test("dragged text does not light up a slot", async ({ page }) => {
  const lit = await page.evaluate(() => {
    const dataTransfer = new DataTransfer();
    dataTransfer.setData("text/plain", "words");
    const event = new DragEvent("dragover", {
      bubbles: true,
      cancelable: true,
      dataTransfer,
    });
    document.querySelector("label")?.dispatchEvent(event);
    return event.defaultPrevented;
  });

  expect(lit).toBe(false);
});

test("a broken file shows a specific error, with its line", async ({
  page,
}) => {
  await page.route(
    "**/api/parse",
    answerWith(
      parsed({
        measurements: {},
        errors: [{ code: "decimal_comma", line: 3, column: 0 }],
      }),
    ),
  );

  await choose(page, "broken.txt");

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("broken.txt");
  await expect(alert).toContainText("Line 3: This looks like decimal commas");
  await expect(page.locator('input[type="file"]')).toHaveCount(3);
});

test("many errors show the first few and a count", async ({ page }) => {
  const errors = Array.from({ length: 7 }, (_, index) => ({
    code: "not_numeric",
    line: index + 2,
  }));
  await page.route(
    "**/api/parse",
    answerWith(parsed({ measurements: {}, errors })),
  );

  await choose(page, "broken.txt");

  await expect(page.getByRole("alert").locator("li")).toHaveCount(4);
  await expect(page.getByRole("alert")).toContainText("More problems: 4");
});

test("a file with no column for the quantity says so", async ({ page }) => {
  await page.route(
    "**/api/parse",
    answerWith(
      parsed({ measurements: {}, warnings: [{ code: "expected_not_found" }] }),
    ),
  );

  await choose(page, "other.txt");

  await expect(page.getByRole("alert")).toContainText(
    "no column for this quantity",
  );
});

test("warnings appear under the card, which stays", async ({ page }) => {
  await page.route(
    "**/api/parse",
    answerWith(
      parsed({ warnings: [{ code: "unsorted_temperature", column: 0 }] }),
    ),
  );

  await choose(page, "a.txt");

  await expect(slots(page).getByText("3 points")).toBeVisible();
  await expect(page.getByText("Rows were not in order of T")).toBeVisible();
});

const REFUSALS = [
  {
    name: "a limit",
    status: 429,
    body: { code: "rate_limited", message: "x", details: [] },
    text: "Too many files",
  },
  {
    name: "too many rows",
    status: 422,
    body: {
      code: "invalid_parse_request",
      message: "x",
      details: [
        { location: ["body", "text"], code: "too_many_rows", message: "x" },
      ],
    },
    text: "more than 2000 rows",
  },
  {
    name: "a server error",
    status: 500,
    body: { code: "internal_error", message: "SECRET-VALUE", details: [] },
    text: "server is not responding",
  },
  {
    name: "any other",
    status: 422,
    body: {
      code: "invalid_parse_request",
      message: "SECRET-VALUE",
      details: [],
    },
    text: "could not be read",
  },
];

for (const { name, status, body, text } of REFUSALS) {
  test(`a refusal for ${name} has its message, not the server's`, async ({
    page,
  }) => {
    await page.route("**/api/parse", answerWith(body, status));

    await choose(page, "a.txt");

    await expect(page.getByRole("alert")).toContainText(text);
    await expect(page.getByRole("alert")).not.toContainText("SECRET-VALUE");
  });
}

test("a server that is down does not blame the file", async ({ page }) => {
  await page.route("**/api/parse", (route) =>
    route.fulfill({ status: 502, contentType: "text/plain", body: "" }),
  );

  await choose(page, "fine.txt");

  await expect(page.getByRole("alert")).toContainText(
    "server is not responding",
  );
  await expect(page.getByRole("alert")).not.toContainText("could not be read");
});

test("two columns with the same problem are told apart, with no console error", async ({
  page,
}) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      problems.push(message.text());
    }
  });
  await page.route(
    "**/api/parse",
    answerWith(
      parsed({
        warnings: [
          { code: "unit_differs", column: 2 },
          { code: "unit_differs", column: 3 },
          { code: "few_rows" },
          { code: "few_rows" },
        ],
      }),
    ),
  );

  await choose(page, "a.txt");

  await expect(
    page.getByText("Column 3: A column with another unit"),
  ).toBeVisible();
  await expect(
    page.getByText("Column 4: A column with another unit"),
  ).toBeVisible();
  expect(problems.filter((text) => text.includes("same key"))).toEqual([]);
});

test("a file of another quantity says so, without unrelated warnings", async ({
  page,
}) => {
  await page.route(
    "**/api/parse",
    answerWith(
      parsed({
        measurements: { resistivity: SEEBECK },
        warnings: [{ code: "few_rows" }, { code: "expected_not_found" }],
      }),
    ),
  );

  await choose(page, "rho.txt");

  await expect(page.getByRole("alert")).toContainText(
    "no column for this quantity",
  );
  await expect(page.getByRole("alert")).not.toContainText("neural net");
});

test("a load is told to a screen reader, in a place that was already there", async ({
  page,
}) => {
  await page.route("**/api/parse", answerWith(parsed()));
  const status = page.getByRole("status").first();
  await expect(status).toBeEmpty();

  await choose(page, "a.txt");

  await expect(status).toContainText("Seebeck coefficient: a.txt");
  await expect(status).toContainText("3 points");
});

test("focus stays in the slot through a choice and a removal", async ({
  page,
}) => {
  await page.route("**/api/parse", answerWith(parsed()));
  await seebeckInput(page).focus();

  await choose(page, "a.txt");

  const remove = page.getByRole("button", { name: "Remove file S" });
  await expect(remove).toBeFocused();

  await page.keyboard.press("Enter");

  await expect(seebeckInput(page)).toBeFocused();
});

test("focus comes back to the slot after a failure", async ({ page }) => {
  await page.route("**/api/parse", (route) => route.abort());
  await seebeckInput(page).focus();

  await choose(page, "a.txt");

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(seebeckInput(page)).toBeFocused();
});

test("a lost connection has its message", async ({ page }) => {
  await page.route("**/api/parse", (route) => route.abort());

  await choose(page, "a.txt");

  await expect(page.getByRole("alert")).toContainText("could not be reached");
});

test("a wrong kind of file is refused with no request", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return route.fulfill({ json: parsed() });
  });

  await choose(page, "sheet.xlsx");

  await expect(page.getByRole("alert")).toContainText(".txt, .csv or .dat");
  expect(requests).toBe(0);
});

test("a read under way shows, and a second file takes over from it", async ({
  page,
}) => {
  const waiting: Route[] = [];
  await page.route("**/api/parse", (route) => {
    waiting.push(route);
  });

  await choose(page, "first.txt");
  const seebeckStatus = page.getByRole("status").first();
  await expect(seebeckStatus).toContainText("first.txt");
  await expect(seebeckStatus).toContainText("Reading");

  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["T S\n"], "second.txt"));
    document.querySelector('[data-file-slot="seebeck"]')?.dispatchEvent(
      new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
  });
  await expect(seebeckStatus).toContainText("second.txt");
  await expect.poll(() => waiting.length).toBe(2);

  await waiting[1]?.fulfill({ json: parsed() });
  await expect(slots(page).getByText("second.txt")).toBeVisible();

  await waiting[0]?.fulfill({ json: parsed() }).catch(() => undefined);
  await expect(slots(page).getByText("first.txt")).toHaveCount(0);
});

test("a read can be cancelled, which stops its request and leaves the slot empty", async ({
  page,
}) => {
  let answer: (() => Promise<void>) | undefined;
  await page.route("**/api/parse", (route) => {
    answer = () => route.fulfill({ json: parsed() });
  });
  const failed = page.waitForEvent("requestfailed");

  await choose(page, "slow.txt");
  await expect.poll(() => answer !== undefined).toBe(true);
  await page.getByRole("button", { name: "Cancel reading S" }).click();

  expect((await failed).failure()?.errorText).toContain("ABORTED");
  await expect(slots(page).getByText("slow.txt")).toHaveCount(0);
  await expect(page.locator('input[type="file"]')).toHaveCount(3);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(seebeckInput(page)).toBeFocused();
  await answer?.().catch(() => undefined);
  await expect(slots(page).getByText("3 points")).toHaveCount(0);
});

test("choosing the same file again reads it again", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return route.fulfill({ json: parsed() });
  });

  await choose(page, "same.txt");
  await expect(slots(page).getByText("3 points")).toBeVisible();
  await page.getByRole("button", { name: "Remove file S" }).click();
  await choose(page, "same.txt");

  await expect(slots(page).getByText("3 points")).toBeVisible();
  expect(requests).toBe(2);
});

test("after a failure, the same file can be chosen again", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/parse", (route) => {
    requests += 1;
    return requests === 1 ? route.abort() : route.fulfill({ json: parsed() });
  });

  await choose(page, "same.txt");
  await expect(page.getByRole("alert")).toBeVisible();
  await choose(page, "same.txt");

  await expect(slots(page).getByText("3 points")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("data stay when moving to another screen and back", async ({ page }) => {
  await page.route("**/api/parse", answerWith(parsed()));
  await choose(page, "kept.txt");
  await expect(slots(page).getByText("kept.txt")).toBeVisible();

  await page.getByRole("link", { name: "Results" }).click();
  await page.getByRole("link", { name: "Model fit" }).click();

  await expect(slots(page).getByText("kept.txt")).toBeVisible();
});

test("a slot shows focus when reached with the keyboard", async ({ page }) => {
  // The switch of the source and its panel come first.
  await page.getByRole("tab", { name: "Separate files" }).focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");

  await expect(seebeckInput(page)).toBeFocused();
  const outline = await page
    .locator("label")
    .first()
    .evaluate((label) => getComputedStyle(label).outlineStyle);

  expect(outline).toBe("solid");
});
