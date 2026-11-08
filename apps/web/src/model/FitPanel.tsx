import { ActivityIcon } from "lucide-react";
import { useId } from "react";

import { FitActions, FitMessages, FitStatusBadge } from "@/model/FitControls";
import type { useFitControl } from "@/model/useFitControl";
import type { useGuess } from "@/model/useGuess";
import { STRINGS } from "@/strings";

/** The head of the right column, in one line as the folded data are: the fit's state and its buttons. */
export function FitPanel({
  control,
  guess,
}: {
  control: ReturnType<typeof useFitControl>;
  guess: ReturnType<typeof useGuess>;
}) {
  const titleId = useId();
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-wrap items-center gap-x-3.5 gap-y-2 min-h-[58px] rounded-xl border bg-card px-3 py-2.5 shadow-card"
    >
      <span className="flex size-8 flex-none items-center justify-center rounded-md bg-muted">
        <ActivityIcon className="size-4" aria-hidden="true" />
      </span>
      <div className="flex min-w-0 flex-[0_1_auto] flex-wrap items-center gap-x-2.5 gap-y-1">
        <h1 id={titleId} className="m-0 text-[13px] font-semibold">
          {STRINGS.fit.panelTitle}
        </h1>
        <FitStatusBadge control={control} guess={guess} />
      </div>
      <div className="ml-auto flex flex-wrap gap-2">
        <FitActions control={control} guess={guess} />
      </div>
      {/* What the buttons say, under them; nothing at all while they say nothing. */}
      <div className="flex basis-full flex-col gap-2 empty:hidden">
        <FitMessages control={control} guess={guess} />
      </div>
    </section>
  );
}
