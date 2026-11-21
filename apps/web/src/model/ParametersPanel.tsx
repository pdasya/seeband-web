import { heldForFit } from "@/model/explicitDpb";
import { useCarrierDomains } from "@/model/carrierDomain";
import { InfoIcon, LockIcon, LockOpenIcon } from "lucide-react";
import { useId, useState } from "react";

import { useModels } from "@/api/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Toggle } from "@/components/ui/toggle";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatNumber } from "@/lib/numbers";
import {
  coreToDisplay,
  explorationCoreValue,
  explorationSliderRange,
  inExplorationDomain,
  parameterSymbol,
  parameterValues,
  isShownValue,
  shownValue,
  steppedDisplayValue,
  tidy,
  typedDisplayValue,
  visibleParameters,
  withCustomRange,
  type ParameterDescription,
  type ExplorationDomain,
} from "@/model/parameters";
import { BoundsEditor } from "@/model/BoundsEditor";
import { fitModeOf } from "@/model/selection";
import { isFitActive, useSessionStore } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { parameters: text } = STRINGS;

function hint({ meaning, display_unit: unit }: ParameterDescription): string {
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
  disabled,
  onChange,
  held,
  domain,
}: {
  parameter: ParameterDescription;
  /** While a fit moves the values, as it would overwrite a change. */
  disabled: boolean;
  /** In core units. */
  value: number;
  onChange: (value: number) => void;
  /** For a fitted parameter: whether a fit keeps it at its value, and how to change that. */
  held?: { value: boolean; onChange: (held: boolean) => void } | undefined;
  domain?: ExplorationDomain | undefined;
}) {
  const id = useId();
  const hintId = useId();
  const errorId = useId();
  const domainId = useId();
  // Text only while it is being typed, or while it cannot be used.
  const [draft, setDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);
  const { minimum, maximum } = parameter.display_range;
  const emptyDomain =
    domain !== undefined &&
    (domain.lower === Infinity ||
      domain.upper === -Infinity ||
      (domain.lower !== undefined &&
        domain.upper !== undefined &&
        (domain.lower > domain.upper ||
          (domain.lower === domain.upper && !domain.inclusive))));
  const sliderRange = explorationSliderRange(parameter, domain);
  const sliderMinimum = sliderRange?.minimum ?? minimum;
  const sliderMaximum = sliderRange?.maximum ?? maximum;
  const label = parameterSymbol(parameter.name);
  const exactDisplay = coreToDisplay(parameter, value);
  const displayed = tidy(exactDisplay);
  const rounded = shownValue(parameter, displayed);
  const fieldValue =
    domain &&
    inExplorationDomain(value, domain) &&
    explorationCoreValue(parameter, rounded, domain) === null
      ? exactDisplay
      : rounded;
  // A value moved from elsewhere, such as by a fit, ends what was being typed.
  const [typedOver, setTypedOver] = useState(displayed);
  if (typedOver !== displayed) {
    setTypedOver(displayed);
    setDraft(null);
    setInvalid(false);
  }

  const commitDraft = () => {
    if (disabled || draft === null) {
      return;
    }
    const typed = typedDisplayValue(parameter, draft, domain);
    const core =
      typed === null ? null : explorationCoreValue(parameter, typed, domain);
    setInvalid(core === null);
    if (typed !== null && core !== null) {
      setDraft(null);
      // An unchanged number keeps the value as it is, to the last bit, and any result.
      if (
        !inExplorationDomain(value, domain) ||
        !isShownValue(parameter, displayed, typed)
      ) {
        onChange(core);
      }
    }
  };
  const setDisplayed = (next: number) => {
    if (disabled) return;
    const core = explorationCoreValue(parameter, next, domain);
    if (core === null) return;
    setDraft(null);
    setInvalid(false);
    onChange(core);
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <label htmlFor={id} className="text-[13px] font-medium">
            {label}
          </label>
          {/* Hover and focus open it, and so does a tap, as a touch screen has no hover. */}
          <Tooltip open={hintOpen} onOpenChange={setHintOpen}>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={text.about(label)}
                onClick={(event) => {
                  // The trigger would close it on a click.
                  event.preventDefault();
                  setHintOpen(true);
                }}
                className="-m-1 inline-flex size-6 items-center justify-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                <InfoIcon className="size-3.5" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-64">
              {hint(parameter)}
            </TooltipContent>
          </Tooltip>
          {parameter.role === "fixed" && (
            <Badge variant="secondary">{text.fixed}</Badge>
          )}
          {held?.value === true && (
            <Badge variant="secondary">{text.held}</Badge>
          )}
        </div>
        {/* The value stays editable while held: it is the value the fit keeps. */}
        {held !== undefined && (
          <Toggle
            variant="outline"
            size="sm"
            className="ml-auto size-7 min-w-7"
            disabled={disabled}
            pressed={held.value}
            onPressedChange={held.onChange}
            aria-label={text.hold(label)}
          >
            {held.value ? (
              <LockIcon aria-hidden="true" />
            ) : (
              <LockOpenIcon aria-hidden="true" />
            )}
          </Toggle>
        )}
        <Input
          id={id}
          disabled={disabled}
          // As a text field, it shows the same format everywhere. Some keypads for decimals have no minus.
          inputMode={minimum < 0 ? "text" : "decimal"}
          autoComplete="off"
          aria-describedby={[
            hintId,
            domain !== undefined ? domainId : "",
            invalid ? errorId : "",
          ]
            .filter(Boolean)
            .join(" ")}
          className="h-7 w-28 flex-none text-right font-mono text-[13px]"
          aria-invalid={invalid}
          title={formatNumber(displayed)}
          value={draft ?? formatNumber(fieldValue)}
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
      {/* The tooltip shows it on demand, and the field keeps it as its description. */}
      <span id={hintId} className="sr-only">
        {hint(parameter)}
      </span>
      <Slider
        aria-label={label}
        disabled={
          disabled || sliderRange === null || sliderMinimum === sliderMaximum
        }
        min={sliderMinimum}
        max={sliderMaximum}
        // By whole control units, as on the desktop. The description's step is for the keyboard.
        // A value shown in another unit, as an energy in eV, moves by the step of that unit.
        step={
          parameter.display_factor === 1
            ? parameter.display_scale
            : parameter.display_range.step
        }
        // A fit can end outside the control's range, and the number shows where.
        value={[Math.min(sliderMaximum, Math.max(sliderMinimum, displayed))]}
        onValueChange={([next]) => {
          if (next !== undefined && next !== displayed) {
            setDisplayed(
              Math.min(sliderMaximum, Math.max(sliderMinimum, next)),
            );
          }
        }}
        onKeyDown={(event) => {
          const steps = KEY_STEPS[event.key];
          if (steps !== undefined) {
            event.preventDefault();
            const multiplier = event.shiftKey && Math.abs(steps) === 1 ? 10 : 1;
            const next = Math.min(
              sliderMaximum,
              Math.max(
                sliderMinimum,
                steppedDisplayValue(parameter, displayed, steps * multiplier),
              ),
            );
            if (next !== displayed) {
              setDisplayed(next);
            }
          }
        }}
      />
      <div className="flex justify-between font-mono text-[11px] text-muted-foreground">
        <span>{formatNumber(shownValue(parameter, sliderMinimum))}</span>
        <span>{formatNumber(shownValue(parameter, sliderMaximum))}</span>
      </div>
      {domain !== undefined && (
        <span id={domainId} className="text-xs text-muted-foreground">
          {emptyDomain
            ? text.noDomainValues
            : text.explorationDomain(
                [
                  domain.lower === undefined
                    ? ""
                    : `${label} ${domain.inclusive ? "≥" : ">"} ${formatNumber(coreToDisplay(parameter, domain.lower))}`,
                  domain.upper === undefined
                    ? ""
                    : `${label} ${domain.inclusive ? "≤" : "<"} ${formatNumber(coreToDisplay(parameter, domain.upper))}`,
                ]
                  .filter(Boolean)
                  .join(", "),
              )}
          {!emptyDomain &&
            sliderRange === null &&
            ` ${text.noExplorationRange}`}
        </span>
      )}
      {invalid && (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {domain !== undefined &&
          draft !== null &&
          typedDisplayValue(parameter, draft) !== null
            ? text.outsideCarrierDomain
            : `${label}: ${text.outOfRange(
                formatNumber(shownValue(parameter, minimum)),
                formatNumber(shownValue(parameter, maximum)),
              )}`}
        </span>
      )}
    </div>
  );
}

/** The parameters of the chosen fit mode. All of them come from its description. */
export function ParametersPanel() {
  const { data } = useModels();
  const selection = useSessionStore((state) => state.selection);
  const saved = useSessionStore((state) => state.parameters);
  const setParameter = useSessionStore((state) => state.setParameter);
  const resets = useSessionStore((state) => state.parameterResets);
  const customBounds = useSessionStore((state) => state.customBounds);
  const held = useSessionStore((state) => state.held);
  const setHeld = useSessionStore((state) => state.setHeld);
  const setSelection = useSessionStore((state) => state.setSelection);
  const active = useSessionStore((state) => isFitActive(state.fit));

  const model = data?.models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  const values =
    mode === undefined ? {} : parameterValues(mode, saved[mode.id], selection);
  const { domains, failed, retry } = useCarrierDomains(
    values,
    selection,
    mode !== undefined && saved[mode.id]?.fermi_energy !== undefined,
  );

  return (
    <Panel
      title={text.title}
      action={
        mode !== undefined && (
          <BoundsEditor mode={mode} scattering={selection.scattering} />
        )
      }
    >
      {failed && (
        <div
          role="alert"
          className="mt-2 flex items-center gap-2 text-xs text-destructive"
        >
          <span>{text.explorationLoadFailed}</span>
          <Button variant="outline" size="sm" onClick={retry}>
            {text.retryExploration}
          </Button>
        </div>
      )}
      {mode !== undefined && (
        <div className="mt-2 flex flex-col gap-3">
          {visibleParameters(mode, selection.scattering).map((parameter) => (
            <ParameterControl
              // A new mode or a reset starts its fields again.
              key={`${mode.id}:${parameter.name}:${String(resets)}`}
              disabled={active || domains[parameter.name] === null}
              domain={domains[parameter.name] ?? undefined}
              parameter={withCustomRange(
                parameter,
                customBounds[mode.id]?.[parameter.name],
              )}
              value={values[parameter.name] ?? parameter.core_range.default}
              onChange={(value) => {
                setParameter(mode.id, parameter.name, value);
              }}
              held={
                parameter.role === "fitted"
                  ? {
                      value: heldForFit(
                        selection,
                        held[mode.id] ?? [],
                      ).includes(parameter.name),
                      onChange: (next) => {
                        if (
                          selection.parameterization !== undefined &&
                          parameter.name === "m1"
                        ) {
                          setSelection({ fitAbsoluteMass: !next });
                        }
                        setHeld(mode.id, parameter.name, next);
                      },
                    }
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </Panel>
  );
}
