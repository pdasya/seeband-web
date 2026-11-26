// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { apiClient, type FitRequest, type ModelsResponse } from "@/api/client";
import { createQueryClient, modelsQuery } from "@/api/queries";
import { checksum, sessionFile } from "@/session/sessionFile";
import { createSessionStore, useSessionStore } from "@/session/store";
import { SessionOpen } from "./SessionOpen";

const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(original, true);
});

test.each([
  { convention: "all_valley", savedN: 8, expected: 0.5 },
  { convention: "single_valley", savedN: 8, expected: 2 },
  { convention: "all_valley", savedN: 1, expected: 2 },
])(
  "Hall migration confirms $convention with saved N₁=$savedN",
  async ({ convention, savedN, expected }) => {
    vi.stubGlobal("crypto", {});
    const request: FitRequest = {
      model: "dpb",
      fit_mode: "dpb_s_rho_rh",
      band_1_degeneracy: savedN,
      band_2_degeneracy: 3,
      start: { m1: 4 },
      min_temperature_k: 50,
      max_temperature_k: 800,
      measurements: { seebeck: { temperature_k: [100], values: [1e-4] } },
    };
    const state = createSessionStore().getState();
    state.selection = {
      ...state.selection,
      model: "dpb",
      fitMode: "dpb_s_rho_rh",
      scattering: "acPh",
      band1Degeneracy: 2,
      band2Degeneracy: 3,
    };
    state.fit = {
      status: "done",
      result: {
        status: "converged",
        parameters: { m1: 2, m_eff: -3, band_gap: 600, fermi_energy: -200 },
        parameter_errors: {},
        at_bounds: [],
        known_issues: [],
        held: [],
        parameter_status: {},
        core_version: "0.3.0",
      },
    };
    const saved = await sessionFile(
      state,
      {
        appVersion: "0.3.0",
        apiVersion: "0.3.0",
        saved: "2026-11-20T00:00:00Z",
      },
      () => null,
    );
    // Preserve a completed historical request with its actual multiplicity.
    if (saved.content.fit === null) throw new Error("Missing saved Hall fit");
    saved.content.fit.request = request;
    const file = new File([], "historical-hall.json", {
      type: "application/json",
    });
    // sessionFile's checksum must cover the historical request too.
    saved.checksum = await checksum(saved.content);
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
              id: "dpb_s_rho_rh",
              parameters: [{ name: "mass_ratio", core_range: { default: 1 } }],
            },
          ],
        },
      ],
    } as ModelsResponse;
    vi.spyOn(apiClient, "getModels").mockResolvedValue(models);
    const migrate = vi
      .spyOn(apiClient, "migrateDpb")
      .mockRejectedValue(new Error("Stop after capturing conversion"));
    const client = createQueryClient();
    client.setQueryData(modelsQuery.queryKey, models);
    render(
      <QueryClientProvider client={client}>
        <SessionOpen />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open session" }));
    await screen.findByRole("dialog");
    const choice = screen.queryByRole("combobox", {
      name: "Saved Hall mass convention",
    });
    const confirm = screen.getByRole("button", {
      name: "Confirm scale and convert",
    });
    if (savedN > 1) {
      expect(confirm.hasAttribute("disabled")).toBe(true);
      if (choice === null) throw new Error("Missing Hall convention choice");
      fireEvent.change(choice, { target: { value: convention } });
    } else {
      expect(choice).toBeNull();
      expect(confirm.hasAttribute("disabled")).toBe(false);
    }
    // Changing the requested target multiplicity must not reinterpret the historical mass.
    fireEvent.change(screen.getByLabelText(/N₁/), { target: { value: "27" } });
    expect(
      (screen.getByLabelText("Single-valley |m₁| (mₑ)") as HTMLInputElement)
        .value,
    ).toBe(String(expected).replace(".", ","));
    fireEvent.click(confirm);
    await vi.waitFor(() => expect(migrate).toHaveBeenCalled());
    expect(migrate.mock.calls[0]?.[0]).toMatchObject({
      m1: expect.closeTo(expected),
      band_1_degeneracy: 27,
      band_2_degeneracy: 3,
    });
    client.clear();
  },
);
