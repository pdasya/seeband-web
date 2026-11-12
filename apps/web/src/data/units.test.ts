// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, test } from "vitest";

import { mappingOf } from "@/data/columnChoice";
import {
  UNITS_OF,
  looksLikeAnotherUnit,
  unitOf,
  withUnit,
  type Unit,
} from "@/data/units";
import { STRINGS } from "@/strings";

/** The units the contract lets a column have, from `ColumnRole.unit`. */
function contractUnits(): string[] {
  const contract = JSON.parse(
    readFileSync(
      fileURLToPath(
        new URL(
          "../../../../packages/api-client/openapi.json",
          import.meta.url,
        ),
      ),
      "utf8",
    ),
  ) as {
    components: {
      schemas: {
        ColumnRole: {
          properties: { unit: { anyOf: { enum?: string[] }[] } };
        };
      };
    };
  };
  return contract.components.schemas.ColumnRole.properties.unit.anyOf.flatMap(
    (option) => option.enum ?? [],
  );
}

describe("UNITS_OF", () => {
  test("offers every unit of the contract but K, each once, with SI first", () => {
    const offered = Object.values(UNITS_OF).flat();
    expect(new Set(offered).size).toBe(offered.length);
    expect([...offered, "K"].sort()).toEqual(contractUnits().sort());
    expect(UNITS_OF.seebeck[0]).toBe("V/K");
    expect(UNITS_OF.resistivity[0]).toBe("Ohm*m");
    expect(UNITS_OF.hall[0]).toBe("m^3/C");
  });

  test("has a label for every unit", () => {
    for (const unit of contractUnits()) {
      expect(STRINGS.data.units[unit as Unit]).toMatch(/\S/);
    }
  });
});

describe("unitOf", () => {
  test("gives the unit the server read a quantity's column in", () => {
    expect(
      unitOf(
        [
          { column: 0, role: "temperature", unit: "K" },
          { column: 1, role: "seebeck", unit: "uV/K" },
        ],
        "seebeck",
      ),
    ).toBe("uV/K");
  });

  test("falls back to SI with no mapping or no unit", () => {
    expect(unitOf(undefined, "hall")).toBe("m^3/C");
    expect(unitOf([{ column: 1, role: "resistivity" }], "resistivity")).toBe(
      "Ohm*m",
    );
  });
});

describe("withUnit", () => {
  test("changes only the quantity's column", () => {
    expect(
      withUnit(
        [
          { column: 0, role: "temperature", unit: "K" },
          { column: 1, role: "resistivity", unit: "Ohm*m" },
        ],
        "resistivity",
        "mOhm*cm",
      ),
    ).toEqual([
      { column: 0, role: "temperature", unit: "K" },
      { column: 1, role: "resistivity", unit: "mOhm*cm" },
    ]);
  });
});

describe("looksLikeAnotherUnit", () => {
  const warnings = [
    { code: "few_rows" as const },
    { code: "implausible_magnitude" as const, column: 2 },
  ];

  test("finds the warning for a column, or for any", () => {
    expect(looksLikeAnotherUnit(warnings, 2)).toBe(true);
    expect(looksLikeAnotherUnit(warnings, 1)).toBe(false);
    expect(looksLikeAnotherUnit(warnings, undefined)).toBe(true);
    expect(looksLikeAnotherUnit([{ code: "few_rows" }], undefined)).toBe(false);
  });
});

describe("mappingOf with units", () => {
  test("sends a unit only for a quantity's column", () => {
    expect(
      mappingOf(["temperature", null, "seebeck"], ["uV/K", null, "uV/K"]),
    ).toEqual([
      { column: 0, role: "temperature" },
      { column: 2, role: "seebeck", unit: "uV/K" },
    ]);
  });

  test("leaves the unit out where none was chosen, so the server reads SI", () => {
    expect(mappingOf(["temperature", "hall"], [null, null])).toEqual([
      { column: 0, role: "temperature" },
      { column: 1, role: "hall" },
    ]);
  });
});
