import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { modelsQuery } from "@/api/queries";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
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

function positiveOrNull(value: string): number | null {
  const number = Number(value);
  return value.trim() !== "" && Number.isFinite(number) && number > 0
    ? number
    : null;
}

function Group({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium">{label}</span>
      {children}
    </div>
  );
}

function ChoiceGroup({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string | null;
  onChange: (value: string) => void;
  options: readonly { id: string; label: string; disabled?: boolean }[];
}) {
  return (
    <Group label={label}>
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
        {options.map((option) => (
          <ToggleGroupItem
            key={option.id}
            value={option.id}
            disabled={option.disabled === true}
            className="flex-1"
          >
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </Group>
  );
}

/** A number being typed stays as text, and only one that holds reaches the session. */
function DegeneracyField({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number;
  onCommit: (value: number) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState(String(value));
  const invalid = positiveOrNull(draft) === null;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium">
        {label}
      </label>
      <Input
        id={id}
        type="number"
        min={1}
        step={1}
        value={draft}
        aria-invalid={invalid}
        onChange={(event) => {
          setDraft(event.target.value);
          const number = positiveOrNull(event.target.value);
          if (number !== null) {
            onCommit(number);
          }
        }}
      />
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
  const [minDraft, setMinDraft] = useState(String(minK));
  const [maxDraft, setMaxDraft] = useState(String(maxK));
  const low = positiveOrNull(minDraft);
  const high = positiveOrNull(maxDraft);
  const valid = low !== null && high !== null && low < high;
  const change = (nextMin: string, nextMax: string) => {
    setMinDraft(nextMin);
    setMaxDraft(nextMax);
    const nextLow = positiveOrNull(nextMin);
    const nextHigh = positiveOrNull(nextMax);
    // Both together, as the two bounds only mean something as a pair.
    if (nextLow !== null && nextHigh !== null && nextLow < nextHigh) {
      onCommit(nextLow, nextHigh);
    }
  };
  return (
    <Group label={text.range}>
      <div className="grid grid-cols-2 gap-3">
        <Input
          type="number"
          min={0}
          step={5}
          aria-label={text.rangeMin}
          aria-invalid={!valid}
          value={minDraft}
          onChange={(event) => {
            change(event.target.value, maxDraft);
          }}
        />
        <Input
          type="number"
          min={0}
          step={5}
          aria-label={text.rangeMax}
          aria-invalid={!valid}
          value={maxDraft}
          onChange={(event) => {
            change(minDraft, event.target.value);
          }}
        />
      </div>
      {!valid && (
        <span role="alert" className="text-xs text-destructive">
          {text.rangeInvalid}
        </span>
      )}
    </Group>
  );
}

function MissingData({ mode }: { mode: FitModeDescription }) {
  const data = useSessionStore((state) => state.data);
  const missing = mode.quantities.filter(
    (quantity) => data[quantity] === undefined,
  );
  if (missing.length === 0) {
    return null;
  }
  // A note rather than an alert, as this is the state before any data load.
  return (
    <Alert variant="warning" role="note">
      <AlertCircleIcon aria-hidden="true" />
      <AlertTitle>
        {`${text.missingTitle} ${missing.map(quantitySymbol).join(", ")}.`}
      </AlertTitle>
      <AlertDescription>{text.missingText}</AlertDescription>
    </Alert>
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
      <div className="flex flex-col gap-1.5">
        <ChoiceGroup
          label={text.bands}
          value={model.id}
          onChange={(id) => {
            const next = models.find((candidate) => candidate.id === id);
            if (next !== undefined) {
              chooseModel(id, settingsFor(next, saved[id]));
            }
          }}
          options={models.map(({ id }) => ({
            id,
            label: id.toUpperCase(),
          }))}
        />
        <span className="text-xs text-muted-foreground">{model.name}</span>
      </div>

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

      {mode !== undefined && <MissingData mode={mode} />}

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
        <div key={model.id} className="flex flex-col gap-1.5">
          <div className="grid grid-cols-2 gap-3">
            <DegeneracyField
              label="N₁"
              value={selection.band1Degeneracy}
              onCommit={(band1Degeneracy) => {
                setSelection({ band1Degeneracy });
              }}
            />
            <DegeneracyField
              label="N₂"
              value={selection.band2Degeneracy}
              onCommit={(band2Degeneracy) => {
                setSelection({ band2Degeneracy });
              }}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            {text.degeneracyHint}
          </span>
        </div>
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
    <Panel title={text.title} subtitle={text.subtitle}>
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
