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

export function issueTemperatures(temperatures: readonly number[]): string {
  const unique = [...new Set(temperatures)].sort((a, b) => a - b);
  return unique.length <= 8
    ? unique.map((value) => formatNumber(value)).join(", ")
    : STRINGS.calculation.affectedRange(
        formatNumber(unique.at(0) ?? 0),
        formatNumber(unique.at(-1) ?? 0),
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
