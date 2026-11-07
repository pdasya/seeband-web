import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
}: {
  parameter: ParameterDescription;
  /** In core units. */
  bounds: FitBounds;
  disabled: boolean;
  onChange: (bounds: FitBounds) => void;
}) {
  const errorId = useId();
  const [lowerDraft, setLowerDraft] = useState<string | null>(null);
  const [upperDraft, setUpperDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const symbol = parameterSymbol(parameter.name);
  const shown = (core: number) =>
    formatNumber(shortened(coreToDisplay(parameter, core)));

  // Both ends count together, so that moving a range past its old end takes two entries.
  const commit = () => {
    const lowerText = lowerDraft ?? shown(bounds.lower);
    const upperText = upperDraft ?? shown(bounds.upper);
    const lower = parseNumber(lowerText);
    const upper = parseNumber(upperText);
    if (lower === null || upper === null || lower >= upper) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setLowerDraft(null);
    setUpperDraft(null);
    // An unchanged text keeps the exact value, which it shows shortened.
    const lowerSame = lowerText === shown(bounds.lower);
    const upperSame = upperText === shown(bounds.upper);
    if (!lowerSame || !upperSame) {
      onChange({
        lower: lowerSame ? bounds.lower : displayToCore(parameter, lower),
        upper: upperSame ? bounds.upper : displayToCore(parameter, upper),
      });
    }
  };
  const fieldProps = {
    disabled,
    inputMode: "text" as const,
    autoComplete: "off",
    "aria-invalid": invalid,
    "aria-describedby": invalid ? errorId : undefined,
    className: "h-8 text-right font-mono text-[13px]",
    onBlur: commit,
    onKeyDown: (event: { key: string }) => {
      if (event.key === "Enter") {
        commit();
      }
    },
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="grid grid-cols-[3.5rem_1fr_1fr] items-center gap-2">
        <span className="text-[13px] font-medium">{symbol}</span>
        <Input
          {...fieldProps}
          aria-label={text.boundLower(symbol)}
          value={lowerDraft ?? shown(bounds.lower)}
          onChange={(event) => {
            setLowerDraft(event.target.value);
            setInvalid(false);
          }}
        />
        <Input
          {...fieldProps}
          aria-label={text.boundUpper(symbol)}
          value={upperDraft ?? shown(bounds.upper)}
          onChange={(event) => {
            setUpperDraft(event.target.value);
            setInvalid(false);
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
  // Starts the rows again, as Default bounds also ends what was being typed.
  const [generation, setGeneration] = useState(0);
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
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          {text.editBounds}
        </Button>
      </DialogTrigger>
      <DialogContent closeLabel={text.closeBounds}>
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
              }}
            >
              {text.defaultBounds}
            </Button>
          )}
          <DialogClose asChild>
            <Button>{text.boundsDone}</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
