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

export async function serveModels(page: Page) {
  await page.route("**/api/models", (route) => route.fulfill({ json: MODELS }));
}
