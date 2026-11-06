import type { components } from "@seeband/api-client";

type ErrorBody = components["schemas"]["ErrorResponse"];
export type ApiErrorDetail = components["schemas"]["ErrorDetail"];

/** The client's own codes, for what the server's error format cannot say. */
export const NETWORK_ERROR = "network_error";
export const UNEXPECTED_RESPONSE = "unexpected_response";
export const STREAM_ENDED = "stream_ended";

/**
 * Any failure of a call, in the form of the server's errors.
 *
 * Show `code` through i18n. `message` is English text for developers.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: ApiErrorDetail[] = [],
    readonly retryAfterS: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  const { code, message, details } = body as Partial<ErrorBody>;
  return (
    typeof code === "string" &&
    typeof message === "string" &&
    Array.isArray(details)
  );
}

function retryAfterS(response: Response): number | null {
  // The other form is a date, which the API does not send.
  const header = response.headers.get("retry-after");
  return header !== null && /^\d+$/.test(header) ? Number(header) : null;
}

/** Reads an error response. Not every one is in the API's format, as when a proxy answers. */
export async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    body = undefined;
  }
  if (isErrorBody(body)) {
    return new ApiError(
      response.status,
      body.code,
      body.message,
      body.details,
      retryAfterS(response),
    );
  }
  return new ApiError(
    response.status,
    UNEXPECTED_RESPONSE,
    "The response is not in the API's format",
  );
}

/** Fetches, and turns a failure to reach the server into an `ApiError`. A stop stays as it is. */
export async function fetchOrThrow(
  fetchFunction: typeof fetch,
  url: string,
  init: RequestInit,
): Promise<Response> {
  try {
    return await fetchFunction(url, init);
  } catch (error) {
    if (init.signal?.aborted) {
      throw error;
    }
    throw new ApiError(0, NETWORK_ERROR, "The server could not be reached");
  }
}
