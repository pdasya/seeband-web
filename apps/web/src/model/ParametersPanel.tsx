import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { modelsQuery } from "@/api/queries";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { formatNumber } from "@/lib/numbers";
import {
  coreToDisplay,
  displayToCore,
  parameterValues,
  steppedDisplayValue,
  tidy,
  typedDisplayValue,
  visibleParameters,
  type ParameterDescription,
} from "@/model/parameters";
import { fitModeOf } from "@/model/selection";
import { useSessionStore } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { parameters: text } = STRINGS;

function symbol(name: string): string {
  const known: Record<string, string> = text.symbols;
  return known[name] ?? name;
}

function hint({ meaning, unit }: ParameterDescription): string {
  const known: Record<string, string> = text.units;
  const shown = known[unit] ?? unit;
  return shown === "" ? meaning : `${meaning}, ${shown}`;
}

// Arrows move by one step, Page keys by ten, and so do Shift and an arrow, as in the slider itself.
const KEY_STEPS: Readonly<Record<string, number>> = {
  ArrowRight: 1,
  ArrowUp: 1,
  ArrowLeft: -1,
  ArrowDown: -1,
  PageUp: 10,
  PageDown: -10,
};

function ParameterControl({
  parameter,
  value,
  onChange,
}: {
  parameter: ParameterDescription;
  /** In core units. */
  value: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  const hintId = useId();
  const errorId = useId();
  // Text only while it is being typed, or while it cannot be used.
  const [draft, setDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const { minimum, maximum } = parameter.display_range;
  const label = symbol(parameter.name);
  const displayed = tidy(coreToDisplay(parameter, value));

  const commitDraft = () => {
    if (draft === null) {
      return;
    }
    const typed = typedDisplayValue(parameter, draft);
    setInvalid(typed === null);
    if (typed !== null) {
      setDraft(null);
      // An unchanged number keeps the value as it is, to the last bit, and any result.
      if (typed !== displayed) {
        onChange(displayToCore(parameter, typed));
      }
    }
  };
  const setDisplayed = (next: number) => {
    setDraft(null);
    setInvalid(false);
    onChange(displayToCore(parameter, next));
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <label htmlFor={id} className="text-[13px] font-medium">
            {label}
          </label>
          {parameter.role === "fixed" && (
            <Badge variant="secondary">{text.fixed}</Badge>
          )}
        </div>
        <Input
          id={id}
          // As a text field, it shows the same format everywhere. Some keypads for decimals have no minus.
          inputMode={minimum < 0 ? "text" : "decimal"}
          autoComplete="off"
          aria-describedby={invalid ? `${hintId} ${errorId}` : hintId}
          className="h-8 w-28 flex-none text-right font-mono text-[13px]"
          aria-invalid={invalid}
          value={draft ?? formatNumber(displayed)}
          onChange={(event) => {
            setDraft(event.target.value);
            setInvalid(false);
          }}
          onBlur={commitDraft}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              commitDraft();
            }
          }}
        />
      </div>
      <span id={hintId} className="text-xs text-muted-foreground">
        {hint(parameter)}
      </span>
      <Slider
        aria-label={label}
        min={minimum}
        max={maximum}
        // By whole control units, as on the desktop. The description's step is for the keyboard.
        step={parameter.display_scale}
        value={[displayed]}
        onValueChange={([next]) => {
          if (next !== undefined && next !== displayed) {
            setDisplayed(next);
          }
        }}
        onKeyDown={(event) => {
          const steps = KEY_STEPS[event.key];
          if (steps !== undefined) {
            event.preventDefault();
            const multiplier = event.shiftKey && Math.abs(steps) === 1 ? 10 : 1;
            const next = steppedDisplayValue(
              parameter,
              displayed,
              steps * multiplier,
            );
            if (next !== displayed) {
              setDisplayed(next);
            }
          }
        }}
      />
      <div className="flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>{formatNumber(minimum)}</span>
        <span>{formatNumber(maximum)}</span>
      </div>
      {invalid && (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {`${label}: ${text.outOfRange(formatNumber(minimum), formatNumber(maximum))}`}
        </span>
      )}
    </div>
  );
}

/** The parameters of the chosen fit mode. All of them come from its description. */
export function ParametersPanel() {
  const { data } = useQuery(modelsQuery);
  const selection = useSessionStore((state) => state.selection);
  const saved = useSessionStore((state) => state.parameters);
  const setParameter = useSessionStore((state) => state.setParameter);

  const model = data?.models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);

  return (
    <Panel title={text.title}>
      {mode !== undefined && (
        <div className="mt-3 flex flex-col gap-[18px]">
          {visibleParameters(mode, selection.scattering).map((parameter) => (
            <ParameterControl
              // A new mode starts its fields again.
              key={`${mode.id}:${parameter.name}`}
              parameter={parameter}
              value={
                parameterValues(mode, saved[mode.id])[parameter.name] ??
                parameter.core_range.default
              }
              onChange={(value) => {
                setParameter(mode.id, parameter.name, value);
              }}
            />
          ))}
        </div>
      )}
    </Panel>
  );
}
