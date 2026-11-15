import type { Page } from "@playwright/test";

interface FitBody {
  fit_mode: string;
  start: Record<string, number>;
  measurements: Record<string, unknown>;
  bounds?: object;
  held?: string[];
}

declare global {
  interface Window {
    fitTest: {
      bodies: FitBody[];
      aborted: number;
      send: (event: object) => void;
      end: () => void;
      fail: () => void;
      refuse: { status: number; body: object } | null;
    };
  }
}

/** A fake `POST /api/fit`, whose stream the test feeds event by event. */
export async function fakeFit(page: Page) {
  await page.addInitScript(() => {
    const encoder = new TextEncoder();
    let stream: ReadableStreamDefaultController<Uint8Array> | null = null;
    const state: Window["fitTest"] = {
      bodies: [],
      aborted: 0,
      refuse: null,
      send: (event) => {
        stream?.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      },
      end: () => {
        stream?.close();
      },
      fail: () => {
        stream?.error(new TypeError("lost"));
      },
    };
    window.fitTest = state;
    const realFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (!url.endsWith("/api/fit")) {
        return realFetch(input, init);
      }
      state.bodies.push(JSON.parse(String(init?.body)) as FitBody);
      if (state.refuse !== null) {
        return Promise.resolve(
          new Response(JSON.stringify(state.refuse.body), {
            status: state.refuse.status,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      init?.signal?.addEventListener("abort", () => {
        state.aborted += 1;
      });
      const body = new ReadableStream<Uint8Array>({
        start: (controller) => {
          stream = controller;
          init?.signal?.addEventListener("abort", () => {
            controller.error(new DOMException("Aborted", "AbortError"));
          });
        },
      });
      return Promise.resolve(
        new Response(body, {
          headers: { "Content-Type": "text/event-stream" },
        }),
      );
    };
  });
}
