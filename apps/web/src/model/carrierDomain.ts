import { useQueries } from "@tanstack/react-query";
import type { operations } from "@seeband/api-client";

import { apiClient } from "@/api/client";
import type { ExplorationDomain } from "@/model/parameters";
import type { Selection } from "@/session/store";

type DomainQuery =
  operations["get_dpb_parameter_domain"]["parameters"]["query"];
/** Each query depends only on the other coordinates, so dragging a control keeps its own range stable. */
export function useCarrierDomains(
  values: Record<string, number>,
  selection: Selection,
  hasManualFermi: boolean,
) {
  const queries: DomainQuery[] = [];
  const configuration = selection.bandConfiguration;
  if (
    selection.model === "dpb" &&
    selection.parameterization === "explicit_fermi_v1" &&
    configuration &&
    selection.carrierType &&
    values.fermi_energy !== undefined &&
    values.mass_ratio !== undefined &&
    values.band_offset_k !== undefined
  ) {
    const names: DomainQuery["name"][] = ["fermi_energy"];
    if (hasManualFermi) {
      names.push("band_offset_k");
      if (configuration === "vb_cb") names.push("mass_ratio");
    }
    for (const name of names) {
      queries.push({
        name,
        band_configuration: configuration,
        carrier_type: selection.carrierType,
        fermi_energy: name === "fermi_energy" ? 0 : values.fermi_energy,
        band_offset_k: name === "band_offset_k" ? 0 : values.band_offset_k,
        mass_ratio: name === "mass_ratio" ? 1 : values.mass_ratio,
        band_1_degeneracy: selection.band1Degeneracy,
        band_2_degeneracy: selection.band2Degeneracy,
      });
    }
  }
  const results = useQueries({
    queries: queries.map((query) => ({
      queryKey: ["dpb-parameter-domain", query],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        apiClient.getDpbDomain(query, signal),
      staleTime: Infinity,
    })),
  });
  const domains: Partial<Record<string, ExplorationDomain | null>> = {};
  queries.forEach(({ name }, i) => {
    const domain = results[i]?.data;
    if (!domain) domains[name] = null;
    else if (domain.empty)
      domains[name] = { lower: Infinity, upper: -Infinity, inclusive: true };
    else if (domain.lower != null || domain.upper != null) {
      domains[name] = {
        ...(domain.lower == null ? {} : { lower: domain.lower }),
        ...(domain.upper == null ? {} : { upper: domain.upper }),
        inclusive: domain.inclusive ?? true,
      };
    }
  });
  return {
    domains,
    failed: results.some((result) => result.isError),
    retry: () => {
      for (const result of results) if (result.isError) void result.refetch();
    },
  };
}
