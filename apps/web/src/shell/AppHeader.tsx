import { NavLink } from "react-router";

import { cn } from "@/lib/utils";
import { STRINGS } from "@/strings";

const LINK = "rounded-md px-3 py-1.5 font-medium no-underline";
const IDLE_LINK = "text-[var(--color-zinc-600)] hover:text-foreground";

// These pages belong to the public site, not to the app, so they leave the app's router.
const SITE_OVERVIEW_PATH = "/";
const SITE_CONVENTIONS_PATH = "/conventions/";

function Logo() {
  return (
    <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M3 20c3-10 6-14 9-14s6 4 9 14" />
        <path d="M3 4c3 6 6 8 9 8s6-2 9-8" />
      </svg>
    </div>
  );
}

function AppLink({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(LINK, isActive ? "bg-muted text-foreground" : IDLE_LINK)
      }
    >
      {children}
    </NavLink>
  );
}

/** U6 moves this to `packages/ui`, to share with the site, and adds the language switch. */
export function AppHeader() {
  const { navigation } = STRINGS;
  return (
    <header className="border-b bg-background">
      <div className="mx-auto flex max-w-[var(--layout-max-width)] flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <Logo />
          <div className="text-base font-semibold tracking-[-0.01em]">
            {STRINGS.appName}
          </div>
          <span className="rounded-full border px-2 py-0.5 text-xs font-medium text-[var(--color-zinc-600)]">
            {STRINGS.appStage}
          </span>
        </div>
        <nav
          aria-label={navigation.label}
          className="flex flex-auto flex-wrap gap-1"
        >
          <a href={SITE_OVERVIEW_PATH} className={cn(LINK, IDLE_LINK)}>
            {navigation.overview}
          </a>
          <AppLink to="/fit">{navigation.fit}</AppLink>
          <AppLink to="/results">{navigation.results}</AppLink>
          <a href={SITE_CONVENTIONS_PATH} className={cn(LINK, IDLE_LINK)}>
            {navigation.conventions}
          </a>
        </nav>
      </div>
    </header>
  );
}
