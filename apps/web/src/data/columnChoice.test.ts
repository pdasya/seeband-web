// @vitest-environment node
import { describe, expect, test } from "vitest";

import { chosenQuantity, initialRoles, mappingOf } from "@/data/columnChoice";

describe("initialRoles", () => {
  test("two columns take T and the slot's quantity", () => {
    expect(initialRoles(2, "seebeck", false)).toEqual([
      "temperature",
      "seebeck",
    ]);
  });

  test("doubt leaves the second column to the user", () => {
    expect(initialRoles(2, "seebeck", true)).toEqual(["temperature", null]);
  });

  test("more columns leave all but T to the user", () => {
    expect(initialRoles(4, "hall", false)).toEqual([
      "temperature",
      null,
      null,
      null,
    ]);
  });
});

describe("chosenQuantity", () => {
  test("is the one quantity beside T, in any order", () => {
    expect(chosenQuantity(["temperature", "resistivity"])).toBe("resistivity");
    expect(chosenQuantity([null, "hall", "temperature"])).toBe("hall");
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
