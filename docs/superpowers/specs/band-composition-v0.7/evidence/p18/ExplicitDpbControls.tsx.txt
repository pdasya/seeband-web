import { useId, useState } from "react";
import { InfoIcon } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { formatNumber, parseNumber } from "@/lib/numbers";
import { useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const text = STRINGS.explicitDpb;

function DensityDpbControls() {
  const selection = useSessionStore((state) => state.selection);
  const setSelection = useSessionStore((state) => state.setSelection);
  const density = selection.netElectronDensityPerM3 ?? 1e24;
  const configuration = selection.bandConfiguration ?? "vb_cb";
  const magnitudeId = useId();
  const hintId = useId();
  const errorId = useId();
  const [polarity, setPolarity] = useState<"p" | "n">(
    configuration === "vb_vb" || density < 0 ? "p" : "n",
  );
  const [draft, setDraft] = useState(formatNumber(Math.abs(density)));
  const [hintOpen, setHintOpen] = useState(false);
  const requiresPositive = configuration !== "vb_cb" && density === 0;
  const branchHint = text.branchDensityHints[configuration];
  const [invalid, setInvalid] = useState(false);
  const [source, setSource] = useState({ density, configuration });
  // A restored value refreshes the field; zero keeps the researcher's pending p/n choice.
  if (source.density !== density || source.configuration !== configuration) {
    setSource({ density, configuration });
    setDraft(formatNumber(Math.abs(density)));
    setInvalid(false);
    if (configuration === "vb_vb" || density < 0) setPolarity("p");
    else if (configuration === "cb_cb" || density > 0) setPolarity("n");
  }
  const commit = () => {
    const value = parseNumber(draft);
    const valid =
      value !== null && value >= 0 && (configuration === "vb_cb" || value > 0);
    setInvalid(!valid);
    if (valid) {
      const signed = value === 0 ? 0 : polarity === "p" ? -value : value;
      setDraft(formatNumber(value));
      if (signed !== density) setSelection({ netElectronDensityPerM3: signed });
    }
  };
  const choosePolarity = (next: string) => {
    if (next !== "p" && next !== "n") return;
    if (
      (configuration === "vb_vb" && next !== "p") ||
      (configuration === "cb_cb" && next !== "n")
    )
      return;
    setPolarity(next);
    const signed =
      density === 0 ? 0 : next === "p" ? -Math.abs(density) : Math.abs(density);
    if (signed !== density) setSelection({ netElectronDensityPerM3: signed });
  };
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-muted-foreground">
        {text.representation}
      </span>
      <label className="text-[13px] font-medium">
        {text.configuration}
        <select
          className="mt-1 block w-full rounded-md border bg-background p-2"
          value={configuration}
          onChange={(event) => {
            const bandConfiguration = event.target
              .value as typeof configuration;
            const nextPolarity =
              bandConfiguration === "vb_vb"
                ? "p"
                : bandConfiguration === "cb_cb"
                  ? "n"
                  : polarity;
            const signed =
              density === 0
                ? 0
                : nextPolarity === "p"
                  ? -Math.abs(density)
                  : Math.abs(density);
            setPolarity(nextPolarity);
            setDraft(formatNumber(Math.abs(density)));
            setInvalid(false);
            if (bandConfiguration !== configuration || signed !== density)
              setSelection({
                bandConfiguration,
                netElectronDensityPerM3: signed,
              });
          }}
        >
          {Object.entries(text.configurations).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-2">
        <label htmlFor={magnitudeId} className="text-[13px] font-medium">
          {text.densityMagnitude}
        </label>
        <Tooltip
          open={hintOpen}
          onOpenChange={setHintOpen}
          disableHoverableContent
        >
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={text.densityAbout}
              onClick={(event) => {
                event.preventDefault();
                setHintOpen(true);
              }}
              className="inline-flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <InfoIcon className="size-3.5" aria-hidden="true" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-80">
            <p className="m-0">{text.densityTooltip}</p>
            <p className="mt-2 mb-0">{branchHint}</p>
          </TooltipContent>
        </Tooltip>
      </div>
      <div className="flex items-center gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          value={polarity}
          onValueChange={choosePolarity}
          aria-label={text.polarity}
          aria-describedby={hintId}
        >
          <ToggleGroupItem
            value="p"
            aria-label={text.polarities.p}
            disabled={configuration === "cb_cb"}
            className="aria-checked:bg-accent aria-checked:text-accent-foreground"
          >
            {text.p}
          </ToggleGroupItem>
          <ToggleGroupItem
            value="n"
            aria-label={text.polarities.n}
            disabled={configuration === "vb_vb"}
            className="aria-checked:bg-accent aria-checked:text-accent-foreground"
          >
            {text.n}
          </ToggleGroupItem>
        </ToggleGroup>
        <Input
          id={magnitudeId}
          value={draft}
          inputMode="decimal"
          autoComplete="off"
          aria-invalid={invalid || requiresPositive}
          aria-describedby={`${hintId}${invalid || requiresPositive ? ` ${errorId}` : ""}`}
          onChange={(event) => {
            setDraft(event.target.value);
            setInvalid(false);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
          }}
        />
      </div>
      <span className="text-xs font-mono" role="status" aria-live="polite">
        {density === 0
          ? configuration === "vb_cb"
            ? text.intrinsic(polarity)
            : text.zeroSameType
          : text.signedDensity(
              density < 0 ? "p" : "n",
              formatNumber(Math.abs(density)),
            )}
      </span>
      <span id={hintId} className="text-xs text-muted-foreground">
        {branchHint}
      </span>
      {(invalid || requiresPositive) && (
        <span id={errorId} role="alert" className="text-xs text-destructive">
          {requiresPositive ||
          (configuration !== "vb_cb" && parseNumber(draft) === 0)
            ? text.densityRequired
            : text.invalidMagnitude}
        </span>
      )}
      {selection.legacySource && (
        <details className="text-xs">
          <summary>{text.legacyResult}</summary>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap">
            {selection.legacySource}
          </pre>
        </details>
      )}
    </div>
  );
}

/** New sessions select carrier character; E_F remains a normal model parameter. */
export function ExplicitDpbControls() {
  const selection = useSessionStore((state) => state.selection);
  const setSelection = useSessionStore((state) => state.setSelection);
  const [hintOpen, setHintOpen] = useState(false);
  if (selection.parameterization === "explicit_density_v1")
    return <DensityDpbControls />;
  const configuration = selection.bandConfiguration ?? "vb_cb";
  const carrier = selection.carrierType ?? "p";
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-muted-foreground">
        {text.fermiRepresentation}
      </span>
      <label className="text-[13px] font-medium">
        {text.configuration}
        <select
          className="mt-1 block w-full rounded-md border bg-background p-2"
          value={configuration}
          onChange={(event) => {
            const bandConfiguration = event.target
              .value as typeof configuration;
            setSelection({
              bandConfiguration,
              carrierType:
                bandConfiguration === "vb_vb"
                  ? "p"
                  : bandConfiguration === "cb_cb"
                    ? "n"
                    : carrier,
            });
          }}
        >
          {Object.entries(text.configurations).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          value={carrier}
          aria-label={text.carrierType}
          onValueChange={(value) => {
            if (value === "p" || value === "n")
              setSelection({ carrierType: value });
          }}
        >
          <ToggleGroupItem
            value="p"
            disabled={configuration === "cb_cb"}
            aria-label={text.carrierTypes.p}
          >
            {text.p}
          </ToggleGroupItem>
          <ToggleGroupItem
            value="n"
            disabled={configuration === "vb_vb"}
            aria-label={text.carrierTypes.n}
          >
            {text.n}
          </ToggleGroupItem>
        </ToggleGroup>
        <Tooltip open={hintOpen} onOpenChange={setHintOpen}>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={text.carrierAbout}
              onClick={() => setHintOpen(true)}
              className="inline-flex size-6 items-center justify-center rounded-full text-muted-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <InfoIcon className="size-3.5" aria-hidden="true" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-80">
            {text.carrierTooltip}
          </TooltipContent>
        </Tooltip>
      </div>
      <span className="text-xs text-muted-foreground">{text.fermiHint}</span>
      {selection.legacySource && (
        <details className="text-xs">
          <summary>{text.legacyResult}</summary>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap">
            {selection.legacySource}
          </pre>
        </details>
      )}
    </div>
  );
}
