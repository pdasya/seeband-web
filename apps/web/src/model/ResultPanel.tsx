import { formatNumber } from "@/lib/numbers";
import type { LiveCurves } from "@/model/useLiveCurves";
import { QUANTITIES } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { fit, data: dataText } = STRINGS;

function rmseText(rmse: { value: number | null; unit: string }): string {
  if (rmse.value === null) {
    return fit.rmseNotFinite;
  }
  const units: Record<string, string> = fit.rmseUnits;
  const value = formatNumber(Number(rmse.value.toPrecision(4)));
  return `${value} ${units[rmse.unit] ?? rmse.unit}`;
}

/** The RMSE of the current values. The rest of a fit's result comes in with the fit. */
export function ResultPanel({ live }: { live: LiveCurves }) {
  const { result } = live;
  const rows = QUANTITIES.flatMap((quantity) => {
    const rmse = result?.rmse?.[quantity];
    return rmse === undefined ? [] : [{ quantity, rmse }];
  });
  const issues = result?.known_issues ?? [];

  return (
    <Panel title={fit.result}>
      {rows.length === 0 ? (
        <p className="mt-3 mb-0 text-xs text-muted-foreground">{fit.noRmse}</p>
      ) : (
        <dl className="mt-3 mb-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
          {rows.map(({ quantity, rmse }) => (
            <div key={quantity} className="contents">
              <dt className="text-muted-foreground">
                {`${fit.rmse}, ${dataText.quantities[quantity].symbol}`}
              </dt>
              <dd className="m-0 text-right font-mono">{rmseText(rmse)}</dd>
            </div>
          ))}
        </dl>
      )}
      {issues.length > 0 && (
        <p className="mt-3 mb-0 text-xs text-muted-foreground">
          {`${fit.knownIssues} ${issues.join(", ")}.`}
        </p>
      )}
    </Panel>
  );
}
