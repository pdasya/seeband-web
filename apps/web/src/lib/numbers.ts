/**
 * How numbers look and are typed across the app: with a decimal comma, whatever the browser's
 * region. Files and the API keep their points, as this is only for what a person reads and types.
 */
export function withDecimalComma(number: string): string {
  return number.replace(".", ",");
}

export function formatNumber(value: number): string {
  return withDecimalComma(String(value));
}

const NUMBER = /^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$/;

/** The number a person typed, with a comma or a point, or null if the text is not a finite one. */
export function parseNumber(text: string): number | null {
  const trimmed = text.trim().replace("−", "-");
  if (!NUMBER.test(trimmed)) {
    return null;
  }
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) ? value : null;
}
