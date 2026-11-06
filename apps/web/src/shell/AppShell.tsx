import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

import { useInterpolation } from "@/data/useInterpolation";
import { AppHeader } from "@/shell/AppHeader";
import { STRINGS } from "@/strings";

const MAIN_ID = "main";

/** What every screen shares. */
export function AppShell() {
  const { pathname } = useLocation();
  useInterpolation();
  const main = useRef<HTMLElement>(null);
  const shownPath = useRef(pathname);

  // After a move inside the app, focus would stay on a link, and a screen reader would say nothing.
  useEffect(() => {
    if (shownPath.current !== pathname) {
      shownPath.current = pathname;
      main.current?.focus();
    }
  }, [pathname]);

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
        ref={main}
        id={MAIN_ID}
        tabIndex={-1}
        className="mx-auto box-border max-w-[var(--layout-max-width)] p-6 outline-none"
      >
        <Outlet />
      </main>
    </div>
  );
}
