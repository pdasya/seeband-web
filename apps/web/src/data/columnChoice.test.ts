// @vitest-environment node
import { describe, expect, test } from "vitest";

import { chosenQuantity, initialRoles, mappingOf } from "@/data/columnChoice";

describe("initialRoles", () => {
  test("takes the first column as T and leaves the quantity to the user", () => {
    expect(initialRoles(2)).toEqual(["temperature", null]);
    expect(initialRoles(4)).toEqual(["temperature", null, null, null]);
  });
});

describe("chosenQuantity", () => {
  test("is the one quantity beside T, in any order", () => {
    expect(chosenQuantity(["temperature", "resistivity"])).toBe("resistivity");
    expect(chosenQuantity([null, "hall", "temperature"])).toBe("hall");
  });

  test("is ρ for σ, which loads as ρ = 1/σ", () => {
    expect(chosenQuantity(["temperature", "conductivity"])).toBe("resistivity");
    expect(
      chosenQuantity(["temperature", "resistivity", "conductivity"]),
    ).toBeNull();
  });

  test("is null with no T, no quantity, two quantities or two T", () => {
    expect(chosenQuantity([null, "seebeck"])).toBeNull();
    expect(chosenQuantity(["temperature", null])).toBeNull();
    expect(chosenQuantity(["temperature", "seebeck", "hall"])).toBeNull();
    expect(chosenQuantity(["temperature", "temperature"])).toBeNull();
    expect(chosenQuantity(["seebeck", "seebeck"])).toBeNull();
  });
});

describe("mappingOf", () => {
  test("leaves out the columns that hold nothing", () => {
    expect(mappingOf([null, "temperature", null, "hall"])).toEqual([
      { column: 1, role: "temperature" },
      { column: 3, role: "hall" },
    ]);
  });
});
