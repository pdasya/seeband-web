import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UNITS_OF, type Unit } from "@/data/units";
import type { Quantity } from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/** The unit a quantity's column is written in. The server converts it to SI. */
export function UnitSelect({
  quantity,
  value,
  label,
  disabled = false,
  onChange,
}: {
  quantity: Quantity;
  value: Unit;
  /** The name of what the unit is for, for a screen reader. */
  label: string;
  disabled?: boolean;
  onChange: (unit: Unit) => void;
}) {
  return (
    <Select
      disabled={disabled}
      value={value}
      onValueChange={(chosen) => {
        onChange(chosen as Unit);
      }}
    >
      <SelectTrigger
        size="sm"
        className="w-full font-mono"
        aria-label={text.unitOf(label)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {UNITS_OF[quantity].map((unit) => (
          <SelectItem key={unit} value={unit} className="font-mono">
            {text.units[unit]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
