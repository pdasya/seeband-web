// @vitest-environment node
import { expect, test } from "vitest";

import type { CalcResponse } from "@/api/client";
import { withSentRmse } from "@/model/useLiveCurves";

const answer = {
  temperature_k: [100],
  curves: {},
  known_issues: [],
  rmse: {
    seebeck: { value: 1, unit: "uV/K" },
    resistivity: { value: 2, unit: "%" },
  },
  issues: [
    { scope: "rmse", quantity: "resistivity", temperature_k: [100], code: "x" },
    {
      scope: "curve",
      quantity: "hall_m3_per_c",
      temperature_k: [100],
      code: "y",
    },
  ],
} as unknown as CalcResponse;

test("an answer keeps only the RMSE of the measurements the current request sends", () => {
  const kept = withSentRmse(answer, new Set(["seebeck"]));
  expect(Object.keys(kept?.rmse ?? {})).toEqual(["seebeck"]);
  // RMSE issues of removed data go too; curve issues stay.
  expect(kept?.issues?.map((issue) => issue.scope)).toEqual(["curve"]);
});

test("an answer for the same measurements is kept as it is", () => {
  expect(withSentRmse(answer, new Set(["seebeck", "resistivity"]))).toBe(
    answer,
  );
  expect(withSentRmse(null, new Set())).toBeNull();
});
