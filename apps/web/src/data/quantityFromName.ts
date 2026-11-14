import type { LoadedQuantity } from "@/session/store";

// Words in file names, as the desktop's examples use `_see`, `_rho` and `_hall`. A lone `s` is left
// out, as it often means something else, such as a sample.
const NAMED: Readonly<Record<string, LoadedQuantity>> = {
  see: "seebeck",
  seebeck: "seebeck",
  thermopower: "seebeck",
  rho: "resistivity",
  res: "resistivity",
  resist: "resistivity",
  resistivity: "resistivity",
  sigma: "conductivity",
  conductivity: "conductivity",
  hall: "hall",
  rh: "hall",
};

/** The one quantity a file's name names, or null if it names none or several. */
export function quantityFromName(name: string): LoadedQuantity | null {
  const stem = name.replace(/\.[^.]*$/, "").toLowerCase();
  const named = new Set(
    stem.split(/[^a-z]+/).flatMap((word) => {
      const quantity = NAMED[word];
      return quantity === undefined ? [] : [quantity];
    }),
  );
  return named.size === 1 ? ([...named][0] ?? null) : null;
}
