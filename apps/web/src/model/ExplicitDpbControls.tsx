import { useState } from "react";
import { Input } from "@/components/ui/input";
import { parseNumber } from "@/lib/numbers";
import { useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const text = STRINGS.explicitDpb;

export function ExplicitDpbControls() {
  const selection = useSessionStore((state) => state.selection);
  const setSelection = useSessionStore((state) => state.setSelection);
  const density = selection.netElectronDensityPerM3 ?? 1e24;
  const configuration = selection.bandConfiguration ?? "vb_cb";
  const [draft, setDraft] = useState(String(density));
  const [invalid, setInvalid] = useState(false);
  const commit = () => {
    const value = parseNumber(draft);
    const valid =
      value !== null &&
      (configuration === "vb_cb" ||
        (configuration === "cb_cb" ? value > 0 : value < 0));
    setInvalid(!valid);
    if (valid && value !== density)
      setSelection({ netElectronDensityPerM3: value });
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
            setSelection({ bandConfiguration });
            setInvalid(
              bandConfiguration !== "vb_cb" &&
                (bandConfiguration === "cb_cb" ? density <= 0 : density >= 0),
            );
          }}
        >
          {Object.entries(text.configurations).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-[13px] font-medium">
        {text.density}
        <Input
          value={draft}
          aria-invalid={invalid}
          onChange={(event) => {
            setDraft(event.target.value);
            setInvalid(false);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
          }}
        />
      </label>
      <span
        className={
          invalid ? "text-xs text-destructive" : "text-xs text-muted-foreground"
        }
        role={invalid ? "alert" : undefined}
      >
        {invalid ? text.invalidDensity : text.densityHint}
      </span>
      {selection.fitMode === "dpb_s_rho_rh" && (
        <label className="flex gap-2 text-xs">
          <input
            type="checkbox"
            checked={selection.fitAbsoluteMass ?? false}
            onChange={(event) =>
              setSelection({ fitAbsoluteMass: event.target.checked })
            }
          />
          {text.fitMass}
        </label>
      )}
      <p className="m-0 text-xs text-muted-foreground">{text.manualStarts}</p>
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
