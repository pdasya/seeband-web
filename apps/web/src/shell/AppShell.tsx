import type { ReactNode } from "react";
import { Outlet } from "react-router";

import { AppHeader } from "@/shell/AppHeader";
import { STRINGS } from "@/strings";

const MAIN_ID = "main";

/** What every screen shares. `children` replaces the routed page, for the error view. */
export function AppShell({ children }: { children?: ReactNode }) {
  return (
    <div className="min-h-screen">
      <a
        href={`#${MAIN_ID}`}
        className="sr-only rounded-md bg-background px-3 py-1.5 font-medium focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-10"
      >
        {STRINGS.skipToContent}
      </a>
      <AppHeader />
      <main
        id={MAIN_ID}
        tabIndex={-1}
        className="mx-auto box-border max-w-[var(--layout-max-width)] p-6"
      >
        {children ?? <Outlet />}
      </main>
    </div>
  );
}
