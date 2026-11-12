import { AlertCircleIcon } from "lucide-react";
import type { Ref } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { chosenQuantity, type Role } from "@/data/columnChoice";
import { UnitSelect } from "@/data/UnitSelect";
import { UNITS_OF, type Unit } from "@/data/units";
import type { ColumnChoice } from "@/data/useFileUpload";
import { formatNumber, withDecimalComma } from "@/lib/numbers";
import { QUANTITIES, type Quantity } from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;
const IGNORE = "ignore";
const ROLES: readonly Role[] = ["temperature", ...QUANTITIES];

function roleSymbol(role: Role): string {
  return role === "temperature" ? "T" : text.quantities[role].symbol;
}

function firstValue(value: number | undefined, role: Role | null): string {
  if (value === undefined) {
    return "";
  }
  return role === "temperature"
    ? formatNumber(value)
    : withDecimalComma(value.toExponential(3));
}

/** What each column of a file with no header holds, as for a single file, then the slot to use. */
export function SlotColumns({
  quantity,
  choice,
  firstSelect,
  onRole,
  onUnit,
  onApply,
}: {
  quantity: Quantity;
  choice: ColumnChoice;
  /** Where focus goes once the choice shows. */
  firstSelect: Ref<HTMLButtonElement>;
  onRole: (column: number, role: Role | null) => void;
  onUnit: (column: number, unit: Unit) => void;
  onApply: () => void;
}) {
  const target = chosenQuantity(choice.roles);
  const named = choice.named === null ? null : text.quantities[choice.named];
  // The column a user decides on first: the second, or the first with nothing chosen.
  const focusColumn = choice.roles.findIndex(
    (role, column) => column > 0 && (role === null || column === 1),
  );
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-xs">
        {choice.mismatch ? text.headerMismatchQuestion : text.noHeaderQuestion}
      </p>
      {choice.negative && (
        <p className="m-0 text-xs text-muted-foreground">
          {text.belowZeroForRho}
        </p>
      )}
      {named !== null && (
        <p className="m-0 text-xs text-muted-foreground">
          {text.nameSuggests(named.title)}
        </p>
      )}
      {Array.from({ length: choice.columns }, (_, column) => {
        const role = choice.roles[column] ?? null;
        const name = `${text.single.column} ${String(column + 1)}`;
        const quantity = role === null || role === "temperature" ? null : role;
        return (
          // The card is narrow, so the column's name and value take a line of their own, and the
          // choices of quantity and unit the next.
          <div key={column} className="flex flex-col gap-1">
            <div className="flex min-w-0 items-baseline gap-2">
              <span className="flex-none font-mono text-[13px] font-medium">
                {name}
              </span>
              <span className="truncate font-mono text-xs text-muted-foreground">
                {firstValue(choice.firstRow[column], role)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Select
                disabled={choice.applying}
                value={role ?? IGNORE}
                onValueChange={(value) => {
                  onRole(column, value === IGNORE ? null : (value as Role));
                }}
              >
                <SelectTrigger
                  ref={column === focusColumn ? firstSelect : undefined}
                  size="sm"
                  className="w-full"
                  aria-label={`${text.single.columnRole} ${name}`}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((option) => (
                    <SelectItem key={option} value={option}>
                      {roleSymbol(option)}
                    </SelectItem>
                  ))}
                  <SelectItem value={IGNORE}>{text.single.ignore}</SelectItem>
                </SelectContent>
              </Select>
              {quantity === null ? (
                <span />
              ) : (
                <UnitSelect
                  quantity={quantity}
                  value={choice.units[column] ?? UNITS_OF[quantity][0]}
                  label={name}
                  disabled={choice.applying}
                  onChange={(unit) => {
                    onUnit(column, unit);
                  }}
                />
              )}
            </div>
          </div>
        );
      })}
      {choice.problems.length > 0 && (
        <Alert variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>
            <ul className="m-0 list-none p-0">
              {choice.problems.map((problem, index) => (
                <li key={index}>{problem}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {target === null ? (
        <p className="m-0 text-xs text-muted-foreground">
          {text.chooseColumns}
        </p>
      ) : (
        target !== quantity && (
          <p className="m-0 text-xs text-muted-foreground">
            {text.goesToSlot(text.quantities[target].title)}
          </p>
        )
      )}
      <Button
        size="sm"
        className="self-start"
        disabled={target === null || choice.applying}
        onClick={onApply}
      >
        {target === null
          ? text.loadAs("…")
          : text.loadAs(text.quantities[target].symbol)}
      </Button>
    </div>
  );
}
