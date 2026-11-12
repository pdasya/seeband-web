// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, test } from "vitest";

import { mappingOf } from "@/data/columnChoice";
import {
  UNITS_OF,
  columnOf,
  unitDoubts,
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
  test("offers every unit of the contract, each once, with SI first", () => {
    const offered = Object.values(UNITS_OF).flat();
    expect(new Set(offered).size).toBe(offered.length);
    expect([...offered].sort()).toEqual(contractUnits().sort());
    expect(UNITS_OF.temperature).toEqual(["K", "C"]);
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
    expect(unitOf(undefined, "temperature")).toBe("K");
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

describe("unitDoubts", () => {
  const warnings = [
    { code: "few_rows" as const },
    { code: "implausible_magnitude" as const, column: 2 },
    { code: "unit_assumed" as const, column: 1 },
    { code: "unit_differs" as const, column: 1 },
  ];

  test("finds the doubts about one column only", () => {
    expect(unitDoubts(warnings, 2)).toEqual(["implausible_magnitude"]);
    expect(unitDoubts(warnings, 1)).toEqual(["unit_assumed"]);
    expect(unitDoubts(warnings, 0)).toEqual([]);
  });

  test("finds none for a column not read, as another column holds them", () => {
    expect(unitDoubts(warnings, undefined)).toEqual([]);
  });
});

describe("columnOf", () => {
  test("gives the column of a role, or nothing", () => {
    const mapping = [
      { column: 0, role: "temperature" as const },
      { column: 2, role: "seebeck" as const },
    ];
    expect(columnOf(mapping, "seebeck")).toBe(2);
    expect(columnOf(mapping, "hall")).toBeUndefined();
    expect(columnOf(undefined, "seebeck")).toBeUndefined();
  });
});

describe("mappingOf with units", () => {
  test("sends the unit chosen for each column, T as well", () => {
    expect(
      mappingOf(["temperature", null, "seebeck"], ["C", null, "uV/K"]),
    ).toEqual([
      { column: 0, role: "temperature", unit: "C" },
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
