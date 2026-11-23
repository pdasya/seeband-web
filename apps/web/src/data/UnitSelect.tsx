import type { Ref } from "react";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Role } from "@/data/columnChoice";
import { UNITS_OF, type Unit } from "@/data/units";
import { cn } from "@/lib/utils";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/**
 * The unit a column is written in. The server converts it to SI.
 *
 * A unit `assumed` as nothing named one shows as such, with no unit selected, so that choosing
 * even the same unit is a choice the user made, and the mark goes.
 */
export function UnitSelect({
  role,
  value,
  label,
  assumed = false,
  disabled = false,
  onChange,
  ref,
}: {
  role: Role;
  value: Unit;
  /** The name of what the unit is for, for a screen reader. */
  label: string;
  assumed?: boolean;
  disabled?: boolean;
  onChange: (unit: Unit) => void;
  ref?: Ref<HTMLButtonElement>;
}) {
  return (
    <Select
      disabled={disabled}
      // An empty value shows the placeholder, and leaves every unit to choose.
      value={assumed ? "" : value}
      onValueChange={(chosen) => {
        onChange(chosen as Unit);
      }}
    >
      <SelectTrigger
        ref={ref}
        size="sm"
        // Dashed and muted, as the unit is the placeholder: the card's note says why.
        className={cn("w-full font-mono", assumed && "border-dashed")}
        // The name replaces the shown unit for a screen reader, so it names the unit too.
        aria-label={
          assumed
            ? text.unitAssumedOf(label, text.units[value])
            : text.unitOf(label)
        }
      >
        <SelectValue placeholder={text.units[value]} />
      </SelectTrigger>
      <SelectContent>
        {role === "resistivity"
          ? // Grouped by length unit, so a prefix is not mistaken across m and cm.
            (["metre", "centimetre"] as const).map((group) => (
              <SelectGroup key={group}>
                <SelectLabel>{text.unitGroups[group]}</SelectLabel>
                {UNITS_OF[role]
                  .filter(
                    (unit) => unit.endsWith("cm") === (group === "centimetre"),
                  )
                  .map((unit) => (
                    <SelectItem key={unit} value={unit} className="font-mono">
                      {text.units[unit]}
                    </SelectItem>
                  ))}
              </SelectGroup>
            ))
          : UNITS_OF[role].map((unit) => (
              <SelectItem key={unit} value={unit} className="font-mono">
                {text.units[unit]}
              </SelectItem>
            ))}
      </SelectContent>
    </Select>
  );
}
