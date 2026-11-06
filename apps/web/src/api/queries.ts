import { QueryClient, queryOptions } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import { ApiError, NETWORK_ERROR } from "@/api/errors";

const MAX_RETRIES = 1;

/** Only what can pass by itself. A 429 says when to try again, and FS tasks show that. */
export function canRetry(failures: number, error: unknown): boolean {
  if (failures >= MAX_RETRIES || !(error instanceof ApiError)) {
    return false;
  }
  return error.code === NETWORK_ERROR || error.status === 503;
}

/** Answers stay in memory only, as measurements must not be stored. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: canRetry, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

export const modelsQuery = queryOptions({
  queryKey: ["models"],
  queryFn: ({ signal }) => apiClient.getModels(signal),
});

export const demoQuery = queryOptions({
  queryKey: ["demo"],
  queryFn: ({ signal }) => apiClient.getDemo(signal),
  // It changes only with a new release.
  staleTime: Infinity,
});
