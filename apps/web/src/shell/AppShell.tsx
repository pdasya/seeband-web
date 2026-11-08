import { useEffect, useRef } from "react";
import { Outlet, useLocation, useNavigationType } from "react-router";

import { useInterpolation } from "@/data/useInterpolation";
import { AppHeader } from "@/shell/AppHeader";
import { useLeaveWarning } from "@/shell/useLeaveWarning";
import { STRINGS } from "@/strings";

const MAIN_ID = "main";

/** What every screen shares. */
export function AppShell() {
  const { pathname, hash } = useLocation();
  const navigation = useNavigationType();
  useInterpolation();
  useLeaveWarning();
  const main = useRef<HTMLElement>(null);
  const shownPath = useRef(pathname);

  // After a move inside the app, focus would stay on a link, and a screen reader would say nothing.
  // A new screen starts at its top, with the header in view: focus alone would scroll it away.
  // Back and forward keep where the browser puts them, and so does a link to a place on the page.
  useEffect(() => {
    if (shownPath.current !== pathname) {
      shownPath.current = pathname;
      main.current?.focus({ preventScroll: true });
      if (navigation !== "POP" && hash === "") {
        window.scrollTo(0, 0);
      }
    }
  }, [pathname, navigation, hash]);

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
