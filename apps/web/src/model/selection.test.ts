// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, test } from "vitest";

import {
  firstModel,
  settingsFor,
  type ModelDescription,
} from "@/model/selection";

// The real descriptions, as the contract's example holds them.
const contract = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../../packages/api-client/openapi.json", import.meta.url),
    ),
    "utf8",
  ),
) as {
  paths: Record<
    string,
    Record<
      string,
      {
        responses: Record<
          string,
          {
            content: Record<
              string,
              {
                examples: Record<
                  string,
                  { value: { models: ModelDescription[] } }
                >;
              }
            >;
          }
        >;
      }
    >
  >;
};
const examples =
  contract.paths["/api/models"]?.get?.responses["200"]?.content[
    "application/json"
  ]?.examples ?? {};
const models = Object.values(examples)[0]?.value.models ?? [];
const spb = models.find(({ id }) => id === "spb") as ModelDescription;
const dpb = models.find(({ id }) => id === "dpb") as ModelDescription;

describe("firstModel", () => {
  test("is the design's, or the first there is", () => {
    expect(firstModel(models)?.id).toBe("dpb");
    expect(firstModel([spb])?.id).toBe("spb");
    expect(firstModel([])).toBeUndefined();
  });
});

describe("settingsFor", () => {
  test("starts DPB as the design does", () => {
    expect(settingsFor(dpb)).toEqual({
      fitMode: "dpb_s_rho",
      scattering: "acPh",
      band1Degeneracy: 1,
      band2Degeneracy: 1,
    });
  });

  test("never chooses a disabled mode, even when asked", () => {
    const withDisabledHall = {
      ...spb,
      fit_modes: spb.fit_modes.map((mode) =>
        mode.id === "spb_s_rho_rh" ? { ...mode, disabled: true } : mode,
      ),
    };
    expect(
      settingsFor(withDisabledHall, { fitMode: "spb_s_rho_rh" }).fitMode,
    ).toBe("spb_s");
  });

  test("keeps the repaired SPB Hall mode when selected", () => {
    expect(settingsFor(spb, { fitMode: "spb_s_rho_rh" }).fitMode).toBe(
      "spb_s_rho_rh",
    );
  });

  test("a mode of another model gives way", () => {
    expect(settingsFor(spb, { fitMode: "dpb_s_rho" }).fitMode).toBe("spb_s");
  });

  test("keeps a scattering type the mode has, and otherwise takes its default", () => {
    expect(
      settingsFor(dpb, { fitMode: "dpb_s_rho_rh", scattering: "dis" })
        .scattering,
    ).toBe("dis");
    expect(
      settingsFor(dpb, { fitMode: "dpb_s_rho", scattering: "nope" }).scattering,
    ).toBe("acPh");
  });

  test("a mode with no scattering has none", () => {
    expect(
      settingsFor(dpb, { fitMode: "dpb_s", scattering: "dis" }).scattering,
    ).toBeNull();
  });

  test("keeps degeneracies where they apply, and SPB has none", () => {
    expect(
      settingsFor(dpb, { fitMode: "dpb_s", band2Degeneracy: 3 })
        .band2Degeneracy,
    ).toBe(3);
    expect(
      settingsFor(spb, { fitMode: "spb_s", band2Degeneracy: 3 })
        .band2Degeneracy,
    ).toBe(1);
  });

  test("a model with every mode disabled has none", () => {
    const off = {
      ...spb,
      fit_modes: spb.fit_modes.map((mode) => ({ ...mode, disabled: true })),
    };

    expect(settingsFor(off).fitMode).toBeNull();
  });
});
