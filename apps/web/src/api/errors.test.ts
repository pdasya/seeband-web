// @vitest-environment node
import { describe, expect, test } from "vitest";

import { ApiClient } from "@/api/client";
import { ApiError } from "@/api/errors";
import { canRetry, createQueryClient } from "@/api/queries";

function failing(error: unknown): ApiClient {
  return new ApiClient({ fetch: () => Promise.reject(error as Error) });
}

describe("errors of a call", () => {
  test("the server's format is kept", async () => {
    const body = {
      code: "invalid_fit",
      message: "m",
      details: [{ location: ["body"], code: "x", message: "y" }],
    };
    const client = new ApiClient({
      fetch: () =>
        Promise.resolve(new Response(JSON.stringify(body), { status: 422 })),
    });

    await expect(client.getHealth()).rejects.toMatchObject({
      status: 422,
      code: "invalid_fit",
      details: body.details,
      retryAfterS: null,
    });
  });

  test.each([
    ["plain text", "Internal Server Error"],
    ["JSON in another format", '{"detail":"x"}'],
    ["null", "null"],
  ])("%s becomes a code of the client's", async (_, text) => {
    const client = new ApiClient({
      fetch: () => Promise.resolve(new Response(text, { status: 500 })),
    });

    await expect(client.getHealth()).rejects.toMatchObject({
      status: 500,
      code: "unexpected_response",
    });
  });

  test("a 200 that is not JSON is an error", async () => {
    const client = new ApiClient({
      fetch: () => Promise.resolve(new Response("<html>")),
    });

    await expect(client.getHealth()).rejects.toMatchObject({
      code: "unexpected_response",
    });
  });

  test("a failure to reach the server has a code, and no text of its own", async () => {
    const error = await failing(new TypeError("SECRET-VALUE"))
      .getHealth()
      .catch((caught: unknown) => caught);

    expect(error).toMatchObject({ status: 0, code: "network_error" });
    expect((error as Error).message).not.toContain("SECRET-VALUE");
  });

  test("an abort stays an abort", async () => {
    const controller = new AbortController();
    controller.abort();
    const abort = controller.signal.reason as Error;

    await expect(failing(abort).getHealth(controller.signal)).rejects.toBe(
      abort,
    );
  });

  test("an abort while reading an error's body stays an abort", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.error(abort);
      },
    });
    const client = new ApiClient({
      fetch: () => Promise.resolve(new Response(body, { status: 429 })),
    });

    await expect(client.getHealth()).rejects.toBe(abort);
  });

  test.each([
    ["5", 5],
    ["0", 0],
    ["", null],
    ["-1", null],
    ["Wed, 21 Oct 2026 07:28:00 GMT", null],
  ])("a Retry-After of %j gives %j", async (header, expected) => {
    const body = JSON.stringify({
      code: "rate_limited",
      message: "m",
      details: [],
    });
    const client = new ApiClient({
      fetch: () =>
        Promise.resolve(
          new Response(body, {
            status: 429,
            headers: { "Retry-After": header },
          }),
        ),
    });

    await expect(client.getHealth()).rejects.toMatchObject({
      retryAfterS: expected,
    });
  });

  test("a request sends its body as JSON, and calls fetch with no other this", async () => {
    let seen: RequestInit | undefined;
    const client = new ApiClient({
      fetch: (_, init) => {
        seen = init;
        return Promise.resolve(Response.json({}));
      },
    });

    await client.postParse({ text: "x" });

    expect(seen?.method).toBe("POST");
    expect(seen?.body).toBe('{"text":"x"}');
    expect(new Headers(seen?.headers).get("content-type")).toBe(
      "application/json",
    );
  });
});

describe("retries", () => {
  test.each([
    ["network", new ApiError(0, "network_error", "m"), true],
    [
      "a worker that died",
      new ApiError(503, "calculation_unavailable", "m"),
      true,
    ],
    ["a refusal", new ApiError(422, "invalid_fit", "m"), false],
    ["a limit", new ApiError(429, "rate_limited", "m"), false],
    ["a server error", new ApiError(500, "internal_error", "m"), false],
    ["anything else", new Error("m"), false],
  ])("%s", (_, error, expected) => {
    expect(canRetry(0, error)).toBe(expected);
    expect(canRetry(1, error)).toBe(false);
  });

  test("the query client uses them, and never repeats a mutation", () => {
    const defaults = createQueryClient().getDefaultOptions();

    expect(defaults.queries?.retry).toBe(canRetry);
    expect(defaults.mutations?.retry).toBe(false);
  });
});
