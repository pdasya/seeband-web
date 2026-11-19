import { expect, test } from "vitest";

import { ApiError } from "@/api/errors";
import { failureText } from "@/model/ChartGrid";

test.each([
  ["chemical_potential_zero_mass", "nonzero mass ratio m₂/m₁"],
  ["chemical_potential_spb_fermi_energy", "E_F above 0 for m > 0 or below 0"],
  ["chemical_potential_dpb_fermi_energy", "the higher band edge, max(0, E_g)"],
])("explains calculation detail %s", (code, advice) => {
  const failure = new ApiError(
    422,
    "calculation_failed",
    "details from server",
    [
      {
        code,
        message: "details from server",
        location: ["body", "parameters"],
      },
    ],
  );

  expect(failureText(failure)).toContain(advice);
  expect(failureText(failure)).not.toContain("details from server");
});

test("a calculation failure with no reason has the general message", () => {
  expect(
    failureText(new ApiError(422, "calculation_failed", "details from server")),
  ).toBe("The calculation has no result for these parameters.");
});
