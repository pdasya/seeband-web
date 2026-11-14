import { useQuery } from "@tanstack/react-query";
import { CheckIcon, ChevronDownIcon, TriangleAlertIcon } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";

import { modelsQuery } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { DataPanel } from "@/data/DataPanel";
import { sessionMismatches } from "@/data/temperatureRanges";
import { cn } from "@/lib/utils";
import { fitModeOf } from "@/model/selection";
import {
  loadedAs,
  QUANTITIES,
  readsFiles,
  useSessionStore,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/**
 * The data, which fold into one line on Hide once separate files give the fit mode all it needs,
 * and open again when it lacks some. A page opened with complete data starts folded.
 */
export function DataBar() {
  const { data: models } = useQuery(modelsQuery);
  const data = useSessionStore((state) => state.data);
  const selection = useSessionStore((state) => state.selection);
  const reading = useSessionStore(readsFiles);
  const dataMode = useSessionStore((state) => state.dataMode);
  const mode = fitModeOf(
    models?.models.find(({ id }) => id === selection.model),
    selection.fitMode,
  );
  // A table stays open, as its mapping is what a user checks after loading it. So do data with
  // a doubt about their unit, as a fit from them would be wrong by a factor. T ranges that look like
  // °C beside K are only a hint, as two runs can cover such ranges, so they show but do not hold it.
  const complete =
    dataMode === "separate" &&
    mode !== undefined &&
    !reading &&
    mode.quantities.every((quantity) => data[quantity] !== undefined) &&
    !QUANTITIES.some(
      (quantity) => (data[quantity]?.unitDoubts?.length ?? 0) > 0,
    );

  const [open, setOpen] = useState(!complete);
  // Data a user has just entered stay in view, so the panel folds only on Hide. It opens again as
  // the data stop being complete, as a user then needs them.
  const [wasComplete, setWasComplete] = useState(complete);
  if (wasComplete !== complete) {
    setWasComplete(complete);
    if (!complete) {
      setOpen(true);
    }
  }

  // Details and Hide are two buttons, so a press moves focus to the one that takes its place.
  const panelToggle = useRef<HTMLButtonElement>(null);
  const barToggle = useRef<HTMLButtonElement>(null);
  const pressed = useRef(false);
  useEffect(() => {
    if (pressed.current) {
      pressed.current = false;
      (open ? panelToggle : barToggle).current?.focus();
    }
  }, [open]);

  const toggle = (ref: RefObject<HTMLButtonElement | null>) => (
    <Button
      ref={ref}
      variant="secondary"
      size="sm"
      aria-expanded={open}
      onClick={() => {
        pressed.current = true;
        setOpen(!open);
      }}
    >
      {open ? text.bar.hide : text.bar.details}
      <ChevronDownIcon
        aria-hidden="true"
        className={open ? "rotate-180" : undefined}
      />
    </Button>
  );

  const doubted = (quantity: (typeof QUANTITIES)[number]) =>
    (data[quantity]?.unitDoubts?.length ?? 0) > 0;
  const temperatureHint = sessionMismatches(data).length > 0;
  const anyDoubt = QUANTITIES.some(doubted) || temperatureHint;
  const names = [
    ...new Set(
      QUANTITIES.flatMap((quantity) => {
        const source = data[quantity]?.source;
        if (source === undefined) {
          return [];
        }
        return [source.kind === "file" ? source.name : text.demoSource];
      }),
    ),
  ];
  return (
    <>
      <div hidden={!open}>
        <DataPanel action={toggle(panelToggle)} />
      </div>
      {!open && (
        <section
          aria-label={text.title}
          className="flex flex-wrap items-center gap-x-3.5 gap-y-2 min-h-[58px] rounded-xl border bg-card px-3 py-2.5 shadow-card"
        >
          {/* A unit in doubt keeps its warning in view, as a fit from it is wrong by a factor. */}
          <span
            className={cn(
              "flex size-8 flex-none items-center justify-center rounded-md",
              anyDoubt
                ? "bg-warning-background text-warning-badge-foreground"
                : "bg-muted",
            )}
          >
            {anyDoubt ? (
              <TriangleAlertIcon className="size-4" aria-hidden="true" />
            ) : (
              <CheckIcon className="size-4" aria-hidden="true" />
            )}
          </span>
          <div className="min-w-0 flex-[0_1_auto]">
            <div className="text-[13px] font-semibold">{text.bar.loaded}</div>
            <div className="truncate font-mono text-xs text-muted-foreground">
              {names.join(" · ")}
            </div>
          </div>
          <ul className="m-0 flex flex-[1_1_auto] list-none flex-wrap gap-1.5 p-0">
            {QUANTITIES.map((quantity) => {
              const points = data[quantity]?.measurement.points;
              const symbol =
                text.quantities[loadedAs(quantity, data[quantity])].symbol;
              const doubt = points !== undefined && doubted(quantity);
              return (
                <li
                  key={quantity}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2.5 py-px text-xs font-medium",
                    doubt
                      ? "border-warning-border bg-warning-background text-warning-badge-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {doubt && (
                    <TriangleAlertIcon className="size-3" aria-hidden="true" />
                  )}
                  {points === undefined
                    ? text.bar.notLoaded(symbol)
                    : doubt
                      ? text.bar.checkUnit(symbol, points)
                      : text.bar.points(symbol, points)}
                </li>
              );
            })}
            {temperatureHint && (
              <li className="inline-flex items-center gap-1 rounded-full border border-warning-border bg-warning-background px-2.5 py-px text-xs font-medium text-warning-badge-foreground">
                <TriangleAlertIcon className="size-3" aria-hidden="true" />
                {text.bar.checkTemperature}
              </li>
            )}
          </ul>
          {toggle(barToggle)}
        </section>
      )}
    </>
  );
}
