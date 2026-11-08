import type { components, operations } from "@seeband/api-client";

import {
  ApiError,
  fetchOrThrow,
  toApiError,
  UNEXPECTED_RESPONSE,
} from "@/api/errors";

type Schemas = components["schemas"];

export type HealthResponse = Schemas["HealthResponse"];
export type ModelsResponse =
  operations["get_models"]["responses"][200]["content"]["application/json"];
export type CalcRequest = Schemas["CalcRequest"];
export type CalcResponse = Schemas["CalcResponse"];
export type BandDiagramRequest = Schemas["BandDiagramRequest"];
export type BandDiagramResponse = Schemas["BandDiagramResponse"];
export type ParseRequest = Schemas["ParseRequest"];
export type ParseResponse = Schemas["ParseResponse"];
export type GuessRequest = Schemas["GuessRequest"];
export type GuessResponse =
  operations["post_guess"]["responses"][200]["content"]["application/json"];
export type DemoResponse = Schemas["DemoResponse"];
export type FitRequest = Schemas["FitApiRequest"];

export interface ApiClientOptions {
  /** Empty in the app, as `/api` is on its own origin. See the README. */
  baseUrl?: string;
  fetch?: typeof fetch;
}

/** The calls of the API. Each takes a signal, to stop it. */
export class ApiClient {
  readonly baseUrl: string;
  readonly fetch: typeof fetch;

  constructor({ baseUrl = "", fetch: fetchFunction }: ApiClientOptions = {}) {
    this.baseUrl = baseUrl;
    // Called through a function, as a browser's `fetch` must not get another `this`.
    this.fetch =
      fetchFunction ?? ((input, init) => globalThis.fetch(input, init));
  }

  getHealth(signal?: AbortSignal) {
    return this.request<HealthResponse>(
      "GET",
      "/api/health",
      undefined,
      signal,
    );
  }

  getModels(signal?: AbortSignal) {
    return this.request<ModelsResponse>(
      "GET",
      "/api/models",
      undefined,
      signal,
    );
  }

  getDemo(signal?: AbortSignal) {
    return this.request<DemoResponse>("GET", "/api/demo", undefined, signal);
  }

  postCalc(body: CalcRequest, signal?: AbortSignal) {
    return this.request<CalcResponse>("POST", "/api/calc", body, signal);
  }

  postBandDiagram(body: BandDiagramRequest, signal?: AbortSignal) {
    return this.request<BandDiagramResponse>(
      "POST",
      "/api/band-diagram",
      body,
      signal,
    );
  }

  postParse(body: ParseRequest, signal?: AbortSignal) {
    return this.request<ParseResponse>("POST", "/api/parse", body, signal);
  }

  postGuess(body: GuessRequest, signal?: AbortSignal) {
    return this.request<GuessResponse>("POST", "/api/guess", body, signal);
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    signal: AbortSignal | undefined,
  ): Promise<T> {
    const response = await fetchOrThrow(this.fetch, `${this.baseUrl}${path}`, {
      method,
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
      ...(signal === undefined ? {} : { signal }),
    });
    if (!response.ok) {
      throw await toApiError(response);
    }
    try {
      return (await response.json()) as T;
    } catch (error) {
      if (signal?.aborted) {
        throw error;
      }
      throw new ApiError(
        response.status,
        UNEXPECTED_RESPONSE,
        "The response is not valid JSON",
      );
    }
  }
}

export const apiClient = new ApiClient();
