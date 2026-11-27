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

test("signed-mass conversion keeps EF from the exact vector validated by migration", async () => {
  const state = createSessionStore().getState();
  state.selection = {
    ...state.selection,
    model: "dpb",
    fitMode: "dpb_s_rho",
    scattering: "acPh",
    carrierType: "p",
    netElectronDensityPerM3: 9e23,
  };
  // EF is supplied by the historical mode's default, not the saved drafts.
  state.parameters = { dpb_s_rho: { m_eff: -3, band_gap: 600 } };
  const saved = await sessionFile(
    state,
    { appVersion: "legacy", apiVersion: null, saved: "2026-11-20T00:00:00Z" },
    () => null,
  );
  const file = new File([], "historical.json");
  Object.defineProperty(file, "text", {
    value: async () => JSON.stringify(saved),
  });
  vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(function (
    this: HTMLInputElement,
  ) {
    Object.defineProperty(this, "files", { value: [file] });
    this.dispatchEvent(new Event("change"));
  });
  const explicitModels = {
    models: [
      {
        id: "dpb",
        fit_modes: [{ id: "dpb_s_rho", parameters: [{ name: "mass_ratio" }] }],
      },
    ],
  } as ModelsResponse;
  const historicalModels = {
    models: [
      {
        id: "dpb",
        fit_modes: [
          {
            id: "dpb_s_rho",
            parameters: [
              { name: "m_eff", core_range: { default: 1 } },
              { name: "band_gap", core_range: { default: 1000 } },
              { name: "fermi_energy", core_range: { default: -175 } },
            ],
          },
        ],
      },
    ],
  } as ModelsResponse;
  vi.spyOn(apiClient, "getModels").mockImplementation(
    async (_signal, parameterization) =>
      parameterization === undefined ? historicalModels : explicitModels,
  );
  vi.spyOn(apiClient, "getHealth").mockResolvedValue({
    core_version: "current",
  } as HealthResponse);
  const migrate = vi.spyOn(apiClient, "migrateDpb").mockResolvedValue({
    parameterization: "explicit_density_v1",
    band_configuration: "vb_cb",
    net_electron_density_per_m3: -2e24,
    parameters: { mass_ratio: 3, band_offset_k: 600, m1: 1.7 },
  });
  const client = createQueryClient();
  client.setQueryData(modelsQuery.queryKey, explicitModels);
  render(
    <QueryClientProvider client={client}>
      <SessionOpen />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Open session" }));
  await screen.findByRole("dialog");
  fireEvent.change(screen.getByLabelText("Single-valley |m₁| (mₑ)"), {
    target: { value: "1.7" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Confirm scale and convert" }),
  );
  await vi.waitFor(() =>
    expect(useSessionStore.getState().selection.parameterization).toBe(
      "explicit_fermi_v1",
    ),
  );
  expect(migrate).toHaveBeenCalledWith({
    parameters: { m_eff: -3, band_gap: 600, fermi_energy: -175 },
    m1: 1.7,
    band_1_degeneracy: state.selection.band1Degeneracy,
    band_2_degeneracy: state.selection.band2Degeneracy,
  });
  expect(useSessionStore.getState().parameters.dpb_s_rho).toEqual({
    mass_ratio: 3,
    band_offset_k: 600,
    m1: 1.7,
    fermi_energy: -175,
  });
  expect(
    useSessionStore.getState().selection.netElectronDensityPerM3,
  ).toBeUndefined();
  expect(useSessionStore.getState().selection.carrierType).toBeUndefined();
  expect(
    JSON.parse(useSessionStore.getState().selection.legacySource ?? "null")
      .content.parameters,
  ).toEqual(saved.content.parameters);
  client.clear();
});

test.each(["legacy", "plain-spb", "values", "bounds-only", "settings-only"])(
  "a historical session opens safely with dormant explicit DPB: %s",
  async (variant) => {
    const spb = variant !== "legacy";
    const dormant = spb && variant !== "plain-spb";
    const state = createSessionStore().getState();
    state.selection = {
      ...state.selection,
      model: spb ? "spb" : "dpb",
      fitMode: spb ? "spb_s" : "dpb_s_rho",
      scattering: "acPh",
      minTemperatureK: 50,
      maxTemperatureK: 800,
    };
    state.parameters = {
      spb_s: { fermi_energy: 30 },
      dpb_s_rho: { fermi_energy: -200, m_eff: -3, band_gap: 600 },
    };
    state.customBounds = {
      dpb_s_rho: { fermi_energy: { lower: -500, upper: 100 } },
    };
    state.held = { dpb_s_rho: ["fermi_energy"] };
    state.savedModelSettings = {
      dpb: {
        fitMode: "dpb_s_rho",
        scattering: "acPh",
        band1Degeneracy: 2,
        band2Degeneracy: 3,
      },
    };
    if (variant === "bounds-only" || variant === "settings-only")
      state.parameters = { spb_s: { fermi_energy: 30 } };
    if (variant === "settings-only") {
      state.held = {};
      state.customBounds = {};
    }
    const result = {
      status: "converged" as const,
      parameters: { fermi_energy: 30 },
      parameter_errors: {},
      at_bounds: [],
      known_issues: [],
      held: [],
      parameter_status: {},
    };
    if (variant === "plain-spb") {
      state.parameters = {};
      state.held = {};
      state.customBounds = {};
      state.savedModelSettings = {};
    }
    if (spb) state.fit = { status: "done", result };
    let saved = await sessionFile(
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
                { name: dormant ? "mass_ratio" : "m_eff" },
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
    expect(
      useSessionStore.getState().selection.parameterization,
    ).toBeUndefined();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(migrate).not.toHaveBeenCalled();
    if (dormant) {
      expect(useSessionStore.getState().parameters.dpb_s_rho).toBeUndefined();
      expect(useSessionStore.getState().customBounds.dpb_s_rho).toBeUndefined();
      expect(useSessionStore.getState().held.dpb_s_rho).toBeUndefined();
      expect(useSessionStore.getState().fit).toEqual({
        status: "done",
        result,
      });
      expect(useSessionStore.getState().parameters.spb_s).toEqual({
        fermi_energy: 30,
      });
      expect(useSessionStore.getState().selection.legacySource).toContain(
        variant === "values" ? '"m_eff":-3' : '"band2Degeneracy":3',
      );
      expect(useSessionStore.getState().savedModelSettings.dpb).toBeUndefined();
      expect(
        screen.getByText(/Historical DPB settings are archived/),
      ).toBeTruthy();
    }
    if (spb) {
      const archive = useSessionStore.getState().selection.legacySource;
      if (!dormant) expect(archive).toBeUndefined();
      for (let n = 0; n < 3; n++) {
        const version = String(n);
        saved = await sessionFile(
          useSessionStore.getState(),
          {
            appVersion: version,
            apiVersion: null,
            saved: "2026-11-20T00:00:00Z",
          },
          () => null,
        );
        fireEvent.click(screen.getByRole("button", { name: "Open session" }));
        await vi.waitFor(() =>
          expect(useSessionStore.getState().restored?.appVersion).toBe(version),
        );
        expect(useSessionStore.getState().selection.legacySource).toBe(archive);
      }
    }
    client.clear();
  },
);
