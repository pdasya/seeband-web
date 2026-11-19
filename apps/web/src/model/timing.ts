// User Timing entries for how long the live curves take, which the browser's performance tools
// and apps/web/scripts/measure-latency.mjs read (FS12, #56). They hold durations only, never
// values or data, and stay in this tab.

/** The prefix of every entry's name. */
export const TIMING_PREFIX = "seeband:";

/** Records `name` as lasting from `startMs` to now, both on `performance.now()`'s clock. */
export function measureSince(name: string, startMs: number): void {
  if (typeof performance === "undefined") {
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
