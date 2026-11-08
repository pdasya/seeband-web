import { apiClient, type FitRequest } from "@/api/client";
import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { streamFit } from "@/api/fitStream";
import { useSessionStore } from "@/session/store";

// Here rather than in a component, so that a fit goes on while another screen is open.
let controller: AbortController | null = null;
let currentRun = 0;

function store() {
  return useSessionStore.getState();
}

/** Ends a running fit. The values of its last iteration stay. */
export function stopFit(): void {
  controller?.abort();
  controller = null;
  store().fitStopped(currentRun);
}

/** Runs a fit, and any other that was running ends. It ends in the store's fit state. */
export async function runFit(request: FitRequest): Promise<void> {
  controller?.abort();
  const own = new AbortController();
  controller = own;
  const run = store().fitRequested(request.fit_mode, request.start);
  currentRun = run;
  try {
    for await (const event of streamFit(apiClient, request, own.signal)) {
      store().fitEvent(run, event);
    }
  } catch (error) {
    // After a Stop or a newer run, the store no longer takes this one's failure.
    const failure =
      error instanceof ApiError
        ? error
        : new ApiError(0, NETWORK_ERROR, "The request failed");
    store().fitFailed(run, {
      code: failure.code,
      message: failure.message,
      details: failure.details,
    });
  } finally {
    if (controller === own) {
      controller = null;
    }
  }
}
