import { useQuery } from "@tanstack/react-query";

import { modelsQuery } from "@/api/queries";
import { formatNumber } from "@/lib/numbers";
import { rmseGaps } from "@/model/liveCurves";
import type { LiveCurves } from "@/model/useLiveCurves";
import { QUANTITIES, useSessionStore, type Quantity } from "@/session/store";
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

function symbols(quantities: readonly Quantity[]): string {
  return quantities
    .map((quantity) => dataText.quantities[quantity].symbol)
    .join(", ");
}

function Note({ children }: { children: string }) {
  return <p className="mt-3 mb-0 text-xs text-muted-foreground">{children}</p>;
}

/** The RMSE of the current values. The rest of a fit's result comes in with the fit. */
export function ResultPanel({ live }: { live: LiveCurves }) {
  const { result, error } = live.measured;
  const { data: models } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const parameters = useSessionStore((state) => state.parameters);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const gaps = rmseGaps(
    { selection, parameters, data, interpolation },
    models?.models,
  );

  const rows = QUANTITIES.flatMap((quantity) => {
    const rmse = result?.rmse?.[quantity];
    return rmse === undefined ? [] : [{ quantity, rmse }];
  });
  // Curves of the open tab can have known errors of their own.
  const issues = [
    ...new Set([
      ...(result?.known_issues ?? []),
      ...(live.derived.result?.known_issues ?? []),
    ]),
  ];
  const explained =
    gaps.noPointsInRange.length > 0 || gaps.notInterpolated.length > 0;

  return (
    <Panel title={fit.result}>
      {rows.length === 0 && !explained && <Note>{fit.noRmse}</Note>}
      {rows.length > 0 && (
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
      {error !== null && result !== null && <Note>{fit.rmseOutdated}</Note>}
      {gaps.noPointsInRange.length > 0 && (
        <Note>{`${symbols(gaps.noPointsInRange)}: ${fit.noPointsInRange}`}</Note>
      )}
      {gaps.notInterpolated.length > 0 && (
        <Note>{`${symbols(gaps.notInterpolated)}: ${fit.notInterpolated}`}</Note>
      )}
      {gaps.zerosLeftOut.length > 0 && (
        <Note>{`${symbols(gaps.zerosLeftOut)}: ${fit.zerosLeftOut}`}</Note>
      )}
      {issues.length > 0 && (
        <Note>{`${fit.knownIssues} ${issues.join(", ")}.`}</Note>
      )}
    </Panel>
  );
}
