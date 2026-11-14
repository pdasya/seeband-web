// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, test } from "vitest";

import { mappingOf } from "@/data/columnChoice";
import {
  UNITS_OF,
  columnOf,
  requestMapping,
  unitDoubtMessage,
  unitDoubts,
  unitIsDefault,
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
    expect(UNITS_OF.seebeck).toEqual(["V/K", "uV/K", "mV/K"]);
    expect(UNITS_OF.resistivity).toEqual([
      "Ohm*m",
      "Ohm*cm",
      "mOhm*cm",
      "uOhm*m",
      "uOhm*cm",
    ]);
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
    expect(unitDoubts(warnings, 2)).toEqual([
      { code: "implausible_magnitude", direction: undefined },
    ]);
    expect(unitDoubts(warnings, 1)).toEqual([
      { code: "unit_assumed", direction: undefined },
    ]);
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

describe("requestMapping", () => {
  test("sends again only the units a user chose", () => {
    expect(
      requestMapping([
        { column: 0, role: "temperature", unit: "K", unit_source: "default" },
        { column: 1, role: "seebeck", unit: "uV/K", unit_source: "header" },
        { column: 2, role: "hall", unit: "cm^3/C", unit_source: "chosen" },
      ]),
    ).toEqual([
      { column: 0, role: "temperature" },
      { column: 1, role: "seebeck" },
      { column: 2, role: "hall", unit: "cm^3/C" },
    ]);
  });

  test("keeps a unit whose source the answer does not give", () => {
    expect(
      requestMapping([
        { column: 1, role: "seebeck", unit: "uV/K" },
        { column: 0, role: "temperature" },
      ]),
    ).toEqual([
      { column: 1, role: "seebeck", unit: "uV/K" },
      { column: 0, role: "temperature" },
    ]);
  });
});

describe("unitIsDefault", () => {
  test("holds only for a unit nothing named", () => {
    expect(unitIsDefault({ unit_source: "default" })).toBe(true);
    expect(unitIsDefault({ unit_source: "header" })).toBe(false);
    expect(unitIsDefault({ unit_source: "chosen" })).toBe(false);
    expect(unitIsDefault({})).toBe(false);
    expect(unitIsDefault(undefined)).toBe(false);
  });
});

describe("unitDoubtMessage", () => {
  const { data: text } = STRINGS;
  const assumed = (unit: Unit) => ({ unit, unit_source: "default" as const });
  const above = {
    code: "implausible_magnitude" as const,
    direction: "above" as const,
  };
  const below = {
    code: "implausible_magnitude" as const,
    direction: "below" as const,
  };

  test("names the lab units that read as SI give values this far above", () => {
    expect(unitDoubtMessage(above, "seebeck", assumed("V/K"))).toBe(
      "These values are far larger than any usual Seebeck coefficient in V/K, the unit assumed. If the file is in µV/K or mV/K, choose it.",
    );
    expect(unitDoubtMessage(above, "resistivity", assumed("Ohm*m"))).toContain(
      "Ω·cm, mΩ·cm, µΩ·m or µΩ·cm",
    );
    expect(unitDoubtMessage(above, "hall", assumed("m^3/C"))).toContain(
      "choose cm³/C",
    );
  });

  test("suggests S/cm only for a conductivity far below, as S/cm read as S/m gives", () => {
    expect(unitDoubtMessage(below, "conductivity", assumed("S/m"))).toContain(
      "far smaller than any usual conductivity in S/m",
    );
    expect(unitDoubtMessage(below, "conductivity", assumed("S/m"))).toContain(
      "choose S/cm",
    );
    expect(
      unitDoubtMessage(above, "conductivity", assumed("S/m")),
    ).not.toContain("S/cm");
  });

  test("suggests no unit that would make values far below smaller still", () => {
    const message = unitDoubtMessage(below, "seebeck", assumed("V/K"));
    expect(message).toContain("far smaller");
    expect(message).not.toMatch(/µV\/K|mV\/K/);
    expect(message).toContain(text.implausible.checkColumn);
  });

  test("asks to check a unit that was chosen, rather than suggest another", () => {
    expect(
      unitDoubtMessage(above, "seebeck", {
        unit: "uV/K",
        unit_source: "chosen",
      }),
    ).toBe(text.implausible.inChosenUnit("larger", "µV/K"));
    // Choosing SI is a choice too, so it is not told to choose a lab unit.
    expect(
      unitDoubtMessage(above, "seebeck", {
        unit: "V/K",
        unit_source: "chosen",
      }),
    ).toBe(text.implausible.inChosenUnit("larger", "V/K"));
  });

  test("asks to check the file where its header names the unit", () => {
    expect(
      unitDoubtMessage(below, "seebeck", {
        unit: "V/K",
        unit_source: "header",
      }),
    ).toBe(text.implausible.inHeaderUnit("smaller", "V/K"));
  });

  test("claims no side where the answer gives none", () => {
    expect(
      unitDoubtMessage(
        { code: "implausible_magnitude" },
        "seebeck",
        assumed("V/K"),
      ),
    ).toBe(text.issues.implausible_magnitude);
  });

  test("keeps the text of an unreadable header unit", () => {
    expect(
      unitDoubtMessage({ code: "unit_assumed" }, "seebeck", assumed("V/K")),
    ).toBe(text.issues.unit_assumed);
  });
});
