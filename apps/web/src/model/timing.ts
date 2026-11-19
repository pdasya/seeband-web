// User Timing entries for how long the live curves take (FS12, #56), which the browser's
// performance tools and apps/web/scripts/measure-latency.mjs read. They are recorded only when the
// app was opened with `?timing` in its address, as they would otherwise pile up for the whole
// session. They hold durations only, never values or data, and stay in this tab.

/** The prefix of every entry's name. */
export const TIMING_PREFIX = "seeband:";

let enabled =
  typeof location !== "undefined" &&
  new URLSearchParams(location.search).has("timing");

/** Turns recording on or off, as `?timing` does when the app opens. */
export function setTimingEnabled(on: boolean): void {
  enabled = on;
}

export function timingEnabled(): boolean {
  return enabled && typeof performance !== "undefined";
}

/** Records `name` as lasting from `startMs` to now, both on `performance.now()`'s clock. */
export function measureSince(name: string, startMs: number): void {
  if (!timingEnabled()) {
    return;
  }
  try {
    performance.measure(`${TIMING_PREFIX}${name}`, {
      start: startMs,
      end: performance.now(),
    });
  } catch {
    // A browser without User Timing Level 3 options only loses the measurement.
  }
}
