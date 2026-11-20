// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  apiClient,
  type HealthResponse,
  type ModelsResponse,
} from "@/api/client";
import { createQueryClient, modelsQuery } from "@/api/queries";
import { sessionFile } from "@/session/sessionFile";
import { createSessionStore, useSessionStore } from "@/session/store";
import { SessionOpen } from "./SessionOpen";

const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useSessionStore.setState(original, true);
});

test("a legacy-only registry opens its historical DPB session without contacting migration", async () => {
  const state = createSessionStore().getState();
  state.selection = {
    ...state.selection,
    model: "dpb",
    fitMode: "dpb_s_rho",
    scattering: "acPh",
    minTemperatureK: 50,
    maxTemperatureK: 800,
  };
  const saved = await sessionFile(
    state,
    { appVersion: "legacy", apiVersion: null, saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  const file = new File([], "historical.json", { type: "application/json" });
  Object.defineProperty(file, "text", {
    value: async () => JSON.stringify(saved),
  });
  vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(function (
    this: HTMLInputElement,
  ) {
    Object.defineProperty(this, "files", { value: [file] });
    this.dispatchEvent(new Event("change"));
  });
  const models = {
    models: [
      {
        id: "dpb",
        fit_modes: [
          {
            id: "dpb_s_rho",
            parameters: [
              { name: "m_eff" },
              { name: "band_gap" },
              { name: "fermi_energy" },
            ],
          },
        ],
      },
    ],
  } as ModelsResponse;
  vi.spyOn(apiClient, "getModels").mockResolvedValue(models);
  vi.spyOn(apiClient, "getHealth").mockResolvedValue({
    core_version: "legacy",
  } as HealthResponse);
  const migrate = vi.spyOn(apiClient, "migrateDpb");
  const client = createQueryClient();
  client.setQueryData(modelsQuery.queryKey, models);
  render(
    <QueryClientProvider client={client}>
      <SessionOpen />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Open session" }));
  await vi.waitFor(() =>
    expect(useSessionStore.getState().restored?.appVersion).toBe("legacy"),
  );
  expect(useSessionStore.getState().selection.parameterization).toBeUndefined();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(migrate).not.toHaveBeenCalled();
  client.clear();
});
