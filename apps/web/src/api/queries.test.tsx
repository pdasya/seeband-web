// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { createQueryClient, useModels } from "./queries";
import { useSessionStore } from "@/session/store";

const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  useSessionStore.setState(original, true);
  vi.unstubAllGlobals();
});

function Catalog() {
  const { data } = useModels();
  return <output>{data?.models[0]?.name}</output>;
}

test("new sessions request Fermi metadata and restored density sessions request historical metadata", async () => {
  const requests: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      requests.push(url);
      const density = url.includes("explicit_density_v1");
      return new Response(
        JSON.stringify({
          models: [
            {
              id: "dpb",
              name: density ? "Historical density" : "Fermi energy",
            },
          ],
        }),
        {
          headers: { "content-type": "application/json" },
        },
      );
    }),
  );
  const client = createQueryClient();
  render(
    <QueryClientProvider client={client}>
      <Catalog />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText("Fermi energy")).toBeTruthy());
  expect(requests).toEqual(["/api/models?parameterization=explicit_fermi_v1"]);
  act(() =>
    useSessionStore.getState().setSelection({
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: "cb_cb",
      netElectronDensityPerM3: 2e24,
    }),
  );
  await waitFor(() =>
    expect(screen.getByText("Historical density")).toBeTruthy(),
  );
  expect(requests).toContain(
    "/api/models?parameterization=explicit_density_v1",
  );
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    2e24,
  );
  client.clear();
});
