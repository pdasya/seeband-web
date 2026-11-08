import { FitActions, FitMessages, FitStatusBadge } from "@/model/FitControls";
import type { useFitControl } from "@/model/useFitControl";
import type { useGuess } from "@/model/useGuess";
import { STRINGS } from "@/strings";

/** The head of the right column: the fit's state, its buttons, and what they say. */
export function FitPanel({
  control,
  guess,
}: {
  control: ReturnType<typeof useFitControl>;
  guess: ReturnType<typeof useGuess>;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="m-0 text-base font-semibold tracking-[-0.01em]">
          {STRINGS.fit.panelTitle}
        </h1>
        <FitStatusBadge control={control} guess={guess} />
      </div>
      <div className="flex flex-wrap gap-2">
        <FitActions control={control} guess={guess} />
      </div>
      <FitMessages control={control} guess={guess} />
    </section>
  );
}
