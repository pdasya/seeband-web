import type { ReactNode } from "react";

/** The design's two columns: they wrap once the side panel and main column no longer fit. */
export function TwoColumns({
  side,
  main,
}: {
  side: ReactNode;
  main: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start gap-6">
      <aside className="flex max-w-full min-w-0 flex-[1_1_300px] flex-col gap-4">
        {side}
      </aside>
      <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
        {main}
      </div>
    </div>
  );
}

/** The title of a screen. `status` is the slot for its status badge, and `actions` for buttons. */
export function PageHeading({
  title,
  subtitle,
  status,
  actions,
}: {
  title: string;
  subtitle: string;
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="m-0 text-2xl font-semibold tracking-[-0.02em]">
            {title}
          </h1>
          {status}
        </div>
        <p className="mt-1 mb-0 text-muted-foreground">{subtitle}</p>
      </div>
      {actions !== undefined && (
        <div className="flex flex-wrap gap-2">{actions}</div>
      )}
    </div>
  );
}

/** A card with a heading, as the design draws its sections. */
export function Panel({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card shadow-card">
      <div className="p-5">
        <h2 className="m-0 text-lg font-semibold tracking-[-0.01em]">
          {title}
        </h2>
        {children}
      </div>
    </section>
  );
}
