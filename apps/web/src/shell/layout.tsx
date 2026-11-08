import type { ReactNode } from "react";

/** The title of a screen. `status` is the slot for its status badge, and `actions` for buttons. */
export function PageHeading({
  title,
  subtitle,
  status,
  actions,
}: {
  title: string;
  subtitle?: string;
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
        {subtitle !== undefined && (
          <p className="mt-1 mb-0 text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {actions !== undefined && (
        <div className="flex flex-wrap gap-2 print:hidden">{actions}</div>
      )}
    </div>
  );
}

/** A card with a heading, as the design draws its sections. */
export function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  /** Beside the title, for what acts on the whole section. */
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card shadow-card">
      <div className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="m-0 text-base font-semibold tracking-[-0.01em]">
            {title}
          </h2>
          {action}
        </div>
        {subtitle !== undefined && (
          <p className="mt-1 mb-0 text-[13px] text-muted-foreground">
            {subtitle}
          </p>
        )}
        {children}
      </div>
    </section>
  );
}
