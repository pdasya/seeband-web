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

/** A same-type pair has no finite-temperature solution at zero carrier density. */
export function isValidCarrierDensity(selection: Selection): boolean {
  if (!isExplicitDpb(selection)) return true;
  const { band_configuration, net_electron_density_per_m3: density } =
    explicitDpbInputs(selection);
  if (density === undefined || !Number.isFinite(density)) return false;
  if (band_configuration === "cb_cb") return density > 0;
  if (band_configuration === "vb_vb") return density < 0;
  return true;
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
