// @vitest-environment node
import { describe, expect, test } from "vitest";

import { ApiClient, type FitRequest } from "@/api/client";
import { ApiError } from "@/api/errors";
import { readEventData, streamFit, type FitEvent } from "@/api/fitStream";

const REQUEST = { model: "dpb" } as FitRequest;

function streamOf(chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(
          typeof chunk === "string" ? encoder.encode(chunk) : chunk,
        );
      }
      controller.close();
    },
  });
}

async function collect<T>(items: AsyncIterable<T>): Promise<T[]> {
  const found: T[] = [];
  for await (const item of items) {
    found.push(item);
  }
  return found;
}

function clientAnswering(
  response: Response | (() => Promise<Response>),
): ApiClient {
  return new ApiClient({
    fetch: () =>
      response instanceof Response ? Promise.resolve(response) : response(),
  });
}

const STARTED = 'data: {"type":"started"}\n\n';
const ITERATION =
  'data: {"type":"iteration","iteration":1,"parameters":{"m_eff":null}}\n\n';
const DONE =
  'data: {"type":"done","result":{"parameters":{},"status":"converged","parameter_errors":{},"at_bounds":[],"known_issues":[]}}\n\n';

describe("readEventData", () => {
  test("reads events however the chunks fall, one byte at a time included", async () => {
    const whole = `${STARTED}: ping\n\n${ITERATION}${DONE}`;
    const bytes = new TextEncoder().encode(whole);

    const data = await collect(
      readEventData(streamOf([...bytes].map((b) => new Uint8Array([b])))),
    );

    expect(data.map((item) => (JSON.parse(item) as FitEvent).type)).toEqual([
      "started",
      "iteration",
      "done",
    ]);
  });

  test("keeps a character split between chunks", async () => {
    const bytes = new TextEncoder().encode('data: {"a":"ρ"}\n\n');
    const middle = bytes.indexOf(0xcf) + 1;

    const data = await collect(
      readEventData(streamOf([bytes.slice(0, middle), bytes.slice(middle)])),
    );

    expect(data).toEqual(['{"a":"ρ"}']);
  });

  test.each([
    ["CRLF", "data: 1\r\n\r\ndata: 2\r\n\r\n"],
    ["CR", "data: 1\r\rdata: 2\r\r\n"],
    ["no space after the colon", "data:1\n\ndata:2\n\n"],
  ])("reads lines with %s", async (_, text) => {
    expect(await collect(readEventData(streamOf([text])))).toEqual(["1", "2"]);
  });

  test("a CRLF cut in two is one line end", async () => {
    expect(
      await collect(
        readEventData(streamOf(["data: 1\r", "\n\r", "\ndata: 2\n\n"])),
      ),
    ).toEqual(["1", "2"]);
  });

  test.each([
    ["one chunk", ["data: 1\r\r"]],
    ["two chunks", ["data: 1\r", "\r"]],
  ])("an event ended by a final CR arrives, in %s", async (_, chunks) => {
    expect(await collect(readEventData(streamOf(chunks)))).toEqual(["1"]);
  });

  test("a line too long stops, whether or not it ever ends", async () => {
    const chunk = "x".repeat(600_000);

    await expect(
      collect(readEventData(streamOf([`data: ${chunk}`, chunk]))),
    ).rejects.toMatchObject({ code: "unexpected_response" });
    await expect(
      collect(readEventData(streamOf([`data: ${chunk}\ndata: ${chunk}\n`]))),
    ).rejects.toMatchObject({ code: "unexpected_response" });
  });

  test("the limit holds for each event, not for a stream", async () => {
    const event = `data: ${"x".repeat(600_000)}\n\n`;

    expect(await collect(readEventData(streamOf([event, event])))).toHaveLength(
      2,
    );
  });

  test("an event in many small chunks does not read them again each time", async () => {
    const piece = "x".repeat(16_000);
    const chunks = [
      "data: ",
      ...Array.from({ length: 60 }, () => piece),
      "\n\n",
    ];

    const started = performance.now();
    const data = await collect(readEventData(streamOf(chunks)));

    expect(data[0]).toHaveLength(960_000);
    expect(performance.now() - started).toBeLessThan(1_000);
  });

  test("joins data lines, and ignores comments and other fields", async () => {
    const text = ": ping\n\nevent: x\nid: 3\ndata: a\ndata: b\n\n";

    expect(await collect(readEventData(streamOf([text])))).toEqual(["a\nb"]);
  });

  test("drops an event that never ended", async () => {
    expect(
      await collect(readEventData(streamOf(["data: 1\n\ndata: 2\n"]))),
    ).toEqual(["1"]);
  });
});

describe("streamFit", () => {
  test("gives the events and stops at the last, ignoring anything after it", async () => {
    const client = clientAnswering(
      new Response(streamOf([STARTED, ITERATION, DONE, ITERATION])),
    );

    const events = await collect(streamFit(client, REQUEST));

    expect(events.map((event) => event.type)).toEqual([
      "started",
      "iteration",
      "done",
    ]);
  });

  test("gives an error event as an event, as the fit has ended", async () => {
    const body =
      'data: {"type":"error","error":{"code":"fit_timeout","message":"m","details":[]}}\n\n';

    const events = await collect(
      streamFit(clientAnswering(new Response(streamOf([body]))), REQUEST),
    );

    expect(events).toEqual([
      {
        type: "error",
        error: { code: "fit_timeout", message: "m", details: [] },
      },
    ]);
  });

  test("a stream with no last event is an error, not a stop", async () => {
    const client = clientAnswering(new Response(streamOf([STARTED])));

    await expect(collect(streamFit(client, REQUEST))).rejects.toMatchObject({
      code: "stream_ended",
    });
  });

  test("a refusal throws the server's error, with its hint", async () => {
    const body = JSON.stringify({
      code: "fit_queue_full",
      message: "m",
      details: [],
    });
    const client = clientAnswering(
      new Response(body, { status: 429, headers: { "Retry-After": "5" } }),
    );

    const error = await collect(streamFit(client, REQUEST)).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: "fit_queue_full",
      retryAfterS: 5,
    });
  });

  test("an event that is not JSON is an error", async () => {
    const client = clientAnswering(new Response(streamOf(["data: {\n\n"])));

    await expect(collect(streamFit(client, REQUEST))).rejects.toMatchObject({
      code: "unexpected_response",
    });
  });

  test.each(["null", "3", '"text"', "{}", '{"type":1}'])(
    "an event of %s is an unexpected response, not a lost connection",
    async (data) => {
      const client = clientAnswering(
        new Response(streamOf([`data: ${data}\n\n`])),
      );

      await expect(collect(streamFit(client, REQUEST))).rejects.toMatchObject({
        code: "unexpected_response",
      });
    },
  );

  test("a connection lost midway is an error", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(STARTED));
      },
      pull(controller) {
        controller.error(new TypeError("network"));
      },
    });

    await expect(
      collect(streamFit(clientAnswering(new Response(body)), REQUEST)),
    ).rejects.toMatchObject({ code: "network_error" });
  });

  test("an abort while reading stays an abort", async () => {
    const encoder = new TextEncoder();
    const controller = new AbortController();
    const body = new ReadableStream<Uint8Array>({
      start(stream) {
        stream.enqueue(encoder.encode(STARTED));
        controller.signal.addEventListener("abort", () => {
          stream.error(controller.signal.reason);
        });
      },
    });
    const seen: string[] = [];

    const failure = await (async () => {
      for await (const event of streamFit(
        clientAnswering(new Response(body)),
        REQUEST,
        controller.signal,
      )) {
        seen.push(event.type);
        controller.abort();
      }
    })().catch((caught: unknown) => caught);

    expect(seen).toEqual(["started"]);
    expect(failure).not.toBeInstanceOf(ApiError);
    expect((failure as Error).name).toBe("AbortError");
  });

  test("leaving early cancels the body, so that the connection closes", async () => {
    let cancelled = false;
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(STARTED));
      },
      cancel() {
        cancelled = true;
      },
    });

    for await (const event of streamFit(
      clientAnswering(new Response(body)),
      REQUEST,
    )) {
      expect(event.type).toBe("started");
      break;
    }

    expect(cancelled).toBe(true);
  });
});
