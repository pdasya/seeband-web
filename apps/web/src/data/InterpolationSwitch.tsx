import { AlertCircleIcon } from "lucide-react";
import { useId } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import { useFitRange, useInterpolation } from "@/data/useInterpolation";
import { QUANTITIES, useSessionStore, type Quantity } from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/** What a user must know about each quantity's interpolated values. */
function flagsOf(
  quantity: Quantity,
  interpolated: ReturnType<
    typeof useSessionStore.getState
  >["interpolation"]["values"],
  failed: readonly Quantity[],
): string[] {
  const { symbol } = text.quantities[quantity];
  const flags = text.interpolation.flags;
  if (failed.includes(quantity)) {
    return [`${symbol}: ${flags.failed}`];
  }
  const result = interpolated[quantity];
  if (result === undefined) {
    return [];
  }
  const messages: string[] = [];
  if (result.values.some((value) => value === null)) {
    messages.push(flags.notFinite);
  }
  if (result.measured_points_in_range === 0) {
    messages.push(flags.noMeasuredPoints);
  } else if (result.extrapolated) {
    messages.push(flags.extrapolated);
  }
  if (result.underdetermined) {
    messages.push(flags.underdetermined);
  }
  return messages.map((message) => `${symbol}: ${message}`);
}

/** The one switch of the design, for all the data. The desktop has one for each quantity. */
export function InterpolationSwitch() {
  const id = useId();
  const interpolation = useSessionStore((state) => state.interpolation);
  const setEnabled = useSessionStore((state) => state.setInterpolationEnabled);
  const range = useFitRange();
  useInterpolation(range);

  const flags = interpolation.enabled
    ? QUANTITIES.flatMap((quantity) =>
        flagsOf(quantity, interpolation.values, interpolation.failed),
      )
    : [];
  return (
    <div className="flex flex-col gap-1.5 pt-1.5">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="text-[13px]">
          <span className="block font-medium">{text.interpolation.title}</span>
          <span className="block text-xs text-muted-foreground">
            {text.interpolation.hint}
          </span>
        </label>
        <Switch
          id={id}
          checked={interpolation.enabled}
          onCheckedChange={setEnabled}
        />
      </div>
      <div role="status" className="text-xs text-muted-foreground">
        {interpolation.enabled && interpolation.loading
          ? text.interpolation.working
          : ""}
        {interpolation.enabled && !interpolation.loading && range !== null
          ? `${text.interpolation.range} ${String(range.minK)}–${String(range.maxK)} K`
          : ""}
        {interpolation.enabled && range === null
          ? text.interpolation.noRange
          : ""}
      </div>
      {interpolation.failure !== null && interpolation.enabled && (
        <Alert variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>{interpolation.failure}</AlertDescription>
        </Alert>
      )}
      {flags.length > 0 && !interpolation.loading && (
        <Alert variant="warning">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>
            <ul className="m-0 list-none p-0">
              {flags.map((flag, index) => (
                <li key={index}>{flag}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
