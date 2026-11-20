import type { Selection } from "@/session/store";

export function isExplicitDpb(selection: Selection): boolean {
  return (
    selection.model === "dpb" &&
    selection.parameterization === "explicit_density_v1"
  );
}

export function explicitDpbInputs(selection: Selection) {
  return isExplicitDpb(selection)
    ? {
        parameterization: "explicit_density_v1" as const,
        band_configuration: selection.bandConfiguration ?? "vb_cb",
        net_electron_density_per_m3: selection.netElectronDensityPerM3 ?? 1e24,
      }
    : {};
}

export function heldForFit(
  selection: Selection,
  held: readonly string[],
): string[] {
  return isExplicitDpb(selection) &&
    !(
      selection.fitMode === "dpb_s_rho_rh" && selection.fitAbsoluteMass === true
    )
    ? [...new Set([...held, "m1"])].sort()
    : [...held];
}
