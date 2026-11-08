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
    "/api/demo": {
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

/** The demo, as the contract's example holds it. */
export const DEMO = Object.values(
  contract.paths["/api/demo"].get.responses["200"].content["application/json"]
    .examples,
)[0]?.value as { measurements: Record<string, { points: number }> };

/** A curve of 3 points, for tests about other things. Later routes in a test take over from it. */
export const CALC = {
  temperature_k: [100, 300, 500],
  curves: { seebeck_v_per_k: [1e-4, 2e-4, 1.5e-4] },
  known_issues: [],
  rmse: {},
};

/** A sketch of the bands, for tests about other things. */
export const BAND_DIAGRAM = {
  wavevector: [-40, 0, 40],
  curves: {
    band_1_energy_k: [-1954, 0, -1954],
    band_2_energy_k: [2954, 1000, 2954],
    fermi_energy_k: [-100, -100, -100],
  },
  known_issues: [],
};

/** Leaves the values as they are, for tests about other things. */
export const NO_GUESS = {
  status: "no_net",
  reason: "temperature_span",
  first_temperature_k: 100,
  last_temperature_k: 200,
  available_ranges: [{ min_temperature_k: 300, max_temperature_k: 800 }],
  warnings: [],
};

export async function serveModels(page: Page) {
  await page.route("**/api/models", (route) => route.fulfill({ json: MODELS }));
  await page.route("**/api/calc", (route) => route.fulfill({ json: CALC }));
  await page.route("**/api/guess", (route) =>
    route.fulfill({ json: NO_GUESS }),
  );
  // A chart shows the bands from the start.
  await page.route("**/api/band-diagram", (route) =>
    route.fulfill({ json: BAND_DIAGRAM }),
  );
}
