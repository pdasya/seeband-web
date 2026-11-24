/**
 * A one-letter symbol and its index written as `E_g`, `R_H` or `κ_e`, as the strings hold them.
 * The app's `src/lib/subscripts.tsx` reads them the same way.
 */
// With what comes before it, and no lookbehind, which Safari before 16.4 cannot read.
const SUBSCRIPT =
  /(^|[^\p{L}\p{N}_])(\p{L})_(\p{L}+|\p{N}+)(?![\p{L}\p{N}_])/gu;

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
};

/** The text as HTML for `set:html`, with each `E_g` as `E<sub>g</sub>` and the rest escaped. */
export function subscripts(text: string): string {
  return text
    .replace(/[&<>"]/g, (character) => ESCAPES[character] ?? character)
    .replace(SUBSCRIPT, "$1$2<sub>$3</sub>");
}

/** The text a screen reader takes from the drawn one, `Eg`, for an attribute such as `alt`. */
export function plainSubscripts(text: string): string {
  return text.replace(SUBSCRIPT, "$1$2$3");
}
