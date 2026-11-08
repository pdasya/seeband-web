import { SettingsIcon } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatNumber, parseNumber } from "@/lib/numbers";
import {
  coreToDisplay,
  displayToCore,
  editableParameters,
  parameterSymbol,
  shortened,
  type FitBounds,
  type ParameterDescription,
} from "@/model/parameters";
import type { FitModeDescription } from "@/model/selection";
import { isFitActive, useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const { parameters: text } = STRINGS;

function BoundsRow({
  parameter,
  bounds,
  disabled,
  onChange,
  onValidity,
}: {
  parameter: ParameterDescription;
  /** In core units. */
  bounds: FitBounds;
  disabled: boolean;
  onChange: (bounds: FitBounds) => void;
  onValidity: (invalid: boolean) => void;
}) {
  const errorId = useId();
  const [lowerDraft, setLowerDraft] = useState<string | null>(null);
  const [upperDraft, setUpperDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const symbol = parameterSymbol(parameter.name);
  const shown = (core: number) =>
    formatNumber(shortened(coreToDisplay(parameter, core)));

  const markInvalid = (next: boolean) => {
    setInvalid(next);
    onValidity(next);
  };

  // Both ends count together, so they are checked as focus leaves the row, not each field.
  const commit = () => {
    const lowerText = lowerDraft ?? shown(bounds.lower);
    const upperText = upperDraft ?? shown(bounds.upper);
    const lowerTyped = parseNumber(lowerText);
    const upperTyped = parseNumber(upperText);
    if (lowerTyped === null || upperTyped === null) {
      markInvalid(true);
      return;
    }
    // An unchanged text keeps the exact value, which it shows shortened.
    const lowerSame = lowerText === shown(bounds.lower);
    const upperSame = upperText === shown(bounds.upper);
    const next = {
      lower: lowerSame ? bounds.lower : displayToCore(parameter, lowerTyped),
      upper: upperSame ? bounds.upper : displayToCore(parameter, upperTyped),
    };
    if (next.lower >= next.upper) {
      markInvalid(true);
      return;
    }
    markInvalid(false);
    setLowerDraft(null);
    setUpperDraft(null);
    if (!lowerSame || !upperSame) {
      onChange(next);
    }
  };
  const fieldProps = {
    disabled,
    inputMode: "text" as const,
    autoComplete: "off",
    "aria-invalid": invalid,
    "aria-describedby": invalid ? errorId : undefined,
    className: "h-8 text-right font-mono text-[13px]",
    onKeyDown: (event: { key: string }) => {
      if (event.key === "Enter") {
        commit();
      }
    },
  };

  return (
    <div className="flex flex-col gap-1">
      <div
        className="grid grid-cols-[3.5rem_1fr_1fr] items-center gap-2"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) {
            commit();
          }
        }}
      >
        <span className="text-[13px] font-medium">{symbol}</span>
        <Input
          {...fieldProps}
          aria-label={text.boundLower(symbol)}
          value={lowerDraft ?? shown(bounds.lower)}
          onChange={(event) => {
            setLowerDraft(event.target.value);
            markInvalid(false);
          }}
        />
        <Input
          {...fieldProps}
          aria-label={text.boundUpper(symbol)}
          value={upperDraft ?? shown(bounds.upper)}
          onChange={(event) => {
            setUpperDraft(event.target.value);
            markInvalid(false);
          }}
        />
      </div>
      {invalid && (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {text.boundsInvalid}
        </span>
      )}
    </div>
  );
}

/** The bounds a fit of this mode may use, where the description lets them change. */
export function BoundsEditor({
  mode,
  scattering,
}: {
  mode: FitModeDescription;
  scattering: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [tipOpen, setTipOpen] = useState(false);
  const gear = useRef<HTMLButtonElement>(null);
  // Focus comes back to the gear as the dialog closes, which is no reason to name it again.
  const refocusing = useRef(false);
  // Starts the rows again, as Default bounds also ends what was being typed.
  const [generation, setGeneration] = useState(0);
  // Rows that hold no valid bounds, which Done will not close on, so as not to drop them unsaid.
  const [invalidRows, setInvalidRows] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const done = useRef<HTMLButtonElement>(null);
  const custom = useSessionStore((state) => state.customBounds[mode.id]);
  const setBounds = useSessionStore((state) => state.setCustomBounds);
  const clearBounds = useSessionStore((state) => state.clearCustomBounds);
  const active = useSessionStore((state) => isFitActive(state.fit));
  const editable = editableParameters(mode, scattering);
  const hasCustom = custom !== undefined && Object.keys(custom).length > 0;

  if (editable.length === 0) {
    return null;
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        setInvalidRows(new Set());
      }}
    >
      <Tooltip
        open={tipOpen}
        onOpenChange={(next) => {
          if (!(next && refocusing.current)) {
            setTipOpen(next);
          }
        }}
      >
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button
              ref={gear}
              variant="outline"
              size="icon-sm"
              aria-label={text.editBounds}
            >
              <SettingsIcon aria-hidden="true" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>{text.editBounds}</TooltipContent>
      </Tooltip>
      <DialogContent
        closeLabel={text.closeBounds}
        // A click beside it is too easily made to close it on what was being typed.
        onInteractOutside={(event) => {
          event.preventDefault();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          refocusing.current = true;
          gear.current?.focus();
          refocusing.current = false;
        }}
      >
        <DialogHeader>
          <DialogTitle>{text.boundsTitle}</DialogTitle>
          <DialogDescription>{text.boundsHint}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-[3.5rem_1fr_1fr] gap-2 text-xs text-muted-foreground">
            <span />
            <span className="text-right">{text.boundLowerTitle}</span>
            <span className="text-right">{text.boundUpperTitle}</span>
          </div>
          {editable.map(({ parameter, bounds: defaults }) => (
            <BoundsRow
              key={`${mode.id}:${parameter.name}:${String(generation)}`}
              parameter={parameter}
              bounds={custom?.[parameter.name] ?? defaults}
              disabled={active}
              onChange={(bounds) => {
                const same =
                  bounds.lower === defaults.lower &&
                  bounds.upper === defaults.upper;
                setBounds(mode.id, parameter.name, same ? null : bounds);
              }}
              onValidity={(invalid) => {
                setInvalidRows((rows) => {
                  const next = new Set(rows);
                  if (invalid) {
                    next.add(parameter.name);
                  } else {
                    next.delete(parameter.name);
                  }
                  return next;
                });
              }}
            />
          ))}
        </div>
        <DialogFooter>
          {hasCustom && (
            <Button
              variant="ghost"
              disabled={active}
              onClick={() => {
                clearBounds(mode.id);
                setGeneration(generation + 1);
                setInvalidRows(new Set());
                // This button goes away now, and focus must not go with it.
                done.current?.focus();
              }}
            >
              {text.defaultBounds}
            </Button>
          )}
          <Button
            ref={done}
            onClick={() => {
              if (invalidRows.size === 0) {
                setOpen(false);
              }
            }}
          >
            {text.boundsDone}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
