import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { modelsQuery } from "@/api/queries";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { formatNumber, parseNumber } from "@/lib/numbers";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  firstModel,
  fitModeOf,
  settingsFor,
  type FitModeDescription,
  type ModelDescription,
} from "@/model/selection";
import { useSessionStore, type Quantity } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

const { model: text, data: dataText } = STRINGS;

function quantitySymbol(quantity: Quantity): string {
  return dataText.quantities[quantity].symbol;
}

function modeLabel(mode: FitModeDescription): string {
  return mode.quantities.map(quantitySymbol).join(" + ");
}

function disabledReason(mode: FitModeDescription): string {
  const issue = mode.known_issues.find(({ id }) =>
    mode.disabled_by.includes(id),
  );
  const known: Record<string, string> = text.disabledReasons;
  return (issue && known[issue.message_key]) ?? text.disabledReason;
}

function scatteringLabel(id: string): string {
  const known: Record<string, string> = text.scatteringNames;
  return known[id] ?? id;
}

function positiveOrNull(text: string): number | null {
  const number = parseNumber(text);
  return number !== null && number > 0 ? number : null;
}

function Group({
  label,
  hideLabel = false,
  children,
}: {
  label: string;
  /** For a choice that its options explain, such as SPB and DPB. Its control keeps the name. */
  hideLabel?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {!hideLabel && <span className="text-[13px] font-medium">{label}</span>}
      {children}
    </div>
  );
}

function ChoiceGroup({
  label,
  hideLabel = false,
  value,
  onChange,
  options,
}: {
  label: string;
  hideLabel?: boolean;
  value: string | null;
  onChange: (value: string) => void;
  options: readonly {
    id: string;
    label: string;
    disabled?: boolean;
    /** Shown on hover or focus, and read as the option's description. */
    hint?: string;
  }[];
}) {
  const hintId = useId();
  return (
    <Group label={label} hideLabel={hideLabel}>
      <ToggleGroup
        type="single"
        variant="outline"
        className="w-full"
        aria-label={label}
        value={value ?? ""}
        onValueChange={(next) => {
          // Pressing the chosen one would otherwise leave nothing chosen.
          if (next !== "") {
            onChange(next);
          }
        }}
      >
        {options.map((option) => {
          const item = (
            <ToggleGroupItem
              key={option.id}
              value={option.id}
              disabled={option.disabled === true}
              aria-describedby={
                option.hint === undefined ? undefined : `${hintId}-${option.id}`
              }
              // A tooltip's trigger sets its own data-state, so being chosen shows from aria-checked.
              className="flex-auto aria-checked:bg-accent aria-checked:text-accent-foreground"
            >
              {option.label}
            </ToggleGroupItem>
          );
          return option.hint === undefined ? (
            item
          ) : (
            <Tooltip key={option.id}>
              <TooltipTrigger asChild>{item}</TooltipTrigger>
              <TooltipContent>{option.hint}</TooltipContent>
            </Tooltip>
          );
        })}
      </ToggleGroup>
      {options.map(
        (option) =>
          option.hint !== undefined && (
            <span key={option.id} id={`${hintId}-${option.id}`} hidden>
              {option.hint}
            </span>
          ),
      )}
    </Group>
  );
}

/**
 * A number being typed stays as text, and reaches the session on leaving the field or on Enter, so
 * the steps on the way to it do not count. An unchanged value does not, as that would clear a result.
 */
function DegeneracyField({
  label,
  value,
  invalid,
  errorId,
  onInvalidChange,
  onCommit,
}: {
  label: string;
  value: number;
  invalid: boolean;
  errorId: string;
  onInvalidChange: (invalid: boolean) => void;
  onCommit: (value: number) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState(formatNumber(value));
  const commit = () => {
    const number = positiveOrNull(draft);
    onInvalidChange(number === null);
    if (number !== null) {
      setDraft(formatNumber(number));
      if (number !== value) {
        onCommit(number);
      }
    }
  };
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium">
        {label}
      </label>
      <Input
        id={id}
        inputMode="decimal"
        autoComplete="off"
        value={draft}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        onChange={(event) => {
          setDraft(event.target.value);
          onInvalidChange(false);
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            commit();
          }
        }}
      />
    </div>
  );
}

function DegeneracyFields({
  band1,
  band2,
  onBand1Commit,
  onBand2Commit,
}: {
  band1: number;
  band2: number;
  onBand1Commit: (value: number) => void;
  onBand2Commit: (value: number) => void;
}) {
  const errorId = useId();
  const [band1Invalid, setBand1Invalid] = useState(false);
  const [band2Invalid, setBand2Invalid] = useState(false);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-2 gap-3">
        <DegeneracyField
          label="N₁"
          value={band1}
          invalid={band1Invalid}
          errorId={errorId}
          onInvalidChange={setBand1Invalid}
          onCommit={onBand1Commit}
        />
        <DegeneracyField
          label="N₂"
          value={band2}
          invalid={band2Invalid}
          errorId={errorId}
          onInvalidChange={setBand2Invalid}
          onCommit={onBand2Commit}
        />
      </div>
      {band1Invalid || band2Invalid ? (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {text.degeneracyInvalid}
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">
          {text.degeneracyHint}
        </span>
      )}
    </div>
  );
}

function FitRangeFields({
  minK,
  maxK,
  onCommit,
}: {
  minK: number;
  maxK: number;
  onCommit: (minK: number, maxK: number) => void;
}) {
  const errorId = useId();
  const [minDraft, setMinDraft] = useState(formatNumber(minK));
  const [maxDraft, setMaxDraft] = useState(formatNumber(maxK));
  const [invalid, setInvalid] = useState(false);
  // Both together, as the two bounds only mean something as a pair.
  const commit = () => {
    const low = positiveOrNull(minDraft);
    const high = positiveOrNull(maxDraft);
    const valid = low !== null && high !== null && low < high;
    setInvalid(!valid);
    if (valid && (low !== minK || high !== maxK)) {
      onCommit(low, high);
    }
  };
  const commitOnEnter = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      commit();
    }
  };
  return (
    <Group label={text.range}>
      <div className="grid grid-cols-2 gap-3">
        <Input
          inputMode="decimal"
          autoComplete="off"
          aria-describedby={invalid ? errorId : undefined}
          aria-label={text.rangeMin}
          aria-invalid={invalid}
          value={minDraft}
          onChange={(event) => {
            setMinDraft(event.target.value);
            setInvalid(false);
          }}
          onBlur={commit}
          onKeyDown={commitOnEnter}
        />
        <Input
          inputMode="decimal"
          autoComplete="off"
          aria-describedby={invalid ? errorId : undefined}
          aria-label={text.rangeMax}
          aria-invalid={invalid}
          value={maxDraft}
          onChange={(event) => {
            setMaxDraft(event.target.value);
            setInvalid(false);
          }}
          onBlur={commit}
          onKeyDown={commitOnEnter}
        />
      </div>
      {invalid && (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {text.rangeInvalid}
        </span>
      )}
    </Group>
  );
}

function ModelControls({ models }: { models: readonly ModelDescription[] }) {
  const selection = useSessionStore((state) => state.selection);
  const saved = useSessionStore((state) => state.savedModelSettings);
  const setSelection = useSessionStore((state) => state.setSelection);
  const chooseModel = useSessionStore((state) => state.chooseModel);

  const model = models.find(({ id }) => id === selection.model);
  const mode = fitModeOf(model, selection.fitMode);
  if (
    model === undefined ||
    selection.minTemperatureK === null ||
    selection.maxTemperatureK === null
  ) {
    return null;
  }
  const disabledModes = model.fit_modes.filter(({ disabled }) => disabled);

  return (
    <div className="mt-3 flex flex-col gap-4">
      <ChoiceGroup
        label={text.bands}
        hideLabel
        value={model.id}
        onChange={(id) => {
          const next = models.find((candidate) => candidate.id === id);
          if (next !== undefined) {
            chooseModel(id, settingsFor(next, saved[id]));
          }
        }}
        options={models.map(({ id, name }) => ({
          id,
          label: id.toUpperCase(),
          hint: name,
        }))}
      />

      <div className="flex flex-col gap-1.5">
        <ChoiceGroup
          label={text.fitMode}
          value={mode?.id ?? null}
          onChange={(id) => {
            setSelection(
              settingsFor(model, {
                fitMode: id,
                scattering: selection.scattering,
                band1Degeneracy: selection.band1Degeneracy,
                band2Degeneracy: selection.band2Degeneracy,
              }),
            );
          }}
          options={model.fit_modes.map((candidate) => ({
            id: candidate.id,
            label: modeLabel(candidate),
            disabled: candidate.disabled,
          }))}
        />
        {disabledModes.map((disabled) => (
          <span key={disabled.id} className="text-xs text-muted-foreground">
            {`${modeLabel(disabled)}: ${disabledReason(disabled)}`}
          </span>
        ))}
      </div>

      {mode !== undefined && mode.scattering.length > 0 && (
        <Group label={text.scattering}>
          <Select
            value={selection.scattering ?? ""}
            onValueChange={(scattering) => {
              setSelection({ scattering });
            }}
          >
            <SelectTrigger className="w-full" aria-label={text.scattering}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {mode.scattering.map((id) => (
                <SelectItem key={id} value={id}>
                  {scatteringLabel(id)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Group>
      )}

      {mode?.degeneracy != null && (
        // A new model starts its fields from its own values.
        <DegeneracyFields
          key={model.id}
          band1={selection.band1Degeneracy}
          band2={selection.band2Degeneracy}
          onBand1Commit={(band1Degeneracy) => {
            setSelection({ band1Degeneracy });
          }}
          onBand2Commit={(band2Degeneracy) => {
            setSelection({ band2Degeneracy });
          }}
        />
      )}

      <FitRangeFields
        minK={selection.minTemperatureK}
        maxK={selection.maxTemperatureK}
        onCommit={(minTemperatureK, maxTemperatureK) => {
          setSelection({ minTemperatureK, maxTemperatureK });
        }}
      />
    </div>
  );
}

/** Which fit can run: all of it comes from the model descriptions of the API. */
export function ModelPanel() {
  const { data, isPending, isError } = useQuery(modelsQuery);
  const models = data?.models;
  const selected = useSessionStore((state) => state.selection.model);
  const setSelection = useSessionStore((state) => state.setSelection);

  useEffect(() => {
    const model = models === undefined ? undefined : firstModel(models);
    if (selected === null && model !== undefined) {
      setSelection({
        model: model.id,
        ...settingsFor(model),
        minTemperatureK: model.default_min_temperature_k,
        maxTemperatureK: model.default_max_temperature_k,
      });
    }
  }, [models, selected, setSelection]);

  return (
    <Panel title={text.title}>
      {isPending && (
        <p role="status" className="mt-3 mb-0 text-xs text-muted-foreground">
          {text.loading}
        </p>
      )}
      {isError && (
        <div className="mt-3">
          <Alert variant="destructive">
            <AlertCircleIcon aria-hidden="true" />
            <AlertDescription>{text.loadFailed}</AlertDescription>
          </Alert>
        </div>
      )}
      {models !== undefined && <ModelControls models={models} />}
    </Panel>
  );
}
