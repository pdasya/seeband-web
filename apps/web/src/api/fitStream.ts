import type { components } from "@seeband/api-client";

import type { ApiClient, FitRequest } from "@/api/client";
import {
  ApiError,
  fetchOrThrow,
  NETWORK_ERROR,
  STREAM_ENDED,
  toApiError,
  UNEXPECTED_RESPONSE,
} from "@/api/errors";

type Schemas = components["schemas"];

/** The generated type of the stream itself is `unknown`, so this names its four events. */
export type FitEvent =
  | Schemas["FitStarted"]
  | Schemas["FitIteration"]
  | Schemas["FitDone"]
  | Schemas["FitError"];

/** The `data` of each Server-Sent Event, as they arrive. An unfinished last event is dropped. */
export async function* readEventData(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<string, void, undefined> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let data: string[] = [];
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      // A line ending in CR may be a CRLF cut in two, so that waits for the next chunk.
      const lines = buffer.split(/\r\n|\n|\r(?!$)/);
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line === "") {
          if (data.length > 0) {
            yield data.join("\n");
            data = [];
          }
        } else if (line === "data" || line.startsWith("data:")) {
          data.push(line.slice("data:".length).replace(/^ /, ""));
        }
        // Other lines do not matter here, and those from `:` keep the connection open.
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}

function parseEvent(data: string): FitEvent {
  try {
    return JSON.parse(data) as FitEvent;
  } catch {
    throw new ApiError(200, UNEXPECTED_RESPONSE, "An event is not valid JSON");
  }
}

/**
 * Starts a fit, and gives its events as they arrive. The last is `done` or `error`.
 *
 * Aborting `signal` is how to stop a fit: the server ends it, and this throws an `AbortError`. A
 * refusal throws an `ApiError`, as does a stream that ends with no last event, which is a lost
 * connection or a stop of the server, not a Stop.
 */
export async function* streamFit(
  client: ApiClient,
  request: FitRequest,
  signal?: AbortSignal,
): AsyncGenerator<FitEvent, void, undefined> {
  const response = await fetchOrThrow(
    client.fetch,
    `${client.baseUrl}/api/fit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream, application/json",
      },
      body: JSON.stringify(request),
      ...(signal === undefined ? {} : { signal }),
    },
  );
  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.body === null) {
    throw new ApiError(
      response.status,
      UNEXPECTED_RESPONSE,
      "The response has no body",
    );
  }
  try {
    for await (const data of readEventData(response.body)) {
      const event = parseEvent(data);
      yield event;
      if (event.type === "done" || event.type === "error") {
        return;
      }
    }
  } catch (error) {
    if (signal?.aborted || error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      0,
      NETWORK_ERROR,
      "The connection was lost during the fit",
    );
  }
  throw new ApiError(
    response.status,
    STREAM_ENDED,
    "The stream ended with no last event",
  );
}
