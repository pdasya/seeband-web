import {
  AlertCircleIcon,
  LoaderCircleIcon,
  UploadIcon,
  XIcon,
} from "lucide-react";
import { useState, type ChangeEvent, type DragEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ACCEPTED_EXTENSIONS } from "@/data/readFile";
import { useFileUpload } from "@/data/useFileUpload";
import { cn } from "@/lib/utils";
import {
  useSessionStore,
  type Quantity,
  type SessionData,
} from "@/session/store";
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
  const low = TEMPERATURE_FORMAT.format(measurement.min_temperature_k);
  const high = TEMPERATURE_FORMAT.format(measurement.max_temperature_k);
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

/** One quantity's file: a place to drop or choose it, then its card. */
export function FileSlot({ quantity }: { quantity: Quantity }) {
  const { data: text } = STRINGS;
  const names = text.quantities[quantity];
  const data = useSessionStore((state) => state.data[quantity]);
  const { state, upload, remove, fail } = useFileUpload(quantity);
  const [dragging, setDragging] = useState(false);

  const onChoose = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // So that choosing the same file again, perhaps after editing it, reads it again.
    event.target.value = "";
    if (file !== undefined) {
      void upload(file);
    }
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const files = event.dataTransfer.files;
    const [file] = files;
    if (files.length > 1) {
      fail(text.oneFile);
    } else if (file !== undefined) {
      void upload(file);
    }
  };
  const dropTarget = {
    onDragOver: (event: DragEvent) => {
      event.preventDefault();
      setDragging(true);
    },
    onDragLeave: () => {
      setDragging(false);
    },
    onDrop,
  };
  const dropping = dragging && "border-ring bg-muted";

  if (state.status === "loading") {
    return (
      <div
        role="status"
        className="flex items-center gap-3 rounded-lg border px-3 py-2.5"
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
      </div>
    );
  }

  if (data !== undefined) {
    const { source } = data;
    return (
      <div className="flex flex-col gap-1.5">
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border px-3 py-2.5",
            dropping,
          )}
          {...dropTarget}
        >
          <Symbol filled>{names.symbol}</Symbol>
          <div className="min-w-0 flex-auto">
            <FileName>
              {source.kind === "file" ? source.name : text.demoSource}
            </FileName>
            <div className="text-xs text-muted-foreground">
              {fileSummary(quantity, data)}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`${text.remove} ${names.symbol}`}
            onClick={remove}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </div>
        {state.status === "idle" && state.warnings.length > 0 && (
          <ul className="m-0 list-none p-0 text-xs text-muted-foreground">
            {state.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label
        className={cn(
          "relative flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-[var(--color-zinc-300)] bg-[var(--color-zinc-50)] px-3 py-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring",
          dropping,
        )}
        {...dropTarget}
      >
        <Symbol filled={false}>{names.symbol}</Symbol>
        <div className="min-w-0 flex-auto">
          <div className="text-[13px] font-medium">{names.title}</div>
          <div className="text-xs text-muted-foreground">{text.dropHint}</div>
        </div>
        <UploadIcon
          className="size-4 flex-none text-muted-foreground"
          aria-hidden="true"
        />
        <input
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          onChange={onChoose}
        />
      </label>
      {state.status === "failed" && (
        <Alert variant="destructive">
          <AlertCircleIcon aria-hidden="true" />
          <AlertDescription>
            {state.name !== "" && (
              <div className="font-mono break-all">{state.name}</div>
            )}
            <ul className="m-0 list-none p-0">
              {state.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
