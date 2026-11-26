import type { CalcResponse } from "@/api/client";
import { formatNumber } from "@/lib/numbers";
import { STRINGS } from "@/strings";

export function issueReason(code: string): string {
  const reasons: Record<string, string> = {
    ...STRINGS.calculation.reasons,
    ...STRINGS.chart.calculationDetails,
  };
  return reasons[code] ?? STRINGS.calculation.reasons.calculation_failed;
}

/** Temperatures to 0.1 K, with their unit. A semicolon separates them, as a comma is decimal. */
export function issueTemperatures(temperatures: readonly number[]): string {
  const unique = [...new Set(temperatures)].sort((a, b) => a - b);
  const shown = (value: number) => formatNumber(Math.round(value * 10) / 10);
  return unique.length <= 8
    ? STRINGS.calculation.affectedList(unique.map(shown))
    : STRINGS.calculation.affectedRange(
        shown(unique.at(0) ?? 0),
        shown(unique.at(-1) ?? 0),
        unique.length,
      );
}

/** Availability belongs to this response, separately for curves and measurement RMSE. */
export function rmseIssueText(
  result: CalcResponse | null | undefined,
  quantity: string,
): string | null {
  const issues = (result?.issues ?? []).filter(
    (issue) => issue.scope === "rmse" && issue.quantity === quantity,
  );
  return issues.length === 0
    ? null
    : issues
        .map(
          (issue) =>
            `${STRINGS.calculation.rmseUnavailable(
              STRINGS.data.quantities[
                quantity as keyof typeof STRINGS.data.quantities
              ]?.symbol ?? quantity,
              issueTemperatures(issue.temperature_k),
            )} ${issueReason(issue.code)}`,
        )
        .join(" ");
}
