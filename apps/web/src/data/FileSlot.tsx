import {
  AlertCircleIcon,
  LoaderCircleIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useRef } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DropArea, useFileDrop } from "@/data/DropArea";
import { SlotColumns } from "@/data/SlotColumns";
import { UnitSelect } from "@/data/UnitSelect";
import { unitOf } from "@/data/units";
import { useFileUpload } from "@/data/useFileUpload";
import { cn } from "@/lib/utils";
import {
  useSessionStore,
  type Quantity,
  type SessionData,
} from "@/session/store";
import { withDecimalComma } from "@/lib/numbers";
import { STRINGS } from "@/strings";

const TEMPERATURE_FORMAT = new Intl.NumberFormat("en", {
  maximumFractionDigits: 1,
  useGrouping: false,
});

function Symbol({ children, filled }: { children: string; filled: boolean }) {
  return (
    <div
      className={cn(
        "flex size-8 flex-none items-center justify-center rounded-md font-mono text-[13px] font-medium",
        filled ? "bg-muted" : "border bg-background",
      )}
    >
      {children}
    </div>
  );
}

function fileSummary(quantity: Quantity, { measurement }: SessionData): string {
  const { data } = STRINGS;
  const low = withDecimalComma(
    TEMPERATURE_FORMAT.format(measurement.min_temperature_k),
  );
  const high = withDecimalComma(
    TEMPERATURE_FORMAT.format(measurement.max_temperature_k),
  );
  return `${String(measurement.points)} ${data.points} · ${low}–${high} K · ${data.quantities[quantity].unit}`;
}

function FileName({ children }: { children: string }) {
  // It is cut short in the card, so the full name is in its tooltip.
  return (
    <div
      className="truncate font-mono text-[13px] font-medium"
      title={children}
    >
      {children}
    </div>
  );
}

function dataName({ source }: SessionData): string {
  return source.kind === "file" ? source.name : STRINGS.data.demoSource;
}

/** One quantity's file: a place to drop or choose it, then its card. */
export function FileSlot({ quantity }: { quantity: Quantity }) {
  const { data: text } = STRINGS;
  const names = text.quantities[quantity];
  const data = useSessionStore((state) => state.data[quantity]);
  const {
    state,
    upload,
    chooseRole,
    chooseColumnUnit,
    applyChoice,
    changeUnit,
    remove,
    fail,
  } = useFileUpload(quantity);
  const input = useRef<HTMLInputElement>(null);
  const removeButton = useRef<HTMLButtonElement>(null);
  const firstSelect = useRef<HTMLButtonElement>(null);
  // The element with focus goes away when a slot changes, so it comes back to the slot's control.
  const keepFocus = useRef(false);

  useEffect(() => {
    // A file on its way, or a choice the server is reading, has not settled yet.
    const settling =
      state.status === "loading" ||
      (state.status === "choose" && state.applying);
    if (keepFocus.current && !settling) {
      keepFocus.current = false;
      (input.current ?? firstSelect.current ?? removeButton.current)?.focus();
    }
  });

  const handlers = {
    onFile: (file: File) => {
      keepFocus.current = true;
      void upload(file);
    },
    onSeveralFiles: () => {
      fail(text.oneFile);
    },
  };
  const onRemove = () => {
    keepFocus.current = true;
    remove();
  };
  const { dragging, dropTarget: drop } = useFileDrop(handlers);
  const dropTarget = { "data-file-slot": quantity, ...drop };
  const dropping = dragging && "border-ring bg-muted";

  // Always there, as a screen reader may not read out a live region that arrives filled.
  let announcement = "";
  if (state.status === "loading") {
    announcement = `${state.name}: ${text.reading}`;
  } else if (state.status === "choose") {
    announcement = `${state.name}: ${text.noHeaderQuestion}`;
  } else if (data !== undefined) {
    announcement = `${names.title}: ${dataName(data)}, ${fileSummary(quantity, data)}`;
  }
  const status = (
    <div role="status" className="sr-only">
      {announcement}
    </div>
  );

  if (state.status === "loading") {
    return (
      <>
        {status}
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border px-3 py-2.5",
            dropping,
          )}
          {...dropTarget}
        >
          <Symbol filled>{names.symbol}</Symbol>
          <div className="min-w-0 flex-auto">
            <FileName>{state.name}</FileName>
            <div className="text-xs text-muted-foreground">{text.reading}</div>
          </div>
          <LoaderCircleIcon
            className="size-4 flex-none animate-spin text-muted-foreground"
            aria-hidden="true"
          />
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`${text.cancel} ${names.symbol}`}
            onClick={onRemove}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </div>
      </>
    );
  }

  if (state.status === "choose") {
    return (
      <div className="flex flex-col gap-1.5">
        {status}
        <div
          className="flex flex-col gap-2.5 rounded-lg border px-3 py-2.5"
          data-file-slot={quantity}
        >
          <div className="flex items-center gap-3">
            <Symbol filled={false}>{names.symbol}</Symbol>
            <div className="min-w-0 flex-auto">
              <FileName>{state.name}</FileName>
              <div className="text-xs text-muted-foreground">
                {text.tableSize(state.rows, state.columns)}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`${text.remove} ${names.symbol}`}
              onClick={onRemove}
            >
              <XIcon aria-hidden="true" />
            </Button>
          </div>
          <SlotColumns
            quantity={quantity}
            choice={state}
            firstSelect={firstSelect}
            onRole={chooseRole}
            onUnit={chooseColumnUnit}
            onApply={() => {
              keepFocus.current = true;
              void applyChoice();
            }}
          />
        </div>
      </div>
    );
  }

  if (data !== undefined) {
    return (
      <div className="flex flex-col gap-1.5">
        {status}
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border px-3 py-2.5",
            dropping,
          )}
          {...dropTarget}
        >
          <Symbol filled>{names.symbol}</Symbol>
          <div className="min-w-0 flex-auto">
            <FileName>{dataName(data)}</FileName>
            <div className="text-xs text-muted-foreground">
              {fileSummary(quantity, data)}
            </div>
          </div>
          <Button
            ref={removeButton}
            variant="ghost"
            size="icon-sm"
            aria-label={`${text.remove} ${names.symbol}`}
            onClick={onRemove}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </div>
        {/* Demo data come in SI, and have no file to read again. */}
        {data.readAs !== undefined && (
          <div className="grid grid-cols-[auto_minmax(0,128px)] items-center justify-start gap-2 text-xs text-muted-foreground">
            <span>{text.valuesIn}</span>
            <UnitSelect
              quantity={quantity}
              value={unitOf(data.readAs, quantity)}
              label={names.title}
              onChange={(unit) => {
                void changeUnit(unit);
              }}
            />
          </div>
        )}
        {data.implausible === true && (
          <Alert>
            <TriangleAlertIcon aria-hidden="true" />
            <AlertTitle>{text.checkUnitTitle}</AlertTitle>
            <AlertDescription>
              {text.issues.implausible_magnitude}
            </AlertDescription>
          </Alert>
        )}
        {state.status === "idle" && state.warnings.length > 0 && (
          <ul className="m-0 list-none p-0 text-xs text-muted-foreground">
            {state.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      {status}
      <DropArea
        slotId={quantity}
        icon={<Symbol filled={false}>{names.symbol}</Symbol>}
        title={names.title}
        inputRef={input}
        {...handlers}
      />
      {state.status === "failed" && (
        <Alert variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>
            {state.name !== "" && (
              <div className="font-mono break-all">{state.name}</div>
            )}
            <ul className="m-0 list-none p-0">
              {state.errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
