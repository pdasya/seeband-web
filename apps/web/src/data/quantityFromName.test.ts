// @vitest-environment node
import { describe, expect, test } from "vitest";

import { quantityFromName } from "@/data/quantityFromName";

describe("quantityFromName", () => {
  test.each([
    ["01_Fe2VAl09Si01_see.txt", "seebeck"],
    ["03_AWI32_SI_rho.txt", "resistivity"],
    ["02_SiP_hall.txt", "hall"],
    ["sample-Seebeck.dat", "seebeck"],
    ["RH 300K.csv", "hall"],
    ["Resistivity_run2.txt", "resistivity"],
    ["BSO_sigma.txt", "conductivity"],
    ["conductivity 2.csv", "conductivity"],
  ] as const)("reads %s as %s", (name, quantity) => {
    expect(quantityFromName(name)).toBe(quantity);
  });

  test.each([
    "data.txt",
    "s_sample.txt",
    // Words that only hold one of the names are not it.
    "research.txt",
    "seebeck_and_rho.txt",
    "rho_sigma.txt",
  ])("names nothing in %s", (name) => {
    expect(quantityFromName(name)).toBeNull();
  });
});
