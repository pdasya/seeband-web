import { ApiError, NETWORK_ERROR } from "@/api/errors";

// Until the values rest, or at the latest at the longer delay, so that a curve follows a long drag.
export const DEBOUNCE_MS = 250;
export const MAX_WAIT_MS = 300;
// Past the API's own limit on a calculation. With one request at a time, a stuck one would block
// every later change.
export const STUCK_AFTER_MS = 60_000;
// If a limit asks for longer, the next change tries again anyway.
const MAX_RETRY_AFTER_S = 30;

/** Whether a failure sends the latest values again by itself. */
export function retriesByItself(error: ApiError): boolean {
  return (
    error.status === 429 &&
    error.retryAfterS !== null &&
    error.retryAfterS <= MAX_RETRY_AFTER_S
  );
}

export interface LatestOnlyHandlers<Result> {
  send: (body: string, signal: AbortSignal) => Promise<Result>;
  onResult: (result: Result, body: string) => void;
  /** `settled` is the body this ends, or null if another try is on its way. `sent` is the body. */
  onFailure: (error: ApiError, settled: string | null, sent: string) => void;
}

/**
 * Sends one request at a time, and always the latest values, so that requests cannot pile up on a
 * server that is slower than the changes. The server cannot stop a calculation that has started,
 * so a change does not abort the running request. Its answer comes first, then the latest values
 * go. So an old answer can never arrive after a newer one.
 */
export class LatestOnly<Result> {
  private latest: string | null = null;
  private waiting = false;
  private sent: string | null = null;
  private running: AbortController | null = null;
  private run = 0;
  private firstChangeAtMs: number | null = null;
  private notBeforeMs = 0;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private stuckTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly handlers: LatestOnlyHandlers<Result>) {}

  /**
   * The current values, or null with nothing to ask, which ends what is running. `waiting` holds
   * requests back, as while the data they need are on their way.
   */
  change(body: string | null, waiting: boolean): void {
    if (body === this.latest && waiting === this.waiting) {
      return;
    }
    this.latest = body;
    this.waiting = waiting;
    if (body === null) {
      this.stop();
    } else if (waiting) {
      this.clearDebounce();
    } else {
      this.debounce();
    }
  }

  /** Ends everything. A later change starts again. */
  dispose(): void {
    this.stop();
    this.latest = null;
    this.waiting = false;
  }

  private stop(): void {
    this.run += 1;
    this.running?.abort();
    this.running = null;
    this.sent = null;
    this.notBeforeMs = 0;
    this.clearDebounce();
    this.clearTimer("retryTimer");
    this.clearTimer("stuckTimer");
  }

  private clearTimer(name: "retryTimer" | "stuckTimer" | "debounceTimer") {
    const timer = this[name];
    if (timer !== null) {
      clearTimeout(timer);
      this[name] = null;
    }
  }

  private clearDebounce(): void {
    this.clearTimer("debounceTimer");
    this.firstChangeAtMs = null;
  }

  private debounce(): void {
    const now = Date.now();
    this.firstChangeAtMs ??= now;
    this.clearTimer("debounceTimer");
    this.debounceTimer = setTimeout(
      () => {
        this.debounceTimer = null;
        this.firstChangeAtMs = null;
        this.sendLatest();
      },
      Math.min(
        DEBOUNCE_MS,
        Math.max(0, MAX_WAIT_MS - (now - this.firstChangeAtMs)),
      ),
    );
  }

  private sendLatest(): void {
    const body = this.latest;
    if (
      body === null ||
      body === this.sent ||
      this.running !== null ||
      this.waiting ||
      Date.now() < this.notBeforeMs
    ) {
      return;
    }
    this.sent = body;
    this.run += 1;
    const { run } = this;
    const controller = new AbortController();
    this.running = controller;
    this.stuckTimer = setTimeout(() => {
      this.run += 1;
      controller.abort();
      this.failed(
        new ApiError(504, "calculation_timeout", "No answer in time"),
        body,
      );
    }, STUCK_AFTER_MS);

    this.handlers
      .send(body, controller.signal)
      .then((result) => {
        if (run === this.run) {
          this.finish();
          this.handlers.onResult(result, body);
          this.next();
        }
      })
      .catch((error: unknown) => {
        if (run === this.run) {
          this.failed(
            error instanceof ApiError
              ? error
              : new ApiError(0, NETWORK_ERROR, "The request failed"),
            body,
          );
        }
      });
  }

  private finish(): void {
    this.running = null;
    this.clearTimer("stuckTimer");
  }

  private failed(error: ApiError, body: string): void {
    this.finish();
    if (retriesByItself(error)) {
      const delayMs = (error.retryAfterS ?? 0) * 1000;
      this.sent = null;
      this.notBeforeMs = Date.now() + delayMs;
      this.clearTimer("retryTimer");
      this.retryTimer = setTimeout(() => {
        this.retryTimer = null;
        this.sendLatest();
      }, delayMs);
      this.handlers.onFailure(error, null, body);
    } else {
      this.handlers.onFailure(error, body, body);
      this.next();
    }
  }

  // Values that changed during a request go now, unless a debounce is still waiting for them.
  private next(): void {
    if (this.debounceTimer === null) {
      this.sendLatest();
    }
  }
}
