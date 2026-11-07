import { useEffect } from "react";

import { holdsFiles, useSessionStore } from "@/session/store";

/**
 * Files are kept in memory only, so a reload or closing the tab loses them. The browser asks first,
 * in its own words, as a page cannot set the text.
 */
export function useLeaveWarning() {
  const warn = useSessionStore(holdsFiles);

  useEffect(() => {
    if (!warn) {
      return undefined;
    }
    const ask = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", ask);
    return () => {
      window.removeEventListener("beforeunload", ask);
    };
  }, [warn]);
}
