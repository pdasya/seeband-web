// @vitest-environment node
import { expect, test } from "vitest";
import { explicitDpbInputs, heldForFit } from "./explicitDpb";
import type { Selection } from "@/session/store";
const selection: Selection = {
  model: "dpb",
  fitMode: "dpb_s_rho",
  scattering: "acPh",
  band1Degeneracy: 2,
  band2Degeneracy: 6,
  minTemperatureK: 100,
  maxTemperatureK: 800,
  parameterization: "explicit_density_v1",
  bandConfiguration: "cb_cb",
  netElectronDensityPerM3: 2e24,
};
test("explicit request identity includes configuration and signed SI density", () => {
  expect(explicitDpbInputs(selection)).toEqual({
    parameterization: "explicit_density_v1",
    band_configuration: "cb_cb",
    net_electron_density_per_m3: 2e24,
  });
  expect(explicitDpbInputs({ ...selection, model: "spb" })).toEqual({});
});
test("absolute mass is held by default and only Hall mode may release it", () => {
  expect(heldForFit(selection, [])).toEqual(["m1"]);
  expect(heldForFit({ ...selection, fitMode: "dpb_s_rho_rh" }, [])).toEqual([
    "m1",
  ]);
  expect(
    heldForFit(
      { ...selection, fitMode: "dpb_s_rho_rh", fitAbsoluteMass: true },
      ["mass_ratio"],
    ),
  ).toEqual(["mass_ratio"]);
});

test("Fermi representation omits legacy carrier constraints", () => {
  expect(
    explicitDpbInputs({
      ...selection,
      parameterization: "explicit_fermi_v1",
    }),
  ).toEqual({
    parameterization: "explicit_fermi_v1",
    band_configuration: "cb_cb",
  });
});

test("stored legacy Fermi carrier constraints remain explicit", () => {
  expect(
    explicitDpbInputs({
      ...selection,
      parameterization: "explicit_fermi_v1",
      carrierType: "p",
    }),
  ).toHaveProperty("carrier_type", "p");
});
