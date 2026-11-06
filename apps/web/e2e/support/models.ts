import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { Page } from "@playwright/test";

const contract = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../../packages/api-client/openapi.json", import.meta.url),
    ),
    "utf8",
  ),
) as {
  paths: {
    "/api/models": {
      get: {
        responses: {
          "200": {
            content: {
              "application/json": {
                examples: Record<string, { value: unknown }>;
              };
            };
          };
        };
      };
    };
  };
};

/** The real descriptions, as the contract's example holds them. */
export const MODELS = Object.values(
  contract.paths["/api/models"].get.responses["200"].content["application/json"]
    .examples,
)[0]?.value as { models: object[] };

/** A curve of 3 points, for tests about other things. Later routes in a test take over from it. */
export const CALC = {
  temperature_k: [100, 300, 500],
  curves: { seebeck_v_per_k: [1e-4, 2e-4, 1.5e-4] },
  known_issues: [],
  rmse: {},
};

export async function serveModels(page: Page) {
  await page.route("**/api/models", (route) => route.fulfill({ json: MODELS }));
  await page.route("**/api/calc", (route) => route.fulfill({ json: CALC }));
}
