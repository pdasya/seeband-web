import { TriangleAlertIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  sessionMismatches,
  type TemperatureRange,
} from "@/data/temperatureRanges";
import { formatNumber } from "@/lib/numbers";
import { loadedAs, QUANTITIES, useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";
import { Subscripted } from "@/lib/subscripts";

const { data: text } = STRINGS;

function rangeText({
  min_temperature_k: low,
  max_temperature_k: high,
}: TemperatureRange) {
  return `${formatNumber(low)}–${formatNumber(high)} K`;
}

/** Separate files whose T ranges look like K beside °C read as K. */
export function TemperatureRangeWarning({ className }: { className?: string }) {
  const data = useSessionStore((state) => state.data);
  const mismatches = sessionMismatches(data);
  if (mismatches.length === 0) {
    return null;
  }
  const named = (quantity: (typeof QUANTITIES)[number]) => {
    const entry = data[quantity];
    const symbol = text.quantities[loadedAs(quantity, entry)].symbol;
    return entry === undefined
      ? symbol
      : `${symbol} (${rangeText(entry.measurement)})`;
  };
  return (
    <Alert className={className}>
      <TriangleAlertIcon aria-hidden="true" />
      <AlertTitle>{text.temperatureRanges.title}</AlertTitle>
      <AlertDescription>
        <ul className="m-0 list-none p-0">
          {mismatches.map(({ lower, higher }) => (
            <li key={`${lower}-${higher}`}>
              <Subscripted
                text={text.temperatureRanges.shifted(
                  named(lower),
                  named(higher),
                  text.quantities[loadedAs(lower, data[lower])].symbol,
                )}
              />
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
