import type { ReactNode } from "react";

/**
 * A one-letter symbol and its index written as `E_g`, `R_H` or `κ_e`, as the strings hold them.
 * Not a name such as `fermi_energy`, whose letter before `_` follows another.
 */
const SUBSCRIPT =
  /(?<![\p{L}\p{N}_])(\p{L})_(\p{L}+|\p{N}+)(?![\p{L}\p{N}_])/gu;

/** The text with each `E_g` drawn as E with a lowered g, in one span so that a flex row keeps it whole. */
export function Subscripted({ text }: { text: string | null }): ReactNode {
  if (text === null) {
    return null;
  }
  const parts: ReactNode[] = [];
  let from = 0;
  for (const match of text.matchAll(SUBSCRIPT)) {
    const [whole, symbol, index] = match;
    parts.push(text.slice(from, match.index), symbol);
    parts.push(<sub key={match.index}>{index}</sub>);
    from = match.index + whole.length;
  }
  if (parts.length === 0) {
    return text;
  }
  parts.push(text.slice(from));
  return <span>{parts}</span>;
}

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
};

/** The same for Plotly, which reads its text as a little HTML: `E<sub>g</sub>`, the rest escaped. */
export function plotlySubscripts(text: string): string {
  return text
    .replace(/[&<>]/g, (character) => ESCAPES[character] ?? character)
    .replace(SUBSCRIPT, "$1<sub>$2</sub>");
}

/**
 * The same text as a screen reader gets it from the drawn one, `Eg` for `E_g`, for a name given
 * as an attribute, so that it holds the visible text.
 */
export function plainSubscripts(text: string): string {
  return text.replace(SUBSCRIPT, "$1$2");
}
