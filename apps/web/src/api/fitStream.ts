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

// Far above any event of the API. Past this, something else is answering, and the tab must not
// grow without limit.
const MAX_EVENT_CHARACTERS = 1_000_000;

function tooLong(): ApiError {
  return new ApiError(200, UNEXPECTED_RESPONSE, "An event is too long");
}

/** Reads the lines of an event stream, and collects the `data` of each event. */
class EventParser {
  private line = "";
  private data: string[] = [];
  private dataCharacters = 0;
  // A CR may be half of a CRLF cut between chunks.
  private skipLineFeed = false;

  /** Takes more text, and returns the `data` of the events that it finished. */
  feed(text: string): string[] {
    const finished: string[] = [];
    let start = 0;
    if (this.skipLineFeed && text.length > 0) {
      this.skipLineFeed = false;
      if (text.startsWith("\n")) {
        start = 1;
      }
    }
    const lineEnd = /\r\n?|\n/g;
    lineEnd.lastIndex = start;
    for (
      let match = lineEnd.exec(text);
      match !== null;
      match = lineEnd.exec(text)
    ) {
      this.line += text.slice(start, match.index);
      start = match.index + match[0].length;
      this.skipLineFeed = match[0] === "\r" && start === text.length;
      const data = this.endLine();
      if (data !== null) {
        finished.push(data);
      }
    }
    this.line += text.slice(start);
    if (this.line.length + this.dataCharacters > MAX_EVENT_CHARACTERS) {
      throw tooLong();
    }
    return finished;
  }

  private endLine(): string | null {
    const { line } = this;
    this.line = "";
    if (line === "") {
      if (this.data.length === 0) {
        return null;
      }
      const data = this.data.join("\n");
      this.data = [];
      this.dataCharacters = 0;
      return data;
    }
    // Other lines do not matter here, and those from `:` keep the connection open.
    if (line === "data" || line.startsWith("data:")) {
      const value = line.slice("data:".length).replace(/^ /, "");
      this.data.push(value);
      this.dataCharacters += value.length;
      if (this.dataCharacters > MAX_EVENT_CHARACTERS) {
        throw tooLong();
      }
    }
    return null;
  }
}

/** The `data` of each Server-Sent Event, as they arrive. An unfinished last event is dropped. */
export async function* readEventData(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<string, void, undefined> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new EventParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        return;
      }
      yield* parser.feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}

function parseEvent(data: string): FitEvent {
  let event: unknown;
  try {
    event = JSON.parse(data);
  } catch {
    throw new ApiError(200, UNEXPECTED_RESPONSE, "An event is not valid JSON");
  }
  if (
    typeof event !== "object" ||
    event === null ||
    typeof (event as { type?: unknown }).type !== "string"
  ) {
    throw new ApiError(200, UNEXPECTED_RESPONSE, "An event has no type");
  }
  return event as FitEvent;
}

/** A failure to read is a lost connection, unless it is a stop or already says what it is. */
async function readNext(
  events: AsyncGenerator<string, void, undefined>,
  signal: AbortSignal | undefined,
): Promise<IteratorResult<string, void>> {
  try {
    return await events.next();
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
  const events = readEventData(response.body);
  try {
    for (;;) {
      const next = await readNext(events, signal);
      if (next.done) {
        break;
      }
      const event = parseEvent(next.value);
      yield event;
      if (event.type === "done" || event.type === "error") {
        return;
      }
    }
  } finally {
    await events.return();
  }
  throw new ApiError(
    response.status,
    STREAM_ENDED,
    "The stream ended with no last event",
  );
}
