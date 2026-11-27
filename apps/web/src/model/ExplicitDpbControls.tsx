import { useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const text = STRINGS.explicitDpb;

/** New sessions specify the common Fermi energy independently of carrier sign. */
export function ExplicitDpbControls() {
  const selection = useSessionStore((state) => state.selection);
  const setSelection = useSessionStore((state) => state.setSelection);
  const archivedDensity = selection.parameterization === "explicit_density_v1";
  const configuration = selection.bandConfiguration ?? "vb_cb";
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-muted-foreground">
        {archivedDensity ? text.archivedDensity : text.fermiRepresentation}
      </span>
      <label className="text-[13px] font-medium">
        {text.configuration}
        <select
          className="mt-1 block w-full rounded-md border bg-background p-2"
          value={configuration}
          disabled={archivedDensity}
          onChange={(event) =>
            setSelection({
              bandConfiguration: event.target.value as typeof configuration,
            })
          }
        >
          {Object.entries(text.configurations).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {!archivedDensity && (
        <span className="text-xs text-muted-foreground">{text.fermiHint}</span>
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
